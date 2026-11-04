import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workbook = self.root / "model.xlsx"
        self.watch = self.root / "watch.json"
        self.output = self.root / "snapshot.json"
        self.watch.write_text(json.dumps({"schema_version": 1, "items": [
            {"id": "cash", "sheet": "Model", "cell": "B2", "unit": "USD thousands", "period": "FY2025"}]}))

    def write(self, value):
        workbook = Workbook()
        workbook.active.title = "Model"
        workbook.active["B2"] = value
        workbook.save(self.workbook)
        workbook.close()

    def run_export(self, *extra):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "export_workbook.py"), str(self.workbook),
                               "--watch", str(self.watch), "--label", "Synthetic state", "--out", str(self.output), *extra], capture_output=True, text=True)

    def test_literal_export_preserves_types_and_source(self):
        self.write(True)
        original = self.workbook.read_bytes()
        result = self.run_export()
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads(self.output.read_text())
        self.assertIs(state["items"][0]["value"], True)
        self.assertEqual(state["value_basis"], "literal")
        self.assertEqual(self.workbook.read_bytes(), original)
        self.assertEqual(self.run_export().returncode, 2)

    def test_missing_formula_cache_fails_with_and_without_flag(self):
        self.write("=1+1")
        self.assertEqual(self.run_export().returncode, 2)
        self.assertEqual(self.run_export("--allow-cached-values").returncode, 2)
        self.assertFalse(self.output.exists())

    def test_empty_cell_is_not_exported_as_zero(self):
        self.write(None)
        self.assertEqual(self.run_export().returncode, 2)
        self.assertFalse(self.output.exists())

    def test_invalid_workbook_returns_incomplete(self):
        self.workbook.write_bytes(b"not an XLSX file")
        result = self.run_export()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["status"], "INCOMPLETE")
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
