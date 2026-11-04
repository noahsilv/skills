import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import subprocess
import sys
import xml.etree.ElementTree as ET

from openpyxl import Workbook

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "tieout.py"
spec = importlib.util.spec_from_file_location("public_tieout", MODULE)
tieout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tieout)


def mapping():
    return {"schema_version": 1, "pairs": [{
        "id": "revenue", "comparison_unit": "USD thousands",
        "left": {"sheet": "Model", "cell": "B2", "unit": "USD thousands", "period": "FY2025"},
        "right": {"sheet": "Source", "cell": "D4", "unit": "USD thousands", "period": "FY2025"},
    }]}


class TieoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.left = Path(self.temp.name) / "model.xlsx"
        self.right = Path(self.temp.name) / "source.xlsx"
        self.write(self.left, "Model", "B2", 1250)
        self.write(self.right, "Source", "D4", 1250)

    def write(self, path, sheet, cell, value):
        wb = Workbook()
        wb.active.title = sheet
        wb.active[cell] = value
        wb.save(path)
        wb.close()

    def run_check(self, config=None, cached=False):
        return tieout.tieout(self.left, self.right, config or mapping(), cached)

    def test_match_and_input_preservation(self):
        before = [tieout.sha256(p) for p in (self.left, self.right)]
        result = self.run_check()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["compared_pairs"], 1)
        self.assertEqual(before, [tieout.sha256(p) for p in (self.left, self.right)])

    def test_mismatch_has_signed_delta(self):
        self.write(self.left, "Model", "B2", 1260)
        result = self.run_check()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["results"][0]["delta"], "10")

    def test_explicit_unit_conversion(self):
        self.write(self.left, "Model", "B2", 1.25)
        config = mapping()
        config["pairs"][0]["left"].update(unit="USD millions", multiplier=1000)
        self.assertEqual(self.run_check(config)["status"], "PASS")
        del config["pairs"][0]["left"]["multiplier"]
        with self.assertRaises(tieout.ContractError):
            self.run_check(config)

    def test_period_mismatch_is_rejected(self):
        config = mapping()
        config["pairs"][0]["right"]["period"] = "H1 2025"
        with self.assertRaises(tieout.ContractError):
            self.run_check(config)

    def test_blank_is_not_zero_or_a_pass(self):
        self.write(self.left, "Model", "B2", None)
        self.write(self.right, "Source", "D4", 0)
        self.assertEqual(self.run_check()["status"], "INCOMPLETE")
        self.write(self.right, "Source", "D4", None)
        self.assertEqual(self.run_check()["compared_pairs"], 0)

    def test_boolean_does_not_equal_one(self):
        self.write(self.left, "Model", "B2", True)
        self.write(self.right, "Source", "D4", 1)
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_text_does_not_equal_number(self):
        self.write(self.left, "Model", "B2", "1250")
        self.assertEqual(self.run_check()["status"], "FAIL")

    def test_missing_sheet_and_error_value_are_incomplete(self):
        config = mapping()
        config["pairs"][0]["left"]["sheet"] = "Absent"
        self.assertEqual(self.run_check(config)["status"], "INCOMPLETE")
        self.write(self.left, "Model", "B2", "#DIV/0!")
        self.assertEqual(self.run_check()["status"], "INCOMPLETE")

    def test_missing_formula_cache_never_passes(self):
        self.write(self.left, "Model", "B2", "=1250")
        self.assertEqual(self.run_check()["status"], "INCOMPLETE")
        self.assertEqual(self.run_check(cached=True)["status"], "INCOMPLETE")
        self.assertEqual(self.run_check()["calculation"], "formula_values_incomplete")
        self.assertEqual(self.run_check(cached=True)["calculation"], "formula_values_incomplete")

    def test_formula_cache_requires_review(self):
        self.write(self.left, "Model", "B2", "=1250")
        # Inject a known synthetic cache; this does not assert recalculation.
        with zipfile.ZipFile(self.left) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        key = "xl/worksheets/sheet1.xml"
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        root = ET.fromstring(parts[key])
        cached = root.find(f".//{namespace}c[@r='B2']/{namespace}v")
        self.assertIsNotNone(cached)
        cached.text = "1250"
        parts[key] = ET.tostring(root)
        with zipfile.ZipFile(self.left, "w") as archive:
            for name, content in parts.items():
                archive.writestr(name, content)
        self.assertEqual(self.run_check()["status"], "INCOMPLETE")
        result = self.run_check(cached=True)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["calculation"], "saved_formula_caches_unverified")

    def test_empty_duplicate_and_unknown_fields_rejected(self):
        configs = [{"schema_version": 1, "pairs": []}]
        duplicate = mapping()
        duplicate["pairs"].append(copy.deepcopy(duplicate["pairs"][0]))
        configs.append(duplicate)
        unknown = mapping()
        unknown["pairs"][0]["tolerence"] = 2
        configs.append(unknown)
        duplicate_endpoint = mapping()
        second = copy.deepcopy(duplicate_endpoint["pairs"][0])
        second["id"] = "another"
        duplicate_endpoint["pairs"].append(second)
        configs.append(duplicate_endpoint)
        for config in configs:
            with self.subTest(config=config), self.assertRaises(tieout.ContractError):
                self.run_check(config)

    def test_invalid_tolerances_rejected(self):
        for value in [True, -1, float("nan"), float("inf"), "0.1"]:
            config = mapping()
            config["pairs"][0]["absolute_tolerance"] = value
            with self.subTest(value=value), self.assertRaises(tieout.ContractError):
                self.run_check(config)

    def test_absolute_and_relative_tolerance_boundary(self):
        self.write(self.left, "Model", "B2", 1251)
        config = mapping()
        config["pairs"][0]["absolute_tolerance"] = 1
        self.assertEqual(self.run_check(config)["status"], "PASS")
        config["pairs"][0]["absolute_tolerance"] = 0.99
        self.assertEqual(self.run_check(config)["status"], "FAIL")
        config["pairs"][0]["relative_tolerance"] = 0.001
        self.assertEqual(self.run_check(config)["status"], "PASS")

    def test_strict_json_parser(self):
        path = Path(self.temp.name) / "bad.json"
        for content in ['{"x": 1, "x": 2}', '{"x": NaN}']:
            path.write_text(content)
            with self.assertRaises(tieout.ContractError):
                tieout.load_json(path)

    def test_cli_invalid_workbook_returns_incomplete(self):
        self.left.write_bytes(b"not an XLSX file")
        config = Path(self.temp.name) / "mapping.json"
        config.write_text(json.dumps(mapping()))
        result = subprocess.run([sys.executable, str(MODULE), str(self.left), str(self.right),
                                 "--mapping", str(config)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["status"], "INCOMPLETE")
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_decimal_multiplier_is_not_rounded(self):
        self.write(self.left, "Model", "B2", 1)
        self.write(self.right, "Source", "D4", 1)
        config = mapping()
        config["pairs"][0]["right"]["multiplier"] = "DECIMAL_LITERAL"
        path = Path(self.temp.name) / "mapping.json"
        path.write_text(json.dumps(config).replace('"DECIMAL_LITERAL"', "1.0000000000000000000000000001"))
        run = subprocess.run([sys.executable, str(MODULE), str(self.left), str(self.right),
                              "--mapping", str(path)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report["results"][0]["delta"], "-1E-28")

    def test_numeric_resource_bound_is_explicit(self):
        from decimal import Decimal
        config = mapping()
        config["pairs"][0]["left"]["multiplier"] = Decimal("1e1001")
        with self.assertRaisesRegex(tieout.ContractError, "numeric bound"):
            self.run_check(config)


if __name__ == "__main__":
    unittest.main()
