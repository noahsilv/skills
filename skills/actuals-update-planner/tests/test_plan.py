import copy
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


planner = module("actuals_planner", ROOT / "scripts/plan.py")
demo = module("actuals_demo", ROOT / "examples/make_demo.py")


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        self.mapping = demo.make_demo(self.inputs)
        self.model = self.inputs / "model.xlsx"
        self.mapfile = self.inputs / "mapping.json"
        self.source = self.inputs / "sources/synthetic-disclosure.txt"

    def save_map(self):
        self.mapfile.write_text(json.dumps(self.mapping))

    def run_plan(self):
        self.save_map()
        return planner.run(self.model, self.mapfile, self.source.parent, self.root / "out")

    def reject(self, message=None):
        self.save_map()
        if message:
            manager = self.assertRaisesRegex(planner.InputError, message)
        else:
            manager = self.assertRaises(planner.InputError)
        with manager:
            planner.run(self.model, self.mapfile, self.source.parent, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def edit_model(self, address, value):
        wb = load_workbook(self.model)
        wb["Forecast"][address] = value
        wb.save(self.model)
        wb.close()
        self.mapping["model_sha256"] = hashlib.sha256(self.model.read_bytes()).hexdigest()

    def cumulative(self):
        self.inputs = self.root / "quarter"
        self.mapping = demo.make_demo(self.inputs, "cumulative")
        self.model = self.inputs / "model.xlsx"
        self.mapfile = self.inputs / "mapping.json"
        self.source = self.inputs / "sources/synthetic-disclosure.txt"

    def test_annual_conversion_variances_and_typed_plan(self):
        originals = {p: p.read_bytes() for p in (self.model, self.source)}
        report = self.run_plan()
        self.assertEqual(report["status"], "PLAN_READY")
        self.assertEqual([v["actual"] for v in report["variances"]], ["1280.000", "-720.000", "185.000"])
        self.assertEqual([v["delta"] for v in report["variances"]], ["80.000", "-20.000", "15.000"])
        self.assertEqual(report["variances"][1]["variance_percent"], "-2.857143")
        self.assertEqual(report["proposed_model_edits"][0]["after"], "='FY2025 Sources'!F3")
        self.assertEqual(report["proposed_model_edits"][-1]["cell"], "C4")
        self.assertEqual(len(report["proposed_source_cells"]), 41)
        self.assertEqual(report["coverage"]["mapped_inputs"], 3)
        self.assertFalse(report["workbook_mutated"])
        self.assertFalse(report["recalculated"])
        for path, contents in originals.items():
            self.assertEqual(path.read_bytes(), contents)

    def test_formula_and_forecast_scopes_are_protected(self):
        report = self.run_plan()
        protected = {(f["sheet"], f["cell"]) for f in report["protected"]["formulas"]}
        edits = {(f["sheet"], f["cell"]) for f in report["proposed_model_edits"]}
        self.assertIn(("Forecast", "C7"), protected)
        self.assertIn(("Forecast", "D5"), protected)
        self.assertFalse(protected & edits)
        self.assertEqual({e["cell"] for e in report["proposed_model_edits"]}, {"C4", "C5", "C6", "C9"})
        self.assertEqual([f["column"] for f in report["protected"]["forecast_columns"]], ["D", "E"])

    def test_reader_never_calls_workbook_save(self):
        self.save_map()
        with patch("openpyxl.workbook.workbook.Workbook.save", side_effect=AssertionError("Unexpected workbook write")):
            report = planner.run(self.model, self.mapfile, self.source.parent, self.root / "out")
        self.assertEqual(report["status"], "PLAN_READY")

    def test_cumulative_flow_uses_contiguous_prior_periods_and_signed_costs(self):
        self.cumulative()
        report = self.run_plan()
        self.assertEqual([v["actual"] for v in report["variances"]], ["375.000", "-225.000", "70.000"])
        self.assertEqual(report["variances"][0]["prior_cells"], ["'Forecast'!B5"])
        self.assertEqual(report["variances"][0]["variance_percent"], "13.636364")
        self.assertTrue(any(c["cell"] == "E3" and c["value"] == "='Forecast'!B5" for c in report["proposed_source_cells"]))

    def test_zero_estimate_is_undefined_percentage(self):
        self.edit_model("C5", 0)
        self.mapping["mappings"][0]["expected_estimate"] = "0"
        row = self.run_plan()["variances"][0]
        self.assertIsNone(row["variance_percent"])
        self.assertEqual(row["percent_status"], "ZERO_ESTIMATE")
        self.assertEqual(row["delta"], "1280.000")

    def test_explicit_sign_conversion_from_positive_source_expense(self):
        self.source.write_text(self.source.read_text().replace("Cost of sales (720,000)", "Cost of sales 720,000"))
        self.mapping["sources"][0]["sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        cost = self.mapping["mappings"][1]
        cost.update(source_value="720000", reported_as="720,000", sign_multiplier=-1)
        cost["citation"]["excerpt"] = "Cost of sales 720,000"
        self.assertEqual(self.run_plan()["variances"][1]["actual"], "-720.000")

    def test_stale_model_digest_is_rejected(self):
        self.mapping["model_sha256"] = "0" * 64
        self.reject("Model hash")

    def test_stale_source_digest_is_rejected(self):
        self.source.write_text(self.source.read_text() + "changed")
        self.reject("Source hash")

    def test_wrong_physical_page_is_rejected(self):
        self.mapping["mappings"][0]["citation"]["page"] = 1
        self.reject("absent")

    def test_out_of_range_page_and_boolean_page_are_rejected(self):
        for page in (0, 3, True):
            with self.subTest(page=page):
                self.mapping["mappings"][0]["citation"]["page"] = page
                self.reject()

    def test_excerpt_and_label_must_be_present(self):
        self.mapping["mappings"][0]["citation"]["excerpt"] = "Revenue 9,999,999"
        self.reject("absent")
        self.mapping["mappings"][0]["citation"]["excerpt"] = "Revenue 1,280,000"
        self.mapping["mappings"][0]["source_label"] = "Other income"
        self.reject("label")

    def test_printed_number_must_be_whole_token_and_equal_declared_value(self):
        self.mapping["mappings"][0].update(reported_as="280", source_value="280")
        self.reject("complete number")
        self.mapping["mappings"][0].update(reported_as="1,280,000", source_value="1280001")
        self.reject("differs")

    def test_numeric_types_and_finiteness_are_strict(self):
        for value in (True, 1280000, 1280000.0, "NaN", "Infinity", "1e6", "0.0000000000001"):
            with self.subTest(value=value):
                self.mapping["mappings"][0]["source_value"] = value
                self.reject("decimal string")

    def test_number_from_another_source_row_cannot_be_assigned_to_label(self):
        item = self.mapping["mappings"][0]
        item.update(reported_as="(720,000)", source_value="-720000")
        item["citation"]["excerpt"] = "Revenue 1,280,000 Cost of sales (720,000)"
        self.reject("immediately follow")

    def test_standalone_stock_uses_period_end_without_subtracting_prior_stock(self):
        self.cumulative()
        stock = self.mapping["mappings"][0]
        stock.update(kind="stock", basis="standalone", prior_periods=[])
        report = self.run_plan()
        self.assertEqual(report["variances"][0]["actual"], "675.000")
        self.assertEqual(report["variances"][0]["prior_cells"], [])

    def test_source_currency_and_scope_must_match(self):
        self.mapping["sources"][0]["currency"] = "EUR"
        self.reject("FX")
        self.mapping["sources"][0]["currency"] = "USD"
        self.mapping["sources"][0]["scope"] = "standalone"
        self.reject("scope")

    def test_source_scale_cannot_match_substring_or_unrelated_date_digit(self):
        self.mapping["sources"][0]["scale"] = "1"
        self.reject("complete scale declaration")

    def test_target_scale_must_agree_with_literal_model_unit_label(self):
        self.mapping["target"]["scale"] = "1"
        self.reject("currency and scale")

    def test_formula_header_cannot_be_both_protected_and_proposed_edit(self):
        self.edit_model("C4", '="FY2025E"')
        self.mapping["target"]["expected_header"] = '="FY2025E"'
        self.reject("literal text")

    def test_formula_row_label_is_not_a_literal_mapping_label(self):
        self.edit_model("A5", '="Revenue"')
        self.mapping["mappings"][0]["label"] = '="Revenue"'
        self.reject("literal text")

    def test_context_and_audit_status_need_text_evidence(self):
        self.mapping["sources"][0]["audit_status"] = "unaudited"
        self.reject("Audit evidence")
        self.mapping["sources"][0]["audit_status"] = "audited"
        self.mapping["sources"][0]["context_evidence"]["excerpt"] = "currency USD"
        self.reject("context excerpt")

    def test_model_headers_labels_and_context_are_checked(self):
        for address, value in (("C4", "FY2024E"), ("A5", "Unrelated line"), ("B1", "Different entity"), ("D4", "Unknown period")):
            with self.subTest(address=address):
                wb = load_workbook(self.model)
                original = wb["Forecast"][address].value
                wb.close()
                self.edit_model(address, value)
                self.reject()
                self.edit_model(address, original)

    def test_formula_target_or_boolean_hardcode_is_protected(self):
        for value in ("=1+1", True, "1200"):
            with self.subTest(value=value):
                self.edit_model("C5", value)
                self.reject("numeric hardcode")

    def test_stale_estimate_is_rejected_even_with_current_hash(self):
        self.edit_model("C5", 1201)
        self.reject("snapshot")

    def test_unmapped_input_requires_explicit_exclusion(self):
        self.mapping["excluded_rows"] = []
        self.reject("Unmapped target hardcodes")

    def test_understated_worksheet_dimensions_cannot_hide_inputs_or_formulas(self):
        output = io.BytesIO()
        with zipfile.ZipFile(self.model) as original, zipfile.ZipFile(output, "w") as changed:
            for member in original.infolist():
                raw = original.read(member.filename)
                if member.filename == "xl/worksheets/sheet1.xml":
                    self.assertIn(b'A1:E9', raw)
                    raw = raw.replace(b'A1:E9', b'A1:E8')
                changed.writestr(member, raw)
        self.model.write_bytes(output.getvalue())
        self.mapping["model_sha256"] = hashlib.sha256(self.model.read_bytes()).hexdigest()
        self.mapping["mappings"] = self.mapping["mappings"][:2]
        self.reject("outside declared dimensions")

    def test_existing_source_sheet_is_rejected_case_insensitively(self):
        self.mapping["source_sheet"] = "forecast"
        self.reject("already exists")

    def test_duplicate_ids_rows_and_sources_are_rejected(self):
        original = copy.deepcopy(self.mapping)
        for change in (lambda m: m["mappings"][1].update(id=m["mappings"][0]["id"]),
                       lambda m: m["mappings"][1].update(row=m["mappings"][0]["row"]),
                       lambda m: m["sources"].append(copy.deepcopy(m["sources"][0]))):
            self.mapping = copy.deepcopy(original)
            change(self.mapping)
            self.reject("duplicate")

    def test_empty_mapping_unknown_keys_and_duplicate_json_keys(self):
        original = copy.deepcopy(self.mapping)
        self.mapping["mappings"] = []
        self.reject()
        self.mapping = original
        self.mapping["mappings"][0]["arbitrary_conversion_factor"] = "1000"
        self.reject("exactly")
        for raw in ('{"a":1,"a":2}', '{"value":NaN}', '{"target":{"column":"C","column":"D"}}'):
            with self.subTest(raw=raw), self.assertRaises(planner.InputError):
                planner.loads(raw)

    def test_unknown_source_id_is_rejected(self):
        self.mapping["mappings"][0]["source_id"] = "missing"
        self.reject("Unknown source")

    def test_cumulative_partition_cannot_have_gap_overlap_or_repeat(self):
        self.cumulative()
        original = copy.deepcopy(self.mapping)
        for begin, end in (("2025-01-02", "2025-03-31"), ("2025-01-01", "2025-03-30"), ("2025-01-01", "2025-04-01")):
            self.mapping = copy.deepcopy(original)
            self.mapping["mappings"][0]["prior_periods"][0]["period"] = {"start": begin, "end": end}
            self.reject()
        self.mapping = original
        self.mapping["mappings"][0]["prior_periods"].append(copy.deepcopy(self.mapping["mappings"][0]["prior_periods"][0]))
        self.reject("duplicate")

    def test_cumulative_stock_and_formula_prior_are_rejected(self):
        self.cumulative()
        self.mapping["mappings"][0]["kind"] = "stock"
        self.reject("additive flow")
        self.mapping["mappings"][0]["kind"] = "flow"
        self.edit_model("B5", "=100*3")
        self.reject("numeric hardcode")

    def test_standalone_flow_requires_matching_coverage(self):
        self.mapping["target"]["period"]["start"] = "2025-04-01"
        self.reject("exact target coverage")

    def test_source_path_traversal_and_symlink_are_rejected(self):
        self.mapping["sources"][0]["file"] = "../synthetic-disclosure.txt"
        self.reject("basename")
        self.mapping["sources"][0]["file"] = "linked.txt"
        (self.source.parent / "linked.txt").symlink_to(self.source)
        self.reject("regular files")

    def test_input_change_before_delivery_prevents_output(self):
        self.save_map()
        real_build = planner.build_plan
        def changing(*args):
            result = real_build(*args)
            self.source.write_text(self.source.read_text() + " changed")
            return result
        with patch.object(planner, "build_plan", side_effect=changing), self.assertRaisesRegex(planner.InputError, "changed while planning"):
            planner.run(self.model, self.mapfile, self.source.parent, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_existing_output_or_model_destination_is_not_overwritten(self):
        self.run_plan()
        original = (self.root / "out/plan.json").read_bytes()
        with self.assertRaises(planner.InputError):
            planner.run(self.model, self.mapfile, self.source.parent, self.root / "out")
        self.assertEqual((self.root / "out/plan.json").read_bytes(), original)
        model_original = self.model.read_bytes()
        with self.assertRaises(planner.InputError):
            planner.run(self.model, self.mapfile, self.source.parent, self.model)
        self.assertEqual(self.model.read_bytes(), model_original)

    def test_documented_generator_and_planner_cli_cases(self):
        for case in ("annual", "cumulative"):
            inputs, out = self.root / f"cli-{case}", self.root / f"cli-{case}-plan"
            make = subprocess.run([sys.executable, str(ROOT / "examples/make_demo.py"), "--out", str(inputs), "--case", case], capture_output=True, text=True)
            self.assertEqual(make.returncode, 0, make.stderr)
            result = subprocess.run([sys.executable, str(ROOT / "scripts/plan.py"), str(inputs / "model.xlsx"), "--mapping", str(inputs / "mapping.json"), "--sources", str(inputs / "sources"), "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("No workbook was changed or recalculated", (out / "plan.md").read_text())
            self.assertEqual(json.loads((out / "plan.json").read_text())["status"], "PLAN_READY")

    def test_excessive_json_nesting_and_integer_have_controlled_cli_exit(self):
        for name, raw in (("deep", "[" * 1200 + "0" + "]" * 1200),
                          ("integer", '{"schema_version":' + "9" * 5000 + "}")):
            self.mapfile.write_text(raw)
            out = self.root / name
            result = subprocess.run([sys.executable, str(ROOT / "scripts/plan.py"), str(self.model), "--mapping", str(self.mapfile), "--sources", str(self.source.parent), "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("REJECTED: Invalid UTF-8 JSON", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
