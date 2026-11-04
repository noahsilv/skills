import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("statement_analysis", ROOT / "scripts/analyze.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class StatementAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/complete.json").read_text())

    def values(self):
        return self.data["periods"][0]["values"]

    def result(self):
        return analysis.analyze(self.data)

    def check(self, name):
        return next(c for c in self.result()["periods"][0]["checks"] if c["id"] == name)

    def metric(self, name):
        return next(m for m in self.result()["periods"][0]["metrics"] if m["id"] == name)

    def test_complete_accounting_and_metrics_with_lineage(self):
        report = self.result()
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual({c["status"] for c in report["periods"][0]["checks"]}, {"PASS"})
        self.assertEqual(self.metric("gross_margin")["value"], "0.437500")
        self.assertEqual(self.metric("net_debt")["value"], "300")
        self.assertEqual(self.metric("current_ratio")["value"], "2.083333")
        self.assertEqual(len(self.metric("gross_debt")["sources"]), 4)
        self.assertEqual(report["periods"][0]["coverage"]["reported"], 26)

    def test_linked_synthetic_document_has_declared_digest(self):
        source = ROOT / "examples/synthetic-disclosure.txt"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), self.data["sources"][0]["sha256"])
        self.assertIn("Revenue 1,280,000", source.read_text())
        self.assertIn("Cost of sales (720,000)", source.read_text())

    def test_discrepancy_retains_other_check_results(self):
        self.values()["total_assets"]["value"] = "1301"
        report = self.result()
        self.assertEqual(report["status"], "DISCREPANCY")
        self.assertEqual(self.check("balance_sheet")["residual"], "1")
        self.assertEqual(self.check("cash_rollforward")["status"], "PASS")

    def test_missing_null_and_absent_are_distinct_from_zero(self):
        self.assertEqual(self.check("cash_rollforward")["status"], "PASS")
        self.values()["fx_cash_movement"].update(value=None, note="Unknown FX movement")
        report = self.result()
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIn("fx_cash_movement", report["periods"][0]["coverage"]["explicit_missing"])
        self.assertEqual(self.check("cash_rollforward")["status"], "UNKNOWN")
        del self.values()["fx_cash_movement"]
        self.assertIn("fx_cash_movement", self.result()["periods"][0]["coverage"]["absent"])

    def test_missing_lease_does_not_become_zero_debt(self):
        self.values()["leases_noncurrent"].update(value=None, note="Lease note unavailable")
        debt = self.metric("gross_debt")
        self.assertEqual(debt["status"], "UNKNOWN")
        self.assertIsNone(debt["value"])
        self.assertEqual(debt["missing"], ["leases_noncurrent"])

    def test_zero_denominator_is_undefined_not_a_pass(self):
        self.values()["current_liabilities"]["value"] = "0"
        self.assertEqual(self.metric("current_ratio")["status"], "UNDEFINED")
        self.assertIsNone(self.metric("current_ratio")["value"])
        self.assertEqual(self.result()["status"], "INCOMPLETE")

    def test_negative_equity_is_retained_but_ratio_not_interpreted(self):
        self.values()["total_equity"]["value"] = "-10"
        self.assertEqual(self.metric("debt_to_equity")["status"], "UNDEFINED")
        self.assertEqual(self.result()["status"], "DISCREPANCY")

    def test_zero_and_negative_numerators_are_calculated(self):
        self.values()["net_income"]["value"] = "0"
        self.assertEqual(self.metric("net_margin")["value"], "0.000000")
        self.values()["net_income"]["value"] = "-128"
        self.assertEqual(self.metric("net_margin")["value"], "-0.100000")

    def test_decimal_identity_is_exact(self):
        for field, value in (("total_assets", "0.3"), ("total_liabilities", "0.1"), ("total_equity", "0.2")):
            self.values()[field]["value"] = value
        self.assertEqual(self.check("balance_sheet")["status"], "PASS")
        self.assertEqual(self.check("balance_sheet")["residual"], "0.0")

    def test_tolerance_boundary_and_no_automatic_plug(self):
        self.data["reconciliation_tolerance"] = "0.1"
        self.data["tolerance_reason"] = "Illustrative rounding allowance"
        self.values()["total_assets"]["value"] = "1300.1"
        self.assertEqual(self.check("balance_sheet")["status"], "PASS")
        self.values()["total_assets"]["value"] = "1300.100000000001"
        self.assertEqual(self.check("balance_sheet")["status"], "FAIL")
        self.assertEqual(self.values()["total_assets"]["value"], "1300.100000000001")

    def test_invalid_numeric_types_are_rejected(self):
        for invalid in (True, 1280, 1280.0, "NaN", "Infinity", "1e3", "01", "0.0000000000001", "9" * 25):
            with self.subTest(value=invalid):
                data = copy.deepcopy(self.data)
                data["periods"][0]["values"]["revenue"]["value"] = invalid
                with self.assertRaises(analysis.InputError):
                    analysis.analyze(data)

    def test_duplicate_json_keys_and_nonstandard_constants(self):
        for raw in ('{"x":1,"x":2}', '{"x":{"value":1,"value":2}}', '{"x":NaN}', '{"x":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(analysis.InputError):
                analysis.loads(raw)

    def test_unknown_fields_types_and_empty_scope(self):
        variants = []
        for field, value in (("schema_version", True), ("currency", "usd"), ("scale", 1000), ("reconciliation_tolerance", "-1"), ("sources", []), ("periods", [])):
            data = copy.deepcopy(self.data)
            data[field] = value
            variants.append(data)
        extra = copy.deepcopy(self.data)
        extra["assumed_ebitda"] = "100"
        variants.append(extra)
        for data in variants:
            with self.subTest(data=list(data)), self.assertRaises(analysis.InputError):
                analysis.analyze(data)

    def test_missing_number_requires_note_and_present_number_requires_source(self):
        self.values()["revenue"].update(value=None, note="")
        with self.assertRaises(analysis.InputError):
            self.result()
        self.values()["revenue"].update(value="1280", note="", sources=[])
        with self.assertRaises(analysis.InputError):
            self.result()

    def test_unknown_and_duplicate_source_references(self):
        ref = self.values()["revenue"]["sources"][0]
        ref["source_id"] = "unknown"
        with self.assertRaises(analysis.InputError):
            self.result()
        ref["source_id"] = "disclosure"
        self.values()["revenue"]["sources"].append(copy.deepcopy(ref))
        with self.assertRaises(analysis.InputError):
            self.result()

    def test_duplicate_source_id_and_period_vintages(self):
        self.data["sources"].append(copy.deepcopy(self.data["sources"][0]))
        with self.assertRaises(analysis.InputError):
            self.result()
        self.data["sources"].pop()
        self.data["periods"].append(copy.deepcopy(self.data["periods"][0]))
        self.data["periods"][1].update(id="restated", basis="restated")
        with self.assertRaisesRegex(analysis.InputError, "Duplicate period coverage"):
            self.result()

    def test_duplicate_period_id_with_different_dates(self):
        previous = copy.deepcopy(self.data["periods"][0])
        previous.update(start="2024-01-01", end="2024-12-31")
        self.data["periods"].append(previous)
        with self.assertRaisesRegex(analysis.InputError, "duplicate id"):
            self.result()

    def test_invalid_and_interim_dates(self):
        for start, end in (("2025-02-30", "2025-12-31"), ("2025-12-31", "2025-01-01"), ("2025-01-01", "2025-06-30")):
            data = copy.deepcopy(self.data)
            data["periods"][0].update(start=start, end=end)
            with self.subTest(start=start, end=end), self.assertRaises(analysis.InputError):
                analysis.analyze(data)
        self.data["periods"][0].update(end="2025-06-30", kind="interim")
        self.assertEqual(self.metric("gross_margin")["value"], "0.437500")
        self.assertEqual(self.result()["periods"][0]["kind"], "interim")

    def test_expense_sign_is_not_silently_changed(self):
        self.values()["cost_of_sales"]["value"] = "-720"
        with self.assertRaisesRegex(analysis.InputError, "sign convention"):
            self.result()

    def test_read_only_hash_and_output_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            source = td / "input.json"
            source.write_text(json.dumps(self.data))
            original = source.read_bytes()
            report = analysis.run(source, td / "out")
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(report["input"]["sha256"], hashlib.sha256(original).hexdigest())
            expected = (td / "out/report.json").read_bytes()
            with self.assertRaises(analysis.InputError):
                analysis.run(source, td / "out")
            self.assertEqual((td / "out/report.json").read_bytes(), expected)
            with self.assertRaises(analysis.InputError):
                analysis.run(source, source)

    def test_changed_input_prevents_delivery(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            source = td / "input.json"
            source.write_text(json.dumps(self.data))
            original_analyze = analysis.analyze
            def changed(data):
                report = original_analyze(data)
                source.write_text("{}")
                return report
            with patch.object(analysis, "analyze", side_effect=changed), self.assertRaisesRegex(analysis.InputError, "changed"):
                analysis.run(source, td / "out")
            self.assertFalse((td / "out").exists())

    def test_documented_cli_cases_and_readable_status(self):
        with tempfile.TemporaryDirectory() as td:
            for name, expected, status in (("complete", 0, "COMPLETE"), ("incomplete", 2, "INCOMPLETE"), ("discrepancy", 1, "DISCREPANCY")):
                output = Path(td) / name
                result = subprocess.run([sys.executable, str(ROOT / "scripts/analyze.py"), str(ROOT / f"examples/{name}.json"), "--out", str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(json.loads((output / "report.json").read_text())["status"], status)
                self.assertIn(status, (output / "report.md").read_text())

    def test_excessive_json_nesting_and_integer_have_controlled_cli_exit(self):
        with tempfile.TemporaryDirectory() as td:
            for name, raw in (("deep", "[" * 1200 + "0" + "]" * 1200),
                              ("integer", '{"schema_version":' + "9" * 5000 + "}")):
                source, out = Path(td) / f"{name}.json", Path(td) / f"{name}-out"
                source.write_text(raw)
                result = subprocess.run([sys.executable, str(ROOT / "scripts/analyze.py"), str(source), "--out", str(out)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("ERROR: Invalid UTF-8 JSON", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
