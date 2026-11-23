"""Run a debt schedule, apply operating stresses and test cash at each payment date."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from liquidity import analyze, markdown


ROOT = Path(__file__).resolve().parents[2]
DEBT = ROOT / "skills/debt-schedule"
SCENARIO = ROOT / "skills/scenario-analysis"
TERMS = DEBT / "examples/terms.json"
OPERATIONS = SCENARIO / "examples/connected-operating-case.json"


def run(out, terms, operations):
    connected = out / "calculation"
    subprocess.run([sys.executable, str(SCENARIO / "examples/run_connected_demo.py"),
                    "--debt-script", str(DEBT / "scripts/debt_schedule.py"), "--debt-terms", str(terms),
                    "--case-template", str(operations), "--out", str(connected)], check=True, stdout=sys.stderr)
    scenario_bytes = (connected / "scenario/report.json").read_bytes()
    handoff = json.loads((connected / "handoff.json").read_bytes())
    if hashlib.sha256(scenario_bytes).hexdigest() != handoff["scenario_report_sha256"]:
        raise ValueError("Scenario report differs from the debt handoff")
    report = analyze(json.loads(scenario_bytes))
    report["scenario_report_sha256"] = handoff["scenario_report_sha256"]
    report_text = markdown(report)
    (out / "liquidity.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "liquidity.md").write_text(report_text, encoding="utf-8", newline="\n")
    return report_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terms", type=Path, default=TERMS, help="fixed-rate debt terms JSON")
    parser.add_argument("--operations", type=Path, default=OPERATIONS, help="aligned operating case JSON")
    parser.add_argument("--out", type=Path, help="new directory for source-linked reports")
    args = parser.parse_args()
    try:
        if args.out is None:
            with TemporaryDirectory() as directory:
                result = run(Path(directory), args.terms, args.operations)
        else:
            args.out.mkdir(parents=True, exist_ok=False)
            result = run(args.out, args.terms, args.operations)
        print(result)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Liquidity run failed: {exc}\n")


if __name__ == "__main__":
    main()
