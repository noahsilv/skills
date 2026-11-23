"""Trace synthetic reported actuals into two model-review cases."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from openpyxl import Workbook, load_workbook


SKILLS = Path(__file__).resolve().parents[2] / "skills"
STATEMENTS = SKILLS / "financial-statement-analysis"
PLANNER = SKILLS / "actuals-update-planner"
REGRESSION = SKILLS / "model-regression-testing/scripts"
PERIOD = "FY2025"
UNIT = "USD millions"
# Mapped source metric, model cell, sign of the statement amount in the model.
ROWS = {
    "sales": ("revenue", "C5", 1),
    "costs": ("cost_of_sales", "C6", -1),
    "operating_cash": ("cash_from_operations", "C9", 1),
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tool(script, *args, expected=0):
    result = subprocess.run([sys.executable, str(script), *map(str, args)],
                            text=True, capture_output=True)
    if result.returncode != expected:
        raise RuntimeError(f"{script.name} exited {result.returncode}, expected {expected}. "
                           f"{result.stdout.strip()} {result.stderr.strip()}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_controls(out, statements, plan):
    period, = statements["periods"]
    source, = statements["sources"]
    planned_source, = plan["sources"]
    source_hash = digest(STATEMENTS / "examples" / source["document"])
    require(source_hash == digest(out / "inputs/sources" / planned_source["file"])
            == planned_source["sha256"] == source["sha256"], "Disclosure versions differ")
    require(statements["status"] == "COMPLETE" and plan["status"] == "PLAN_READY",
            "The statement analysis or actuals plan is incomplete")
    require(statements["entity"]["name"] == plan["entity"] and
            statements["entity"]["scope"] == plan["scope"] and
            statements["currency"] == plan["currency"] == "USD" and
            statements["scale"] == plan["scale"] == "1000000" and
            plan["period"] == {"start": period["start"], "end": period["end"]} and
            (period["start"], period["end"]) == ("2025-01-01", "2025-12-31"),
            "Entity, reporting basis or period differs")
    by_id = {row["id"]: row for row in plan["variances"]}
    require(set(by_id) == set(ROWS) and len(plan["variances"]) == len(ROWS),
            "Unexpected actuals plan coverage")
    reference = Workbook()
    reference.properties.creator = "Noah Silverman"
    sheet = reference.active
    sheet.title = "Reported"
    sheet.append(["Metric", PERIOD, UNIT])
    pairs, watch = [], []
    for index, (name, (metric, cell, sign)) in enumerate(ROWS.items(), start=2):
        amount = Decimal(period["normalized_values"][metric]["value"])
        row = by_id[name]
        require(row["model_cell"] == cell and row["source_id"] == planned_source["id"] and
                amount * sign == Decimal(row["actual"]), f"Plan disagrees with statement for {name}")
        sheet.append([metric, amount])
        left = {"sheet": "Forecast", "cell": cell, "period": PERIOD, "unit": UNIT}
        right = {"sheet": "Reported", "cell": f"B{index}", "period": PERIOD,
                 "unit": UNIT, "multiplier": sign}
        pairs.append({"id": name, "comparison_unit": UNIT, "left": left, "right": right})
        watch.append({"id": name, **left})
    reference.save(out / "reported.xlsx")
    reference.close()
    watch.append({"id": "growth", "sheet": "Forecast", "cell": "D8", "period": "FY2026", "unit": "fraction"})
    write(out / "tieout-map.json", {"schema_version": 1, "pairs": pairs})
    write(out / "watch.json", {"schema_version": 1, "items": watch})
    write(out / "declarations.json", {"schema_version": 1, "changes": [
        {"id": name, "reason": "Replace the estimate with the reported annual amount."} for name in ROWS
    ]})
    return source_hash


def snapshot(out, path, label, target):
    run_tool(REGRESSION / "export_workbook.py", path, "--watch", out / "watch.json",
             "--label", label, "--out", target)


def review_case(out, model, name, exceptions):
    case = out / name
    case.mkdir()
    candidate = case / "returned.xlsx"
    # Build a separate analyst-return fixture from the estimate workbook. The
    # values are deliberately keyed independently of the plan and statement.
    book = load_workbook(model)
    try:
        sheet = book["Forecast"]
        sheet["C4"], sheet["C5"], sheet["C9"] = "FY2025A", 1280, 185
        sheet["C6"] = -702 if exceptions else -720
        if exceptions:
            sheet["D8"] = 0.06
        book.properties.creator = "Noah Silverman"
        book.save(candidate)
    finally:
        book.close()
    submitted = digest(candidate)
    tieout_file = case / "tieout.json"
    run_tool(SKILLS / "workbook-tieout/scripts/tieout.py", candidate, out / "reported.xlsx",
             "--mapping", out / "tieout-map.json", "--out", tieout_file, expected=1 if exceptions else 0)
    snapshot(out, candidate, name, case / "snapshot.json")
    regression_file = case / "regression.json"
    run_tool(REGRESSION / "regression.py", out / "baseline.json", case / "snapshot.json",
             "--declarations", out / "declarations.json", "--out", regression_file,
             expected=1 if exceptions else 3)
    tieout, regression = load(tieout_file), load(regression_file)
    matches = {r["id"]: r["status"] for r in tieout["results"]}
    movements = {r["id"]: r["status"] for r in regression["results"]}
    expected_matches = dict.fromkeys(ROWS, "MATCH")
    if exceptions:
        expected_matches["costs"] = "MISMATCH"
    require(matches == expected_matches, f"{name}: unexpected source comparisons")
    expected_movement = {**dict.fromkeys(ROWS, "EXPECTED_CHANGED"), "growth": "REGRESSION" if exceptions else "STABLE"}
    require(movements == expected_movement, f"{name}: unexpected model movements")
    cost = next(r for r in tieout["results"] if r["id"] == "costs")
    growth = next(r for r in regression["results"] if r["id"] == "growth")
    require(Decimal(cost["delta"]) == (18 if exceptions else 0), f"{name}: incorrect cost difference")
    require(Decimal(growth["delta"]) == (Decimal("0.01") if exceptions else 0),
            f"{name}: incorrect growth difference")
    require(submitted == digest(candidate), "Candidate changed during review")
    return {"case": name, "tieout": tieout["status"], "row_status": matches,
            "signed_cost_difference_usd_millions": str(Decimal(cost["delta"]).normalize()),
            "regression": regression["status"], "watch_status": movements,
            "growth_difference_percentage_points": str(Decimal(growth["delta"]) * 100)}


def exercise(out):
    run_tool(PLANNER / "examples/make_demo.py", "--out", out / "inputs", "--case", "annual")
    model = out / "inputs/model.xlsx"
    before = digest(model)
    run_tool(STATEMENTS / "scripts/analyze.py", STATEMENTS / "examples/complete.json", "--out", out / "statements")
    run_tool(PLANNER / "scripts/plan.py", model, "--mapping", out / "inputs/mapping.json",
             "--sources", out / "inputs/sources", "--out", out / "plan")
    plan = load(out / "plan/plan.json")
    source_hash = source_controls(out, load(out / "statements/report.json"), plan)
    snapshot(out, model, "Original estimates", out / "baseline.json")
    results = [review_case(out, model, "reconciled", False),
               review_case(out, model, "exceptions", True)]
    require(before == digest(model) == plan["inputs"]["model"]["sha256"], "Baseline workbook changed")
    report = {"fixture": "Synthetic annual actuals review", "disclosure_sha256": source_hash,
              "baseline_preserved": True, "recalculated": False, "results": results}
    require(report == load(Path(__file__).with_name("expected.json")),
            "Review results differ from the recorded fixture")
    write(out / "summary.json", report)
    for row in results:
        print(f"{row['case']}: source tieout {row['tieout']}, model regression {row['regression']}, "
              f"signed cost difference {row['signed_cost_difference_usd_millions']} USD millions, "
              f"growth difference {row['growth_difference_percentage_points']} percentage points")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="retain the run in a new directory")
    args = parser.parse_args()
    try:
        if args.out is None:
            with TemporaryDirectory() as folder:
                exercise(Path(folder))
        else:
            args.out.mkdir(parents=True, exist_ok=False)
            exercise(args.out)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Review harness failed: {exc}\n")


if __name__ == "__main__":
    main()
