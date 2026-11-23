"""Regression tests for private terms in public source and skill archives."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import check_publication as scan


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.list = self.folder / "review.txt"
        self.list.write_text("Example Restricted\n", encoding="utf-8")
        self.terms = scan.load_terms(self.list)

    def test_case_and_unicode_forms(self):
        self.assertTrue(scan.matches("Ｅxample RESTRICTED", self.terms))
        self.assertFalse(scan.matches("ordinary financing example", self.terms))

    def test_literal_punctuation_and_matching_path(self):
        path = self.folder / "notes.md"
        path.write_text("ordinary financing example", encoding="utf-8")
        self.assertTrue(scan.contains_term(path, "Example Restricted/notes.md", self.terms))
        self.assertFalse(scan.matches("dealx123", {"deal.123"}))

    def test_archive_members_and_comments(self):
        path = self.folder / "fixture.skill"
        for name, content, comment in (("SKILL.md", "example restricted", b""),
                                       ("Example Restricted.md", "clear", b""),
                                       ("SKILL.md", "clear", b"Example Restricted")):
            with self.subTest(name=name, content=content, comment=comment):
                with ZipFile(path, "w") as archive:
                    archive.writestr(name, content)
                    archive.comment = comment
                self.assertTrue(scan.contains_term(path, path.name, self.terms))

    def test_configuration_errors(self):
        with patch.object(scan, "ROOT", self.folder):
            with self.assertRaises(ValueError):
                scan.load_terms(self.list)
        self.list.write_text("  \n", encoding="utf-8")
        with self.assertRaises(ValueError):
            scan.load_terms(self.list)

    def test_cli_counts_without_printing_terms_or_sensitive_names(self):
        checkout = self.folder / "published"
        checkout.mkdir()
        path = checkout / "Example Restricted.md"
        path.write_text("example restricted", encoding="utf-8")
        output = io.StringIO()
        with patch.object(scan, "ROOT", checkout), patch.object(scan, "source_files", return_value=[path]), \
                patch("sys.argv", ["check_publication", "--terms", str(self.list)]), \
                contextlib.redirect_stdout(output):
            self.assertEqual(scan.main(), 1)
        self.assertNotIn("restricted", output.getvalue().lower())
        self.assertIn("content: 1", output.getvalue())

    def test_cli_distinguishes_clear_files_and_an_unreadable_list(self):
        checkout = self.folder / "published"
        checkout.mkdir()
        path = checkout / "case.md"
        path.write_text("public financing example", encoding="utf-8")
        with patch.object(scan, "ROOT", checkout), patch.object(scan, "source_files", return_value=[path]):
            with patch("sys.argv", ["check_publication", "--terms", str(self.list)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(scan.main(), 0)
            error = io.StringIO()
            with patch("sys.argv", ["check_publication", "--terms", str(self.folder / "private-name")]), \
                    contextlib.redirect_stderr(error):
                self.assertEqual(scan.main(), 2)
            self.assertNotIn("private-name", error.getvalue())


if __name__ == "__main__":
    unittest.main()
