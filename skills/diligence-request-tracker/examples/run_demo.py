#!/usr/bin/env python3
"""Exercise the CLI using synthetic client returns and simulated review decisions."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "tracker.py"


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def run(*arguments):
    result = subprocess.run([sys.executable, str(CLI), *map(str, arguments)], check=True,
                            capture_output=True, text=True)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    out = args.output
    for name in ("requests.json", "returned.csv"):
        shutil.copyfile(ROOT / "examples" / "inputs" / name, out / name)
    run("init", "--tracker-id", "synthetic-diligence", "--input", out / "requests.json", "--out", out / "tracker-0.json")
    run("export", "--tracker", out / "tracker-0.json", "--round-id", "round-1", "--out", out / "client-round-1.csv",
        "--manifest", out / "round-1.json")
    run("reconcile", "--tracker", out / "tracker-0.json", "--manifest", out / "round-1.json",
        "--returned", out / "returned.csv", "--archive", out / "archive", "--out", out / "proposals.json",
        "--report", out / "proposals.md")
    review = {"review_id": "DEMO-REVIEW-1", "actor": "Synthetic reviewer", "date": "2026-02-21",
              "reference": "Synthetic exercise decision; accept both responses and explicitly close only REQ-010.",
              "proposal_sha256": hashlib.sha256((out / "proposals.json").read_bytes()).hexdigest(),
              "decisions": [{"request_id": "REQ-010", "accept_response": True, "close": True},
                            {"request_id": "REQ-040", "accept_response": True, "close": False}]}
    write_json(out / "review.json", review)
    run("apply", "--tracker", out / "tracker-0.json", "--proposal", out / "proposals.json", "--review", out / "review.json",
        "--archive", out / "archive", "--out", out / "tracker.json")
    run("export", "--tracker", out / "tracker.json", "--round-id", "round-2", "--open-only", "--out", out / "client-round-2.csv",
        "--manifest", out / "round-2.json")
    validation = json.loads(run("validate", "--tracker", out / "tracker.json"))
    write_json(out / "validation.json", validation)
    rows = list(csv.reader(io.StringIO((out / "client-round-2.csv").read_text())))
    assert [row[0] for row in rows[1:]] == ["REQ-040", "REQ-090"]
    assert rows[1][4].startswith("'=")
    assert all("PRIVATE_SYNTHETIC" not in (out / name).read_text() for name in ("client-round-1.csv", "client-round-2.csv"))
    assert validation["statuses"] == {"open": 1, "answered": 1, "closed": 1}
    print(f"Synthetic CLI roundtrip completed: {out / 'proposals.md'}")


if __name__ == "__main__":
    main()
