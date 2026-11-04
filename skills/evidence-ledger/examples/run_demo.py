#!/usr/bin/env python3
"""Run the actual CLI on bundled synthetic evidence in a new directory."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "ledger.py"


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True)
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
    for source in (ROOT / "examples" / "inputs").iterdir():
        if source.is_file():
            shutil.copyfile(source, out / source.name)
    for update_file in ("update-initial.json", "update-revised.json"):
        update = json.loads((out / update_file).read_text())
        for source in update["sources"]:
            measured = run("fingerprint", out / source["label"]).strip()
            if source["sha256"] != measured:
                raise ValueError("synthetic input source hash mismatch")
    run("init", "--ledger-id", "synthetic-asset-review", "--out", out / "ledger-0.json")
    run("stage", "--ledger", out / "ledger-0.json", "--input", out / "update-initial.json", "--out", out / "proposal-initial.json")
    for number, base, proposal, output, decisions in (
        (1, "ledger-0.json", "proposal-initial.json", "ledger-1.json",
         [{"claim_id": "CLM-010", "action": "accept", "supersedes": []}]),
        (2, "ledger-1.json", "proposal.json", "ledger.json", []),
    ):
        if number == 2:
            run("stage", "--ledger", out / base, "--input", out / "update-revised.json", "--out", out / proposal)
        review = {"review_id": f"DEMO-REVIEW-{number}", "actor": "Synthetic reviewer",
                  "date": f"2026-02-0{number}",
                  "reference": "Synthetic exercise decision; no real-world acceptance or approval.",
                  "proposal_sha256": hashlib.sha256((out / proposal).read_bytes()).hexdigest(),
                  "decisions": decisions}
        review_path = out / f"review-{number}.json"
        write_json(review_path, review)
        run("apply", "--ledger", out / base, "--proposal", out / proposal, "--review", review_path, "--out", out / output)
    run("report", "--ledger", out / "ledger.json", "--out", out / "ledger.md")
    validation = json.loads(run("validate", "--ledger", out / "ledger.json"))
    write_json(out / "validation.json", validation)
    assert validation["statuses"] == {"CLM-010": "accepted", "CLM-020": "pending", "CLM-030": "pending"}
    assert len(validation["conflicts"]) == 1 and validation["unknown_claims"] == ["CLM-030"]
    print(f"Synthetic CLI demonstration completed: {out / 'ledger.md'}")


if __name__ == "__main__":
    main()
