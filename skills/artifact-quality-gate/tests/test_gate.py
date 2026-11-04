"""Test attestation completeness and reject stale, cross-run, malformed evidence."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gate.py"
SPEC = importlib.util.spec_from_file_location("quality_gate", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, content in [("artifact.csv", "label,value\nrevenue,10\n"), ("checker.py", "# synthetic inspection identity\n"), ("result.log", "synthetic self-reported check: pass\n"), ("support.txt", "synthetic support\n")]:
            (self.root / name).write_text(content, encoding="utf-8")
        self.spec = {"schema_version": 1, "artifacts": [{"id": "report", "path": "artifact.csv"}], "checks": [{"id": "header-check", "artifact_ids": ["report"], "requirement": "Confirm the CSV has the declared header.", "kind": "file_check"}]}
        self.request = {"schema_version": 1, "check_id": "header-check", "status": "pass", "summary": "Caller reports that the declared header exists.", "evidence": [{"role": "checker", "path": "checker.py"}, {"role": "log", "path": "result.log"}]}
        self.run = gate.initialize(self.spec, self.root)
        self.fp = gate.bytes_fingerprint(json.dumps(self.run).encode())

    def record(self, request=None):
        return gate.make_record(self.run, self.fp, self.request if request is None else request, self.root)

    def aggregate(self, records):
        return gate.aggregate(self.run, self.fp, records, self.root)

    def test_complete_attestation_is_explicitly_not_correctness(self):
        record = self.record()
        result = self.aggregate([record])
        self.assertEqual(result["verdict"], "ATTESTED")
        self.assertEqual(result["assurance"], "self_reported")
        self.assertIn("correctness", result["limitation"])
        self.assertEqual(record["artifacts"], self.run["artifacts"])
        self.assertEqual(len(record["evidence"][0]["sha256"]), 64)

    def test_generated_objects_do_not_share_mutable_inputs(self):
        before_spec = copy.deepcopy(self.spec)
        self.run["checks"][0]["requirement"] = "A different requirement"
        self.assertEqual(self.spec, before_spec)
        record = self.record()
        before_run = copy.deepcopy(self.run)
        record["artifacts"][0]["path"] = "other.csv"
        self.assertEqual(self.run, before_run)

    def test_no_records_is_incomplete(self):
        result = self.aggregate([])
        self.assertEqual(result["verdict"], "INCOMPLETE")
        self.assertEqual(result["missing_checks"], ["header-check"])

    def test_failed_check_is_findings(self):
        self.request["status"] = "fail"
        self.assertEqual(self.aggregate([self.record()])["verdict"], "FINDINGS")

    def test_not_run_remains_incomplete(self):
        self.request.update(status="not_run", evidence=[], summary="Checker unavailable.")
        result = self.aggregate([self.record()])
        self.assertEqual(result["verdict"], "INCOMPLETE")
        self.assertEqual(result["not_run_checks"], ["header-check"])

    def test_missing_check_takes_precedence_over_failure(self):
        self.run["checks"].append({"id": "second-check", "artifact_ids": ["report"], "requirement": "Second required review.", "kind": "file_check"})
        self.fp = gate.bytes_fingerprint(json.dumps(self.run).encode())
        self.request["status"] = "fail"
        result = self.aggregate([self.record()])
        self.assertEqual(result["verdict"], "INCOMPLETE")
        self.assertEqual(result["failed_checks"], ["header-check"])

    def test_artifact_changed_before_record_rejected(self):
        (self.root / "artifact.csv").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(gate.ValidationError, "changed since initialization"):
            self.record()

    def test_artifact_changed_after_record_rejected(self):
        record = self.record()
        (self.root / "artifact.csv").write_text("label,value\nrevenue,11\n", encoding="utf-8")
        with self.assertRaisesRegex(gate.ValidationError, "changed since initialization"):
            self.aggregate([record])

    def test_changed_log_checker_support_rejected(self):
        self.request["evidence"].append({"role": "supporting", "path": "support.txt"})
        for name in ["result.log", "checker.py", "support.txt"]:
            with self.subTest(name=name):
                target = self.root / name
                old = target.read_bytes()
                record = self.record()
                target.write_bytes(b"changed")
                with self.assertRaisesRegex(gate.ValidationError, "evidence changed"):
                    self.aggregate([record])
                target.write_bytes(old)

    def test_missing_evidence_file_rejected(self):
        record = self.record()
        (self.root / "result.log").unlink()
        with self.assertRaises(gate.ValidationError):
            self.aggregate([record])

    def test_cross_run_id_rejected(self):
        record = self.record()
        record["run_id"] = gate.initialize(self.spec, self.root)["run_id"]
        with self.assertRaisesRegex(gate.ValidationError, "mixed runs"):
            self.aggregate([record])

    def test_run_byte_fingerprint_mismatch_rejected(self):
        record = self.record()
        record["run_sha256"] = "0" * 64
        with self.assertRaisesRegex(gate.ValidationError, "different run manifest bytes"):
            self.aggregate([record])

    def test_run_path_is_bound_to_supplied_root(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaisesRegex(gate.ValidationError, "root differs"):
                gate.aggregate(self.run, self.fp, [], Path(other))

    def test_no_zero_check_or_zero_artifact_pass(self):
        for field in ("checks", "artifacts"):
            spec = copy.deepcopy(self.spec)
            spec[field] = []
            with self.subTest(field=field), self.assertRaises(gate.ValidationError):
                gate.initialize(spec, self.root)

    def test_duplicate_and_unknown_artifact_references_rejected(self):
        for ids in [["unknown"], ["report", "report"], []]:
            spec = copy.deepcopy(self.spec)
            spec["checks"][0]["artifact_ids"] = ids
            with self.subTest(ids=ids), self.assertRaises(gate.ValidationError):
                gate.initialize(spec, self.root)

    def test_uncovered_artifact_rejected(self):
        self.spec["artifacts"].append({"id": "support", "path": "support.txt"})
        with self.assertRaisesRegex(gate.ValidationError, "every artifact"):
            gate.initialize(self.spec, self.root)

    def test_duplicate_check_definitions_rejected(self):
        self.spec["checks"].append(copy.deepcopy(self.spec["checks"][0]))
        with self.assertRaisesRegex(gate.ValidationError, "duplicate check id"):
            gate.initialize(self.spec, self.root)

    def test_duplicate_records_rejected(self):
        record = self.record()
        with self.assertRaisesRegex(gate.ValidationError, "duplicate check record"):
            self.aggregate([record, record])

    def test_unrequested_check_rejected(self):
        self.request["check_id"] = "unrequested"
        with self.assertRaisesRegex(gate.ValidationError, "not explicitly required"):
            self.record()

    def test_unknown_keys_at_all_contract_levels(self):
        for where in ("spec", "artifact", "check"):
            spec = copy.deepcopy(self.spec)
            {"spec": spec, "artifact": spec["artifacts"][0], "check": spec["checks"][0]}[where]["extra"] = 1
            with self.subTest(where=where), self.assertRaises(gate.ValidationError):
                gate.initialize(spec, self.root)
        for where in ("request", "evidence"):
            request = copy.deepcopy(self.request)
            {"request": request, "evidence": request["evidence"][0]}[where]["extra"] = 1
            with self.subTest(where=where), self.assertRaises(gate.ValidationError):
                self.record(request)
        run = {**self.run, "extra": True}
        with self.assertRaises(gate.ValidationError):
            gate.validate_run(run, self.root)
        for where in ("record", "evidence", "artifact"):
            record = self.record()
            {"record": record, "evidence": record["evidence"][0], "artifact": record["artifacts"][0]}[where]["extra"] = 1
            # Copy record to prevent modifying the initialized run via shared references.
            with self.subTest(where=where), self.assertRaises(gate.ValidationError):
                self.aggregate([record])
            self.run = gate.initialize(self.spec, self.root)
            self.fp = gate.bytes_fingerprint(json.dumps(self.run).encode())

    def test_status_is_strict(self):
        for status in ["PASS", "passed", "skipped", True, 1, [], None]:
            request = copy.deepcopy(self.request)
            request["status"] = status
            with self.subTest(status=status), self.assertRaises(gate.ValidationError):
                self.record(request)

    def test_malformed_record_status_rejected_during_aggregation(self):
        record = self.record()
        record["status"] = "approved"
        with self.assertRaises(gate.ValidationError):
            self.aggregate([record])

    def test_boolean_schema_version_rejected(self):
        self.spec["schema_version"] = True
        with self.assertRaises(gate.ValidationError):
            gate.initialize(self.spec, self.root)

    def test_recalculation_pass_rejected_at_record_and_aggregate(self):
        generic_record = self.record()
        self.run["checks"][0]["kind"] = "recalculation"
        self.fp = gate.bytes_fingerprint(json.dumps(self.run).encode())
        with self.assertRaisesRegex(gate.ValidationError, "recalculation pass is unsupported"):
            self.record()
        generic_record["run_sha256"] = self.fp["sha256"]
        with self.assertRaisesRegex(gate.ValidationError, "recalculation pass is unsupported"):
            self.aggregate([generic_record])

    def test_recalculation_not_run_is_incomplete(self):
        self.run["checks"][0]["kind"] = "recalculation"
        self.fp = gate.bytes_fingerprint(json.dumps(self.run).encode())
        self.request.update(status="not_run", summary="No supervised calculation engine is supported.", evidence=[])
        self.assertEqual(self.aggregate([self.record()])["verdict"], "INCOMPLETE")

    def test_engine_claim_field_is_rejected(self):
        self.request["engine"] = "spreadsheet-engine"
        with self.assertRaises(gate.ValidationError):
            self.record()

    def test_checker_and_log_are_both_required(self):
        for roles in [[], [{"role": "checker", "path": "checker.py"}], [{"role": "log", "path": "result.log"}]]:
            request = {**self.request, "evidence": roles}
            with self.subTest(roles=roles), self.assertRaisesRegex(gate.ValidationError, "checker and log"):
                self.record(request)

    def test_duplicate_evidence_and_source_as_evidence_rejected(self):
        for evidence in [[{"role": "checker", "path": "result.log"}, {"role": "log", "path": "result.log"}], [{"role": "checker", "path": "artifact.csv"}, {"role": "log", "path": "result.log"}]]:
            with self.subTest(evidence=evidence), self.assertRaises(gate.ValidationError):
                self.record({**self.request, "evidence": evidence})

    def test_hardlinked_evidence_rejected(self):
        (self.root / "result.log").unlink()
        os.link(self.root / "checker.py", self.root / "result.log")
        with self.assertRaisesRegex(gate.ValidationError, "hard link"):
            self.record()

    def test_hardlinked_artifact_rejected(self):
        os.link(self.root / "artifact.csv", self.root / "alias.csv")
        self.spec["artifacts"].append({"id": "other", "path": "alias.csv"})
        with self.assertRaisesRegex(gate.ValidationError, "hard link"):
            gate.initialize(self.spec, self.root)

    def test_record_artifact_binding_must_match_required_snapshot(self):
        record = copy.deepcopy(self.record())
        record["artifacts"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(gate.ValidationError, "artifact binding"):
            self.aggregate([record])

    def test_hash_and_size_types_are_strict(self):
        for field, value in [("sha256", "F" * 64), ("sha256", None), ("size", True), ("size", -1), ("size", 1.0)]:
            record = copy.deepcopy(self.record())
            record["evidence"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(gate.ValidationError):
                self.aggregate([record])

    def test_assurance_cannot_claim_independent_execution(self):
        record = self.record()
        record["assurance"] = "independently_verified"
        with self.assertRaises(gate.ValidationError):
            self.aggregate([record])

    def test_traversal_absolute_backslash_dot_paths_rejected(self):
        for path in ["../artifact.csv", "/tmp/artifact.csv", "./artifact.csv", "a//artifact.csv", "a/../artifact.csv", "a\\artifact.csv", "C:/artifact.csv"]:
            spec = copy.deepcopy(self.spec)
            spec["artifacts"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(gate.ValidationError):
                gate.initialize(spec, self.root)

    def test_symlink_artifact_and_evidence_rejected(self):
        for name in ["artifact.csv", "result.log"]:
            target = self.root / name
            old = target.read_bytes()
            target.unlink()
            target.symlink_to(self.root / "support.txt")
            with self.subTest(name=name), self.assertRaisesRegex(gate.ValidationError, "symlink"):
                self.record()
            target.unlink()
            target.write_bytes(old)

    def test_duplicate_json_keys_nonfinite_invalid_encoding_rejected(self):
        for content in [b'{"a":1,"a":2}', b'{"x":{"a":1,"a":2}}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":', b'\xff']:
            path = self.root / "bad.json"
            path.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(gate.ValidationError):
                gate.load_json(path)

    def test_oversized_json_rejected(self):
        path = self.root / "oversize.json"
        path.write_bytes(b" " * (gate.MAX_JSON_BYTES + 1))
        with self.assertRaisesRegex(gate.ValidationError, "2 MiB"):
            gate.load_json(path)

    def test_output_does_not_overwrite_input_or_follow_symlinks(self):
        path = self.root / "artifact.csv"
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            gate.write_new(path, {"replace": True})
        link = self.root / "out.json"
        link.symlink_to(path)
        with self.assertRaises(gate.ValidationError):
            gate.write_new(link, {})
        self.assertEqual(path.read_bytes(), before)

    def test_cli_lifecycle_and_exit_status(self):
        spec, request, run, record, report = [self.root / f"{name}.json" for name in ["spec", "request", "run", "record", "report"]]
        spec.write_text(json.dumps(self.spec), encoding="utf-8")
        request.write_text(json.dumps(self.request), encoding="utf-8")
        original = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        base = [sys.executable, str(SCRIPT)]
        init_cmd = base + ["init", "--root", str(self.root), "--spec", str(spec), "--output", str(run)]
        self.assertEqual(subprocess.run(init_cmd, capture_output=True).returncode, 0)
        make = base + ["record", "--root", str(self.root), "--run", str(run), "--request", str(request), "--output", str(record)]
        self.assertEqual(subprocess.run(make, capture_output=True).returncode, 0)
        agg = base + ["aggregate", "--root", str(self.root), "--run", str(run), "--record", str(record), "--output", str(report)]
        self.assertEqual(subprocess.run(agg, capture_output=True).returncode, 0)
        self.assertEqual(json.loads(report.read_bytes())["verdict"], "ATTESTED")
        self.assertEqual(subprocess.run(agg, capture_output=True).returncode, 2)
        incomplete = base + ["aggregate", "--root", str(self.root), "--run", str(run), "--output", str(self.root / "missing.json")]
        self.assertEqual(subprocess.run(incomplete, capture_output=True).returncode, 3)
        self.assertTrue(all((self.root / name).read_bytes() == content for name, content in original.items()))

    def test_cli_stale_file_has_no_success_report(self):
        run_path = self.root / "run.json"
        gate.write_new(run_path, self.run)
        self.run, self.fp = gate.load_json(run_path)
        record_path = self.root / "record.json"
        gate.write_new(record_path, self.record())
        (self.root / "artifact.csv").write_text("changed", encoding="utf-8")
        output = self.root / "report.json"
        result = subprocess.run([sys.executable, str(SCRIPT), "aggregate", "--root", str(self.root), "--run", str(run_path), "--record", str(record_path), "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["verdict"], "INCOMPLETE")
        self.assertFalse(output.exists())

    def test_synthetic_demo_and_existing_directory_refusal(self):
        demo = SCRIPT.parent / "demo.py"
        output = self.root / "demo"
        command = [sys.executable, str(demo), "--output-dir", str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((output / "report.json").read_bytes())["verdict"], "ATTESTED")
        self.assertEqual(json.loads((output / "result.log").read_bytes())["data_row_count"], 3)
        before = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
        self.assertTrue(all((output / name).read_bytes() == content for name, content in before.items()))


if __name__ == "__main__":
    unittest.main()
