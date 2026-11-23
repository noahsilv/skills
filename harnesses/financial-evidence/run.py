"""Follow a synthetic disclosure revision through the opening and closing debt balances."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from evidence_graph import FILES, build, impact, related, require, verified


ROOT = Path(__file__).resolve().parents[2]
STATEMENTS = ROOT / "skills/financial-statement-analysis"
FINANCING = ROOT / "skills/financing-pro-forma"
SOURCE_ID = "reported.debt_current"


def write(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def tool(script, *args):
    process = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)
    if process.returncode:
        raise ValueError(f"{script.name} exited {process.returncode}: {process.stderr.strip()} {process.stdout.strip()}")


def version(folder, corrected):
    folder.mkdir()
    source = (STATEMENTS / "examples/synthetic-disclosure.txt").read_bytes()
    normalized = json.loads((STATEMENTS / "examples/complete.json").read_bytes())
    require(hashlib.sha256(source).hexdigest() == normalized["sources"][0]["sha256"],
            "The baseline disclosure and normalization use different versions")
    if corrected:
        old = "Current borrowings excluding leases 90,000"
        new = "Current borrowings excluding leases 95,000"
        require(source.splitlines().count(old.encode()) == 1, "Starting disclosure line differs")
        source = source.replace(old.encode(), new.encode()) + (
            b"Synthetic correction: 5,000 of other current liabilities is reclassified as current borrowings. "
            b"Total current liabilities and cash are unchanged.\n")
        row = normalized["periods"][0]["values"]["debt_current"]
        require(row["value"] == "90" and row["sources"][0]["locator"] == "physical text page 2: " + old,
                "Starting normalized borrowing line differs")
        row["value"] = "95"
        row["sources"][0]["locator"] = "physical text page 2: " + new
        normalized["sources"][0]["sha256"] = hashlib.sha256(source).hexdigest()
    (folder / FILES["disclosure"]).write_bytes(source)
    write(folder / FILES["normalized"], normalized)
    shutil.copyfile(FINANCING / "examples/transactions.json", folder / FILES["transactions"])
    return calculate_version(folder)


def calculate_version(folder):
    tool(STATEMENTS / "scripts/analyze.py", folder / FILES["normalized"], "--out", folder / "statements")
    bridge = FINANCING / "scripts/bridge.py"
    tool(bridge, "prepare", folder / FILES["statements"], "--period", "fy2025", "--out", folder / FILES["opening"])
    tool(bridge, "bridge", folder / FILES["opening"], folder / FILES["transactions"], "--out", folder / FILES["closing"])
    write(folder / "graph.json", build(folder))
    return verified(folder)


def walkthrough(folder):
    original = version(folder / "original", False)
    revised = version(folder / "revised", True)
    changes = impact(original, revised, SOURCE_ID)
    write(folder / "impact.json", changes)
    selected = ("reported.debt_current", "opening.net_debt", "refinance.closing.net_debt",
                "refinance.change_in_net_debt", "capital_spending.closing.net_debt", "capital_spending.change_in_net_debt")
    table = {row["id"]: [row["original"], row["revised"], row["unit"]] for row in changes if row["id"] in selected}
    require(table == json.loads(Path(__file__).with_name("expected.json").read_bytes()), "Worked revision differs")
    require("refinance.closing.cash_and_equivalents" not in related(revised, SOURCE_ID, "downstream"),
            "The borrowing reclassification should not feed closing cash")
    print("Trace ID | Original | Revised | Unit")
    for key in selected:
        print(" | ".join([key, *table[key]]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    demo = sub.add_parser("demo", help="run both source versions and compare their results")
    demo.add_argument("--out", type=Path, help="retain both versions in a new directory")
    check = sub.add_parser("verify", help="recheck a saved graph against the source and report files")
    check.add_argument("version", type=Path)
    query = sub.add_parser("trace", help="show upstream support or downstream consequences for a trace ID")
    query.add_argument("version", type=Path)
    query.add_argument("id")
    query.add_argument("--direction", choices=("upstream", "downstream"), default="upstream")
    compare = sub.add_parser("impact", help="compare the downstream values of the same trace ID")
    compare.add_argument("original", type=Path)
    compare.add_argument("revised", type=Path)
    compare.add_argument("id")
    args = parser.parse_args()
    try:
        if args.action == "demo":
            if args.out:
                args.out.mkdir(parents=True, exist_ok=False)
                walkthrough(args.out)
            else:
                with TemporaryDirectory() as directory:
                    walkthrough(Path(directory))
        elif args.action == "verify":
            graph = verified(args.version)
            print(f"Verified {len(graph['nodes'])} amounts against {len(graph['files'])} files.")
        elif args.action == "trace":
            graph = verified(args.version)
            print(json.dumps({key: graph["nodes"][key] for key in related(graph, args.id, args.direction)}, indent=2))
        else:
            print(json.dumps(impact(verified(args.original), verified(args.revised), args.id), indent=2))
    except (ValueError, OSError, KeyError, ArithmeticError, TypeError) as exc:
        parser.exit(1, f"Financial evidence: {exc}\n")


if __name__ == "__main__":
    main()
