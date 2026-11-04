import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ledger", ROOT / "scripts" / "ledger.py")
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


def source(identity="SRC-1", content=b"Synthetic revenue: 18.5"):
    return {"source_id": identity, "label": "Synthetic summary", "version": identity,
            "sha256": ledger.digest(content), "limitations": "Synthetic fixture"}


def claim(identity="C-1", source_id="SRC-1", value=18.5, **changes):
    result = {"claim_id": identity, "entity": "Synthetic Asset A", "metric": "revenue",
              "period": "FY2025", "units": "million", "currency": "USD", "basis": "reported_actual",
              "qualifiers": ["standalone"], "value": value,
              "evidence": [{"source_id": source_id, "locator": "Line 1"}], "unknown_reason": None}
    result.update(changes)
    return result


def decision(cid, action="accept", supersedes=None):
    return {"claim_id": cid, "action": action, "supersedes": supersedes or []}


def apply(base, update, decisions, identity="R-1"):
    raw = ledger.encode(base)
    proposal = ledger.stage(base, raw, update)
    proposal_raw = ledger.encode(proposal)
    review = {"review_id": identity, "actor": "Synthetic reviewer", "date": "2026-02-01",
              "reference": "Synthetic test decision", "proposal_sha256": ledger.digest(proposal_raw),
              "decisions": decisions}
    return ledger.apply_review(base, raw, proposal, proposal_raw, review)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.base = ledger.new_ledger("synthetic-ledger")
        self.update = {"sources": [source()], "claims": [claim()]}

    def test_stage_does_not_mutate_base_or_accept(self):
        before = ledger.encode(self.base)
        plan = ledger.stage(self.base, before, self.update)
        self.assertEqual(before, ledger.encode(self.base))
        self.assertEqual(plan["candidate_check"]["statuses"], {"C-1": "pending"})
        self.assertEqual(plan["candidate_check"]["source_truth"], "not_checked")

    def test_explicit_supersession_preserves_originals(self):
        first = apply(self.base, self.update, [decision("C-1")])
        second_update = {"sources": [source("SRC-2", b"Synthetic revised revenue: 19.1")],
                         "claims": [claim("C-2", "SRC-2", 19.1)]}
        with self.assertRaisesRegex(ledger.Invalid, "supersession"):
            apply(first, second_update, [decision("C-2")], "R-2")
        second = apply(first, second_update, [decision("C-2", supersedes=["C-1"])], "R-2")
        self.assertEqual(second["claims"][0], first["claims"][0])
        self.assertEqual(second["reviews"][0], first["reviews"][0])
        self.assertEqual(ledger.validate(second)["statuses"], {"C-1": "superseded", "C-2": "accepted"})
        self.assertEqual(second["parent_sha256"], ledger.digest(ledger.encode(first)))

    def test_conflict_does_not_overwrite_accepted_value(self):
        first = apply(self.base, self.update, [decision("C-1")])
        conflict = {"sources": [], "claims": [claim("C-2", value=21.0)]}
        second = apply(first, conflict, [], "R-2")
        result = ledger.validate(second)
        self.assertEqual(result["statuses"]["C-1"], "accepted")
        self.assertEqual(result["statuses"]["C-2"], "pending")
        self.assertEqual(result["conflicts"][0]["claim_ids"], ["C-1", "C-2"])

    def test_source_and_claim_ids_are_immutable(self):
        first = apply(self.base, self.update, [])
        for update in ({"sources": [source(content=b"Changed")], "claims": []},
                       {"sources": [], "claims": [claim(value=100)]}):
            with self.subTest(update=update), self.assertRaisesRegex(ledger.Invalid, "immutable"):
                ledger.stage(first, ledger.encode(first), update)

    def test_repeated_input_is_idempotent(self):
        first = apply(self.base, self.update, [])
        plan = ledger.stage(first, ledger.encode(first), self.update)
        self.assertEqual(plan["added"], {"sources": [], "claims": []})
        candidate, _ = ledger.merged(first, self.update)
        self.assertEqual(candidate, first)

    def test_unknown_is_explicit_and_cannot_be_accepted(self):
        self.update["claims"] = [claim(value=None, unknown_reason="No debt balance supplied", evidence=[])]
        pending = apply(self.base, self.update, [])
        self.assertEqual(ledger.validate(pending)["unknown_claims"], ["C-1"])
        with self.assertRaisesRegex(ledger.Invalid, "unknown claims"):
            apply(self.base, self.update, [decision("C-1")])

    def test_populated_claim_requires_known_source_and_locator(self):
        for change in ({"evidence": []}, {"evidence": [{"source_id": "missing", "locator": "p1"}]},
                       {"evidence": [{"source_id": "SRC-1", "locator": ""}]}):
            with self.subTest(change=change), self.assertRaises(ledger.Invalid):
                ledger.merged(self.base, {"sources": [source()], "claims": [claim(**change)]})

    def test_units_and_qualifiers_conflict_but_other_periods_do_not(self):
        update = {"sources": [source()], "claims": [claim(), claim("C-2", units="thousand"),
                  claim("C-3", period="FY2024"), claim("C-4", entity="Synthetic Asset B"),
                  claim("C-5", basis="forecast"), claim("C-6", qualifiers=["consolidated"])]}
        state = apply(self.base, update, [])
        self.assertEqual(ledger.validate(state)["conflicts"][0]["claim_ids"], ["C-1", "C-2", "C-6"])

    def test_stale_and_modified_proposals_are_refused(self):
        raw = ledger.encode(self.base)
        proposal = ledger.stage(self.base, raw, self.update)
        review = {"review_id": "R-1", "actor": "Synthetic reviewer", "date": "2026-02-01",
                  "reference": "Synthetic decision", "proposal_sha256": ledger.digest(ledger.encode(proposal)), "decisions": []}
        with self.assertRaisesRegex(ledger.Invalid, "stale"):
            ledger.apply_review(self.base, raw + b" ", proposal, ledger.encode(proposal), review)
        proposal["added"]["claims"] = []
        with self.assertRaisesRegex(ledger.Invalid, "modified"):
            ledger.apply_review(self.base, raw, proposal, ledger.encode(proposal), review)

    def test_review_hash_reference_and_date_are_required(self):
        raw = ledger.encode(self.base)
        proposal = ledger.stage(self.base, raw, self.update)
        proposal_raw = ledger.encode(proposal)
        review = {"review_id": "R-1", "actor": "Synthetic reviewer", "date": "2026-02-01",
                  "reference": "Synthetic test", "proposal_sha256": ledger.digest(proposal_raw), "decisions": []}
        for key, value in (("reference", ""), ("date", "2026-02-30"), ("proposal_sha256", "0" * 64)):
            broken = copy.deepcopy(review)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(ledger.Invalid):
                ledger.apply_review(self.base, raw, proposal, proposal_raw, broken)

    def test_acceptance_cannot_be_rewritten_or_supersede_other_period(self):
        first = apply(self.base, self.update, [decision("C-1")])
        with self.assertRaisesRegex(ledger.Invalid, "decided"):
            apply(first, {"sources": [], "claims": []}, [decision("C-1", "reject")], "R-2")
        with self.assertRaisesRegex(ledger.Invalid, "supersession"):
            apply(first, {"sources": [], "claims": [claim("C-2", period="FY2024")]},
                  [decision("C-2", supersedes=["C-1"])], "R-2")

    def test_no_invented_confidence_field(self):
        self.update["claims"][0]["confidence"] = 0.99
        with self.assertRaisesRegex(ledger.Invalid, "expected fields"):
            ledger.stage(self.base, ledger.encode(self.base), self.update)

    def test_duplicate_json_and_nonfinite_numbers_are_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ledger.Invalid):
                ledger.decode(raw)

    def test_cli_refuses_overwrite_and_preserves_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base.json"
            update = root / "update.json"
            out = root / "plan.json"
            base.write_bytes(ledger.encode(self.base))
            update.write_bytes(ledger.encode(self.update))
            before = (base.read_bytes(), update.read_bytes())
            command = [sys.executable, str(ROOT / "scripts" / "ledger.py"), "stage", "--ledger", str(base),
                       "--input", str(update), "--out", str(out)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            saved = out.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(saved, out.read_bytes())
            self.assertEqual(before, (base.read_bytes(), update.read_bytes()))


if __name__ == "__main__":
    unittest.main()
