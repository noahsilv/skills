"""Fixed finance steps and the files each step reads and produces."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEBT = ROOT / "skills/debt-schedule"
SCENARIO = ROOT / "skills/scenario-analysis"
LIQUIDITY = HERE.parent / "debt-liquidity"

STEPS = ("debt", "operating", "liquidity")
PARENT = {"debt": None, "operating": "debt", "liquidity": "operating"}
FIXTURES = {"terms.json": DEBT / "examples/terms.json",
            "operations.json": SCENARIO / "examples/connected-operating-case.json"}
INPUTS = {"debt": ("terms.json",), "operating": ("operations.json", "terms.json"), "liquidity": ()}
CODE = {
    "debt": (DEBT / "scripts/debt_schedule.py",),
    "operating": (SCENARIO / "examples/run_connected_demo.py", SCENARIO / "scripts/scenario_analysis.py"),
    "liquidity": (LIQUIDITY / "liquidity.py",),
}
OUTPUTS = {
    "debt": ("report/report.json", "report/report.md", "report/schedule.csv", "report/accruals.csv"),
    "operating": ("mapped.json", "payment-map.json", "report/report.json", "report/report.md",
                  "report/assumption_changes.csv", "report/cases.csv", "report/period_results.csv",
                  "report/sensitivities.csv"),
    "liquidity": ("report.json", "report.md"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def execute(step, inputs, out, parent):
    if step == "debt":
        sys.path.insert(0, str(DEBT / "scripts"))
        from debt_schedule import run
        run(inputs / "terms.json", out / "report")
    elif step == "operating":
        sys.path.insert(0, str(SCENARIO / "examples"))
        from run_connected_demo import map_debt, scenario
        template, _ = scenario.read_input(inputs / "operations.json")
        debt_report, _ = scenario.read_input(parent / "report/report.json")
        mapped, payments = map_debt(template, debt_report, sha(inputs / "terms.json"))
        save(out / "mapped.json", mapped)
        save(out / "payment-map.json", payments)
        scenario.run(out / "mapped.json", out / "report")
    elif step == "liquidity":
        sys.path.insert(0, str(LIQUIDITY))
        from liquidity import analyze, markdown
        source = parent / "report/report.json"
        content = source.read_bytes()
        result = analyze(json.loads(content))
        result["scenario_report_sha256"] = hashlib.sha256(content).hexdigest()
        save(out / "report.json", result)
        (out / "report.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    else:
        raise ValueError(f"Unknown finance step: {step}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=STEPS)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("parent", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        execute(args.step, args.inputs, args.out, args.parent)
    except (ValueError, OSError, ArithmeticError) as exc:
        parser.exit(1, f"{args.step}: {exc}\n")
