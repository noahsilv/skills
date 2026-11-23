"""Run the public finance walkthroughs and their regression checks."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
# Each entry names a real case, its walkthrough command and its test directory.
CASES = {
    "actuals": (("harnesses/actuals-review/run.py",), None),
    "liquidity": (("harnesses/debt-liquidity/run.py",), "harnesses/debt-liquidity"),
    "credit": (("harnesses/credit-review/demo.py",), "harnesses/credit-review"),
    "trace": (("harnesses/financial-evidence/run.py", "demo"), "harnesses/financial-evidence"),
    "workbook": ((), "harnesses/excel-recalculation"),
    "diligence": (("examples/context_evidence_demo.py",), None),
}


def check_case(name, scratch, with_calc):
    walkthrough, suite = CASES[name]
    checks = []
    if walkthrough:
        args = list(walkthrough)
        if name == "diligence":
            args.append(str(scratch / "diligence"))
        checks.append(("walkthrough", args))
    if suite:
        checks.append(("tests", ["-m", "unittest", "discover", "-s", suite, "-p", "test_*.py"]))
    if name == "workbook" and with_calc:
        checks.append(("saved_workbook_results", ["harnesses/excel-recalculation/run.py", "calculate"]))
    result = {"case": name, "status": "PASS", "checks": []}
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    environment.pop("PYTHONOPTIMIZE", None)
    for label, args in checks:
        item = {"check": label, "status": "FAIL"}
        result["checks"].append(item)
        try:
            process = subprocess.run([sys.executable, *args], cwd=ROOT, env=environment,
                                     capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            log = process.stdout + process.stderr
            if process.returncode != 0:
                raise ValueError(log.strip() or f"Process exited with code {process.returncode}")
            if label == "tests":
                count = re.search(r"^Ran (\d+) tests? in ", log, re.MULTILINE)
                if not count or int(count[1]) == 0:
                    raise ValueError("The test runner executed zero tests")
                item["tests"] = int(count[1])
            if label == "saved_workbook_results":
                receipt = json.loads(process.stdout)
                if [(c["version"], c["status"]) for c in receipt["checks"]] != [
                    ("baseline", "VERIFIED"), ("challenge", "VERIFIED")
                ]:
                    raise ValueError("Incomplete calculation receipt")
                item["engine"] = receipt["engine"]
                item["formula_results"] = sum(c["formula_count"] for c in receipt["checks"])
            item["status"] = "PASS"
        except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
            item["error"] = str(exc)
            result["status"] = "FAIL"
            break
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=CASES,
                        help="run one case, repeat to select several (default: all)")
    parser.add_argument("--with-calc", action="store_true", help="also calculate both workbooks with LibreOffice")
    parser.add_argument("--json", action="store_true", help="print a machine-readable test report")
    args = parser.parse_args()
    names = list(dict.fromkeys(args.case or CASES))
    if args.with_calc and "workbook" not in names:
        parser.error("--with-calc requires the workbook case")
    with TemporaryDirectory() as folder:
        cases = []
        for name in names:
            if not args.json:
                print(f"Running {name}", flush=True)
            case = check_case(name, Path(folder), args.with_calc)
            cases.append(case)
            if not args.json:
                for item in case["checks"]:
                    detail = f" ({item['tests']} tests)" if "tests" in item else ""
                    print(f"  {item['status']} {item['check']}{detail}", flush=True)
                    if "error" in item:
                        print(item["error"], file=sys.stderr)
    passed = all(case["status"] == "PASS" for case in cases)
    if args.json:
        print(json.dumps({"status": "PASS" if passed else "FAIL", "cases": cases}, indent=2))
    else:
        print(f"{sum(case['status'] == 'PASS' for case in cases)} of {len(cases)} cases passed.")
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
