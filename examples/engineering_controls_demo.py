#!/usr/bin/env python3
"""Exercise catalog capability gaps and stale-file evidence on synthetic data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def execute(script, args, expected=0):
    result = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    if result.returncode != expected:
        raise RuntimeError(result.stderr or result.stdout)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    out = parser.parse_args().output_directory
    out.mkdir(parents=True, exist_ok=False)
    router = ROOT / "skills/skill-router/scripts/route.py"
    routing = []
    for name, capabilities in [("missing-library", ["python3.11"]), ("declared-library", ["python3.11", "openpyxl"])]:
        request = {"schema_version": 1, "query": "Use workbook-tieout to reconcile spreadsheet cells",
                   "available_capabilities": capabilities, "limit": 1}
        request_path = out / (name + ".json")
        request_path.write_text(json.dumps(request, indent=2) + "\n")
        target = out / (name + "-result.json")
        execute(router, ["--catalog", ROOT / "catalog/skills.json", "--root", ROOT, "--request", request_path, "--output", target])
        routing.append({"case": name, "result": json.loads(target.read_text())})
    for index, expected_missing in [(0, ["openpyxl"]), (1, [])]:
        suggestion = routing[index]["result"]["suggestions"][0]
        if suggestion["id"] != "workbook-tieout" or suggestion["missing_capabilities"] != expected_missing:
            raise RuntimeError("routing result did not preserve the requested skill and declared capability gap")
    gate_root = out / "gate-run"
    execute(ROOT / "skills/artifact-quality-gate/scripts/demo.py", ["--output-dir", gate_root])
    before = json.loads((gate_root / "report.json").read_text())
    if before["verdict"] != "ATTESTED":
        raise RuntimeError("unexpected initial gate verdict")
    original = (gate_root / "sample.csv").read_bytes()
    # Only the new synthetic artifact is changed, after its original check.
    (gate_root / "sample.csv").write_bytes(original + b"extra,row\n")
    failed = execute(ROOT / "skills/artifact-quality-gate/scripts/gate.py", ["aggregate", "--root", gate_root,
              "--run", gate_root / "run.json", "--record", gate_root / "check-record.json",
              "--output", gate_root / "stale-report.json"], expected=2)
    if (gate_root / "stale-report.json").exists():
        raise RuntimeError("stale aggregation must not create a fresh successful report")
    stale = json.loads(failed.stderr)
    if stale.get("verdict") != "INCOMPLETE":
        raise RuntimeError("stale artifact was not reported incomplete")
    # Store full run receipts locally. The public case study links only the
    # readable summary, which contains no machine-specific filesystem paths.
    summary = {"routing": routing, "initial_gate_verdict": before["verdict"], "stale_gate_error": stale,
               "original_artifact_sha256": hashlib.sha256(original).hexdigest(),
               "edited_artifact_sha256": hashlib.sha256((gate_root / "sample.csv").read_bytes()).hexdigest(),
               "stale_report_created": False}
    (out / "receipts.json").write_text(json.dumps(summary, indent=2) + "\n")
    text = '''# Executed workflow-control example

The same explicit workbook-tieout request was routed against the portfolio catalog twice: first with only Python declared, then with Python and openpyxl declared. The first response retained the requested skill while reporting a missing library. The second reported the declared capability set as available; neither response executed a spreadsheet check.

The artifact demo then ran its small synthetic CSV-shape checker, bound the file, checker and log to one run, and aggregated the record as **ATTESTED** (self-reported evidence completeness). After the sample CSV was changed, aggregation returned exit **2**, an **INCOMPLETE** error, and created no new report. The prior report remains historical evidence for the prior bytes.

This checks file/evidence consistency. It does not prove financial correctness, authenticate the checker, certify source truth or demonstrate workbook recalculation.
'''
    (out / "summary.md").write_text(text)
    print(json.dumps({"routing_cases": 2, "initial_gate": before["verdict"], "stale_exit": failed.returncode, "new_stale_report": False}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
