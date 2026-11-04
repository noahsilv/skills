#!/usr/bin/env python3
"""Run a synthetic financing-source ledger and request-return handoff."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "skills" / "evidence-brief" / "examples" / "financing"


def dump(path, obj):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(obj, stream, indent=2)
        stream.write("\n")


def run(script, *args):
    result = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    out = args.output_directory
    out.mkdir(parents=True, exist_ok=False)
    ledger = ROOT / "skills/evidence-ledger/scripts/ledger.py"
    tracker = ROOT / "skills/diligence-request-tracker/scripts/tracker.py"
    sources = []
    for sid, filename, version in [("DISCUSSION", "committee-record.md", "2030-06-14"), ("DECK", "concept-deck.md", "2030-06-10 v2")]:
        sources.append({"source_id": sid, "label": filename, "version": version,
                        "sha256": hashlib.sha256((SOURCES / filename).read_bytes()).hexdigest(),
                        "limitations": "Synthetic example; source support was checked separately from schema validation."})
    def claim(cid, metric, value, units, currency, basis, source, locator, qualifiers):
        return {"claim_id": cid, "entity": "Synthetic refinancing", "metric": metric,
                "period": "proposed transaction", "units": units, "currency": currency,
                "basis": basis, "qualifiers": qualifiers, "value": value,
                "evidence": [{"source_id": source, "locator": locator}], "unknown_reason": None}
    claims = [
        claim("SPONSOR-AMOUNT", "facility_amount", 42, "million", "EUR", "sponsor_requested", "DECK", "Slide 3", ["requested, not approved"]),
        claim("SPONSOR-TENOR", "tenor", 7, "years", None, "sponsor_requested", "DECK", "Slide 3", ["requested, not approved"]),
        claim("LENDER-AMOUNT", "facility_amount", 36, "million", "EUR", "lender_conditional", "DISCUSSION", "00:55", ["up to", "subject to reconciled debt schedule", "not a credit approval or commitment"]),
        claim("LENDER-TENOR", "tenor", 6, "years", None, "lender_conditional", "DISCUSSION", "00:55", ["subject to reconciled debt schedule", "not a credit approval or commitment"]),
        claim("DILIGENCE-DECISION", "decision", "Further diligence within the existing advisory budget only", "text", None, "recorded_decision", "DISCUSSION", "02:10", ["no financing amount or tenor approved"]),
    ]
    dump(out / "claims-input.json", {"sources": sources, "claims": claims})
    run(ledger, "init", "--ledger-id", "financing-case", "--out", out / "ledger-base.json")
    run(ledger, "stage", "--ledger", out / "ledger-base.json", "--input", out / "claims-input.json", "--out", out / "claim-proposal.json")
    proposal_hash = hashlib.sha256((out / "claim-proposal.json").read_bytes()).hexdigest()
    dump(out / "synthetic-review.json", {"review_id": "DEMO-PENDING", "actor": "Synthetic reviewer",
         "date": "2030-06-14", "reference": "Demonstration only: record these claims as pending, accept none.",
         "proposal_sha256": proposal_hash, "decisions": []})
    run(ledger, "apply", "--ledger", out / "ledger-base.json", "--proposal", out / "claim-proposal.json",
        "--review", out / "synthetic-review.json", "--out", out / "ledger-pending.json")
    run(ledger, "report", "--ledger", out / "ledger-pending.json", "--out", out / "ledger.md")
    request = {"request_id": "DD-010", "category": "Debt reconciliation",
               "request": "Provide the reconciled debt schedule and identify the two balances awaiting servicer confirmation.",
               "due_date": "", "response": "", "evidence_reference": "", "status": "open",
               "private_note": "Synthetic review note: no facility terms have been approved."}
    dump(out / "requests-input.json", [request])
    run(tracker, "init", "--tracker-id", "financing-case", "--input", out / "requests-input.json", "--out", out / "tracker-base.json")
    run(tracker, "export", "--tracker", out / "tracker-base.json", "--round-id", "round-1",
        "--out", out / "client-request.csv", "--manifest", out / "round.json")
    rows = list(csv.reader(io.StringIO((out / "client-request.csv").read_text())))
    if len(rows) != 2 or rows[1][0] != "DD-010":
        raise RuntimeError("unexpected request export")
    rows[1][4] = "The schedule is still under reconciliation; two servicer balances remain outstanding."
    rows[1][5] = "Synthetic return; corroboration pending."
    with (out / "returned.csv").open("x", newline="", encoding="utf-8") as stream:
        csv.writer(stream, quoting=csv.QUOTE_ALL).writerows(rows)
    before = hashlib.sha256((out / "tracker-base.json").read_bytes()).hexdigest()
    run(tracker, "reconcile", "--tracker", out / "tracker-base.json", "--manifest", out / "round.json",
        "--returned", out / "returned.csv", "--archive", out / "archive",
        "--out", out / "response-proposal.json", "--report", out / "response-proposal.md")
    assert hashlib.sha256((out / "tracker-base.json").read_bytes()).hexdigest() == before
    files = ["ledger.md", "ledger-pending.json", "client-request.csv", "returned.csv", "response-proposal.md", "response-proposal.json"]
    dump(out / "handoff.json", {"scope": "Synthetic source-to-ledger and request-return demonstration. No client delivery or response acceptance occurred.",
         "claim_status": "pending", "request_id": "DD-010", "tracker_after_reconciliation": "unchanged; response proposed only",
         "sources": sources, "outputs": {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in files}})
    print(json.dumps({"status": "DEMONSTRATED", "claims": len(claims), "request_id": "DD-010", "response_applied": False}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, AssertionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
