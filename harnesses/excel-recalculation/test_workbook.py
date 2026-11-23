import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from openpyxl import load_workbook
from workbook import prepare, verify


class WorkbookTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "case.xlsx"
        prepare(self.path, "baseline")

    def test_fresh_workbook_cannot_pass(self):
        check = verify(self.path, "baseline")
        self.assertEqual(check["status"], "INCOMPLETE")
        self.assertEqual(len(check["missing_caches"]), 22)

    def test_existing_input_preserved(self):
        original = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            prepare(self.path, "challenge")
        self.assertEqual(original, self.path.read_bytes())

    def test_challenge_changes_exactly_one_input(self):
        challenge = self.path.with_name("challenge.xlsx")
        prepare(challenge, "challenge")
        baseline, revised = load_workbook(self.path), load_workbook(challenge)
        self.addCleanup(baseline.close)
        self.addCleanup(revised.close)
        changes = [(ws.title, c.coordinate, c.value, revised[ws.title][c.coordinate].value)
                   for ws in baseline for row in ws for c in row
                   if c.value != revised[ws.title][c.coordinate].value]
        self.assertEqual(changes, [("Inputs", "C17", 100, 110)])
        with self.assertRaisesRegex(ValueError, "named fixture"):
            verify(self.path, "challenge")

    def test_pasted_amount_is_not_a_formula(self):
        model = load_workbook(self.path)
        model["Bridge"]["C11"] = 402
        model.save(self.path)
        model.close()
        with self.assertRaisesRegex(ValueError, "formulas differ"):
            verify(self.path, "baseline")

    def test_wrong_cached_value_is_detected_with_formula_intact(self):
        # Alter one OOXML cache by hand to emulate a stale saved result.
        stale = self.path.with_name("stale.xlsx")
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        with ZipFile(self.path) as old, ZipFile(stale, "w") as new:
            for member in old.infolist():
                content = old.read(member)
                if member.filename == "xl/worksheets/sheet2.xml":
                    xml = ET.fromstring(content)
                    cell = xml.find(f".//{ns}c[@r='C11']")
                    ET.SubElement(cell, ns + "v").text = "401"
                    content = ET.tostring(xml)
                new.writestr(member, content)
        with self.assertRaisesRegex(ValueError, "at C11"):
            verify(stale, "baseline")


if __name__ == "__main__":
    unittest.main()
