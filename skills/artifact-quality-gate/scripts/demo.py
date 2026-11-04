#!/usr/bin/env python3
"""Generate one synthetic lifecycle in a new directory, running a known CSV checker."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

import gate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        destination = gate.no_symlinks(args.output_dir)
        gate.require(destination.parent.is_dir(), "destination parent must already exist")
        destination.mkdir(exist_ok=False)
        examples = Path(__file__).resolve().parents[1] / "examples" / "inputs"
        for name in ("sample.csv", "checker.py", "spec.json", "record-request.json"):
            with (destination / name).open("xb") as stream:
                stream.write((examples / name).read_bytes())
        spec, _ = gate.load_json(destination / "spec.json")
        gate.write_new(destination / "run.json", gate.initialize(spec, destination))
        # Only the known, bundled synthetic checker is executed by this demo.
        checked = subprocess.run([sys.executable, str(destination / "checker.py"), str(destination / "sample.csv")], capture_output=True, timeout=10, check=False)
        gate.require(checked.returncode == 0, "synthetic checker failed")
        with (destination / "result.log").open("xb") as stream:
            stream.write(checked.stdout)
        run, run_fp = gate.load_json(destination / "run.json")
        request, _ = gate.load_json(destination / "record-request.json")
        gate.write_new(destination / "check-record.json", gate.make_record(run, run_fp, request, destination))
        record, record_fp = gate.load_json(destination / "check-record.json")
        report = gate.aggregate(run, run_fp, [record], destination)
        report["record_files"] = [{"path": str(destination / "check-record.json"), **record_fp}]
        gate.write_new(destination / "report.json", report)
        readable = "# Synthetic artifact gate\n\nVerdict: **ATTESTED** (self-reported evidence).\n\nOne required CSV shape check has a pass record bound to this run and the current sample, checker, and log bytes. The checker tests header, row width, and presence of data rows only.\n\n" + gate.LIMITATION + "\n"
        with (destination / "report.md").open("x", encoding="utf-8") as stream:
            stream.write(readable)
        print(json.dumps({"verdict": report["verdict"], "output_dir": str(destination), "assurance": gate.ASSURANCE, "limitation": gate.LIMITATION}))
        return 0
    except (gate.ValidationError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc), "verdict": "INCOMPLETE"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
