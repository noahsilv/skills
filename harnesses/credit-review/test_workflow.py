from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from demo import CLI, invoke, walkthrough
import run


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "review"

    def initialize(self):
        run.initialize(self.root)

    def advance(self, step="debt", refresh=False):
        with closing(run.connect(self.root, writable=True)) as db:
            for name in run.STEPS[:run.STEPS.index(step) + 1]:
                run.advance_step(self.root, db, name, refresh)

    def state(self):
        with closing(run.connect(self.root)) as db:
            return run.inspect(self.root, db)

    def history(self):
        with closing(run.connect(self.root)) as db:
            return run.receipts(db)

    def test_revision_reuses_debt_and_keeps_both_input_versions(self):
        walkthrough(self.root)
        history = self.history()
        for row in history:
            if row["step"] != "operating":
                continue
            folder = self.root / "attempts" / row["folder"]
            snapshot = folder / "inputs/operations.json"
            self.assertEqual(run.sha(snapshot), row["inputs"]["inputs/operations.json"])
            self.assertEqual(row["outputs"]["upstream/report/report.json"], history[0]["outputs"]["report/report.json"])
            model = json.loads(snapshot.read_bytes())
            combined = next(c for c in model["cases"] if c["id"] == "combined")
            self.assertEqual(combined["overrides"]["fixed_cost"]["values"][0], "1.15" if row["id"] == 2 else "1.10")
        receipt, = json.loads(invoke("receipt", self.root, "liquidity"))
        self.assertEqual((receipt["id"], receipt["parent_id"]), (5, 4))
        self.assertEqual({r["run_id"] for r in history}, {receipt["run_id"]})
        self.assertTrue(receipt["recorded_utc"].endswith("Z"))
        self.assertIn(sys.implementation.name, receipt["runtime"])

    def test_changed_report_invalidates_downstream_even_if_repair_reproduces_same_bytes(self):
        self.initialize()
        self.advance("liquidity")
        first = self.state()
        path = self.root / first["debt"]["folder"] / "report/schedule.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        state = self.state()
        self.assertEqual([row["status"] for row in state.values()], ["STALE", "WAITING", "WAITING"])
        self.assertIn("schedule.csv", state["debt"]["reason"])
        self.advance("debt", refresh=True)
        self.assertEqual(self.state()["operating"]["status"], "STALE")
        self.assertEqual(path.read_bytes()[-2:], b"\n\n")
        self.advance("liquidity", refresh=True)
        self.assertEqual(len(self.history()), 6)

    def test_failed_stage_records_no_accepted_outputs_and_requires_explicit_retry(self):
        self.initialize()
        terms = self.root / "inputs/terms.json"
        original = terms.read_bytes()
        terms.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.advance()
        failed, = self.history()
        self.assertEqual((failed["outcome"], failed["outputs"]), ("FAILED", {}))
        terms.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "--refresh"):
            self.advance()
        self.advance(refresh=True)
        self.assertEqual([r["outcome"] for r in self.history()], ["FAILED", "COMPLETED"])

    def test_missing_input_blocks_before_an_attempt_is_recorded(self):
        self.initialize()
        terms = self.root / "inputs/terms.json"
        terms.rename(terms.with_suffix(".held"))
        with self.assertRaisesRegex(ValueError, "BLOCKED"):
            self.advance()
        self.assertEqual(self.history(), [])

    def test_interruption_leaves_work_ready_with_no_partial_receipt(self):
        self.initialize()
        with patch.object(run.subprocess, "run", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.advance()
        self.assertEqual(self.state()["debt"]["status"], "READY")
        self.assertEqual(self.history(), [])
        self.advance()
        self.assertEqual(len(self.history()), 1)
        self.assertEqual(len(list((self.root / "attempts").iterdir())), 2)

    def test_changed_input_during_execution_keeps_original_snapshot_and_fails(self):
        self.initialize()
        terms = self.root / "inputs/terms.json"
        original = terms.read_bytes()
        execute = subprocess.run

        def revise_after_execution(*args, **kwargs):
            result = execute(*args, **kwargs)
            terms.write_bytes(original + b"\n")
            return result

        with patch.object(run.subprocess, "run", side_effect=revise_after_execution):
            with self.assertRaisesRegex(ValueError, "input changed during execution"):
                self.advance()
        failed, = self.history()
        self.assertEqual(failed["outcome"], "FAILED")
        self.assertEqual((run.attempt_path(self.root, failed) / "inputs/terms.json").read_bytes(), original)

    def test_concurrent_advances_commit_only_one_debt_attempt(self):
        self.initialize()
        command = [sys.executable, str(CLI), "advance", str(self.root), "--through", "debt"]
        children = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        for child in children:
            output, error = child.communicate(timeout=60)
            self.assertEqual(child.returncode, 0, (output, error))
        self.assertEqual(len(self.history()), 1)

    def test_reinitialization_preserves_existing_user_files(self):
        self.root.mkdir()
        note = self.root / "note.txt"
        note.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.initialize()
        self.assertEqual(note.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
