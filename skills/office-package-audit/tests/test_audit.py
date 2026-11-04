"""Synthetic behavior and failure-path tests, with no source Office assets."""

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


audit = load("package_audit", ROOT / "scripts/audit.py")
example = load("package_examples", ROOT / "examples/make_examples.py")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def run_parts(self, parts=None, extension="docx", limits=None):
        path = self.folder / ("sample." + extension)
        example.write_package(path, parts if parts is not None else example.package_parts())
        before = path.read_bytes()
        result = audit.inspect_file(path, limits)
        self.assertEqual(path.read_bytes(), before, "Inspection must not modify input")
        self.assertEqual(result["sha256"], hashlib.sha256(before).hexdigest())
        return result

    def codes(self, result):
        return {f["code"] for f in result["findings"]}

    def test_minimal_packages_pass(self):
        for kind, ext in [("word", "docx"), ("excel", "xlsx"), ("powerpoint", "pptx")]:
            with self.subTest(kind=kind):
                result = self.run_parts(example.package_parts(kind), ext)
                self.assertEqual(result["exit_code"], 0, result)
                self.assertTrue(result["coverage"]["archive_preflight_passed"])

    def test_missing_main_relationship_fails(self):
        parts = example.package_parts()
        del parts["_rels/.rels"]
        self.assertIn("missing-office-main-part", self.codes(self.run_parts(parts)))

    def test_wrong_main_type_fails(self):
        parts = example.package_parts()
        parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace("wordprocessingml.document.main+xml", "wordprocessingml.template.main+xml")
        self.assertIn("main-content-type-mismatch", self.codes(self.run_parts(parts)))

    def test_extension_and_document_family_must_agree(self):
        result = self.run_parts(example.package_parts("excel"))
        self.assertIn("main-part-format-mismatch", self.codes(result))

    def test_external_target_is_flagged_without_exposing_value(self):
        parts = example.package_parts()
        parts["word/_rels/document.xml.rels"] = f'<Relationships xmlns="{example.REL}"><Relationship Id="rId2" Type="{example.R}/hyperlink" Target="https://example.invalid/SECRET_VALUE" TargetMode="External"/></Relationships>'
        result = self.run_parts(parts)
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("external-relationship", self.codes(result))
        self.assertNotIn("SECRET_VALUE", json.dumps(result))

    def test_properties_and_custom_data_redact_values(self):
        parts = example.package_parts()
        parts["docProps/custom.xml"] = '<properties><item>SECRET_VALUE</item></properties>'
        parts["customXml/item1.xml"] = '<item>SECRET_VALUE</item>'
        result = self.run_parts(parts)
        self.assertTrue({"document-properties", "custom-xml"} <= self.codes(result))
        self.assertNotIn("SECRET_VALUE", json.dumps(result))

    def test_word_revisions_comments_and_hidden_text(self):
        parts = example.package_parts()
        parts["word/document.xml"] = f'<w:document xmlns:w="{example.W}"><w:body><w:p><w:del><w:r><w:delText>SECRET_VALUE</w:delText></w:r></w:del><w:r><w:rPr><w:vanish/></w:rPr><w:t>SECRET_VALUE</w:t></w:r></w:p></w:body></w:document>'
        parts["word/comments.xml"] = f'<w:comments xmlns:w="{example.W}"><w:comment w:id="0"><w:p>SECRET_VALUE</w:p></w:comment></w:comments>'
        result = self.run_parts(parts)
        self.assertTrue({"tracked-changes", "comments-part", "hidden-text-property"} <= self.codes(result))
        self.assertNotIn("SECRET_VALUE", json.dumps(result))

    def test_hidden_rows_columns_and_sheets(self):
        parts = example.package_parts("excel")
        parts["xl/workbook.xml"] = parts["xl/workbook.xml"].replace('name="Example"', 'name="Example" state="veryHidden"')
        parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace('<sheetData>', '<cols><col min="1" max="1" hidden="1"/></cols><sheetData>').replace('<row r="1">', '<row r="1" hidden="1">')
        result = self.run_parts(parts, "xlsx")
        findings = [f for f in result["findings"] if f["code"] == "hidden-workbook-items"]
        self.assertEqual(sum(f["count"] for f in findings), 3)

    def test_notes_and_embedded_content_need_review(self):
        parts = example.package_parts("powerpoint")
        parts["ppt/notesSlides/notesSlide1.xml"] = f'<p:notes xmlns:p="{example.P}"><p:cSld/></p:notes>'
        parts["ppt/embeddings/item.bin"] = b"Synthetic embedded content"
        parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace("</Types>", '<Default Extension="bin" ContentType="application/octet-stream"/></Types>')
        result = self.run_parts(parts, "pptx")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("speaker-notes", self.codes(result))
        self.assertIn("ppt/embeddings/item.bin", result["coverage"]["uninspected_parts"])

    def test_missing_relationship_target_fails(self):
        parts = example.package_parts()
        parts["_rels/.rels"] = parts["_rels/.rels"].replace('Target="word/document.xml"', 'Target="word/missing.xml"')
        self.assertIn("missing-relationship-target", self.codes(self.run_parts(parts)))

    def test_duplicate_relationship_ids_fail(self):
        parts = example.package_parts()
        parts["_rels/.rels"] = parts["_rels/.rels"].replace('</Relationships>', f'<Relationship Id="rId1" Type="{example.R}/styles" Target="word/document.xml"/></Relationships>')
        self.assertIn("duplicate-relationship-id", self.codes(self.run_parts(parts)))

    def test_relationship_traversal_above_root_fails(self):
        parts = example.package_parts()
        parts["_rels/.rels"] = parts["_rels/.rels"].replace('Target="word/document.xml"', 'Target="../outside.xml"')
        self.assertIn("invalid-internal-target", self.codes(self.run_parts(parts)))

    def test_valid_parent_relative_relationship(self):
        self.assertEqual(audit.target_part("word/document.xml", "../media/image.png"), "media/image.png")
        self.assertEqual(audit.target_part("word/document.xml", "/word/styles.xml"), "word/styles.xml")
        self.assertEqual(audit.target_part("word/document.xml", "media/file%20name.xml"), "word/media/file name.xml")

    def test_unsafe_member_path_stops_before_parsing(self):
        for name in ["../outside.xml", "/absolute.xml", "C:/file.xml", "word\\file.xml"]:
            with self.subTest(name=name):
                parts = example.package_parts()
                parts[name] = "<x/>"
                result = self.run_parts(parts)
                self.assertIn("unsafe-member-name", self.codes(result))
                self.assertEqual(result["coverage"]["xml_parts_inspected"], 0)

    def test_duplicate_zip_members_rejected(self):
        path = self.folder / "dupes.docx"
        example.write_package(path, example.package_parts())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "a") as z:
                z.writestr("word/document.xml", "<x/>")
        self.assertIn("duplicate-member", self.codes(audit.inspect_file(path)))

    def test_case_equivalent_package_names_are_rejected(self):
        parts = example.package_parts()
        parts["WORD/DOCUMENT.XML"] = parts["word/document.xml"]
        result = self.run_parts(parts)
        self.assertIn("case-equivalent-members", self.codes(result))
        self.assertEqual(result["exit_code"], 2)
        self.assertFalse(result["coverage"]["archive_preflight_passed"])
        self.assertEqual(result["coverage"]["xml_parts_inspected"], 0)

    def test_nul_original_filename_is_not_silently_truncated(self):
        parts = example.package_parts()
        parts["word/document.xmlXsuffix"] = parts.pop("word/document.xml")
        path = self.folder / "nul-name.docx"
        example.write_package(path, parts)
        raw = path.read_bytes().replace(b"word/document.xmlXsuffix", b"word/document.xml\x00suffix")
        path.write_bytes(raw)
        with zipfile.ZipFile(path) as archive:
            entry = archive.getinfo("word/document.xml")
            self.assertNotEqual(entry.orig_filename, entry.filename)
        result = audit.inspect_file(path)
        self.assertIn("unsafe-member-name", self.codes(result))
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(path.read_bytes(), raw)

    def test_relationship_parts_require_relationship_content_type(self):
        parts = example.package_parts()
        parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace("application/vnd.openxmlformats-package.relationships+xml", "text/plain")
        result = self.run_parts(parts)
        self.assertIn("relationship-content-type", self.codes(result))
        self.assertEqual(result["exit_code"], 2)

    def test_consuming_relationship_reference_must_resolve(self):
        parts = example.package_parts("excel")
        parts["xl/workbook.xml"] = parts["xl/workbook.xml"].replace('r:id="rId1"', 'r:id="rId999"')
        result = self.run_parts(parts, "xlsx")
        self.assertIn("unresolved-relationship-reference", self.codes(result))
        self.assertEqual(result["exit_code"], 2)
        self.assertNotIn("rId999", json.dumps(result))

    def test_embed_and_link_ids_are_checked_in_both_namespace_families(self):
        for namespace in [example.R, audit.STRICT_REL.rstrip("/")]:
            for local in ["embed", "link"]:
                with self.subTest(namespace=namespace, attribute=local):
                    parts = example.package_parts()
                    parts["word/document.xml"] = parts["word/document.xml"].replace('<w:document ', f'<w:document xmlns:r="{namespace}" r:{local}="missing" ')
                    self.assertIn("unresolved-relationship-reference", self.codes(self.run_parts(parts)))

    def test_relationship_ids_do_not_leak_between_source_parts(self):
        parts = example.package_parts()
        parts["word/document.xml"] = parts["word/document.xml"].replace('<w:document ', f'<w:document xmlns:r="{example.R}" r:id="rId1" ')
        # rId1 exists at package scope; it does not belong to the main part.
        self.assertIn("unresolved-relationship-reference", self.codes(self.run_parts(parts)))

    def test_declared_external_consuming_reference_is_review_not_error(self):
        parts = example.package_parts()
        parts["word/document.xml"] = parts["word/document.xml"].replace('<w:document ', f'<w:document xmlns:r="{example.R}" r:id="rId2" ')
        parts["word/_rels/document.xml.rels"] = f'<Relationships xmlns="{example.REL}"><Relationship Id="rId2" Type="{example.R}/hyperlink" Target="https://example.invalid/" TargetMode="External"/></Relationships>'
        result = self.run_parts(parts)
        self.assertNotIn("unresolved-relationship-reference", self.codes(result))
        self.assertEqual(result["exit_code"], 1)

    def test_strict_properties_at_arbitrary_part_names_need_review(self):
        for strict_main in [False, True]:
            for kind in ["extendedProperties", "customProperties"]:
                with self.subTest(strict_main=strict_main, kind=kind):
                    parts = example.package_parts()
                    if strict_main:
                        parts["word/document.xml"] = parts["word/document.xml"].replace(example.W, "http://purl.oclc.org/ooxml/wordprocessingml/main")
                        parts["_rels/.rels"] = parts["_rels/.rels"].replace(example.R, audit.STRICT_REL.rstrip("/"))
                    parts["other/properties.xml"] = f'<Properties xmlns="http://purl.oclc.org/ooxml/officeDocument/{kind}"><Company>SECRET_VALUE</Company></Properties>'
                    result = self.run_parts(parts)
                    self.assertIn("document-properties", self.codes(result))
                    self.assertEqual(result["exit_code"], 1)
                    self.assertNotIn("SECRET_VALUE", json.dumps(result))

    def test_dtd_rejected_in_utf8_and_utf16(self):
        for encoding in ["utf-8", "utf-16"]:
            with self.subTest(encoding=encoding):
                parts = example.package_parts()
                parts["customXml/item1.xml"] = '<!DOCTYPE x [<!ENTITY x "sensitive">]><x>&x;</x>'.encode(encoding)
                result = self.run_parts(parts)
                self.assertIn("unsupported-xml-declaration", self.codes(result))
                self.assertIn("customXml/item1.xml", result["coverage"]["uninspected_parts"])

    def test_malformed_xml_fails(self):
        parts = example.package_parts()
        parts["word/document.xml"] = "<unclosed>"
        self.assertIn("invalid-xml", self.codes(self.run_parts(parts)))

    def test_undeclared_part_type_fails(self):
        parts = example.package_parts()
        parts["word/item.unknown"] = b"synthetic"
        self.assertIn("undeclared-content-type", self.codes(self.run_parts(parts)))

    def test_archive_and_member_limits(self):
        for limits, code in [(audit.Limits(members=1), "member-count-limit"),
                             (audit.Limits(member_bytes=10), "member-size-limit"),
                             (audit.Limits(total_bytes=10), "expanded-size-limit")]:
            with self.subTest(code=code):
                self.assertIn(code, self.codes(self.run_parts(limits=limits)))
        path = self.folder / "too-large.docx"
        path.write_bytes(b"x" * 20)
        self.assertIn("archive-size-limit", self.codes(audit.inspect_file(path, audit.Limits(archive_bytes=10))))

    def test_compression_ratio_bound(self):
        parts = example.package_parts()
        parts["repeat.xml"] = "<x>" + "A" * 100_000 + "</x>"
        self.assertIn("compression-ratio-limit", self.codes(self.run_parts(parts)))

    def test_encrypted_zip_member_is_rejected(self):
        path = self.folder / "encrypted.docx"
        example.write_package(path, example.package_parts(), compression=zipfile.ZIP_STORED)
        data = bytearray(path.read_bytes())
        local = data.index(b"PK\x03\x04")
        central = data.index(b"PK\x01\x02")
        for offset in [local + 6, central + 8]:
            flags = struct.unpack_from("<H", data, offset)[0]
            struct.pack_into("<H", data, offset, flags | 1)
        path.write_bytes(data)
        self.assertIn("encrypted-member", self.codes(audit.inspect_file(path)))

    def test_unsupported_compression_rejected(self):
        path = self.folder / "bzip.docx"
        example.write_package(path, example.package_parts(), compression=zipfile.ZIP_BZIP2)
        self.assertIn("unsupported-compression", self.codes(audit.inspect_file(path)))

    def test_symlink_member_rejected(self):
        path = self.folder / "links.docx"
        example.write_package(path, example.package_parts())
        with zipfile.ZipFile(path, "a") as z:
            info = zipfile.ZipInfo("word/link.xml")
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            z.writestr(info, "../../file")
        self.assertIn("symlink-member", self.codes(audit.inspect_file(path)))

    def test_crc_failure_is_not_a_clean_scan(self):
        path = self.folder / "crc.docx"
        example.write_package(path, example.package_parts(), compression=zipfile.ZIP_STORED)
        raw = path.read_bytes().replace(b"Synthetic example.", b"Synthetix example.")
        path.write_bytes(raw)
        self.assertIn("member-unreadable", self.codes(audit.inspect_file(path)))

    def test_invalid_row_and_huge_integer_fail_without_crash(self):
        for r in ["-1", "bad", "0", "1048577", "9" * 5000]:
            with self.subTest(length=len(r)):
                parts = example.package_parts("excel")
                parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace('r="1"', f'r="{r}"')
                self.assertIn("invalid-row-index", self.codes(self.run_parts(parts, "xlsx")))

    def test_shared_string_indexes_reject_negative_missing_and_huge(self):
        for value in ["-1", "0", "9" * 5000]:
            with self.subTest(length=len(value)):
                parts = example.package_parts("excel")
                parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace('<c r="A1"><v>12</v>', f'<c r="A1" t="s"><v>{value}</v>')
                self.assertIn("shared-string-reference", self.codes(self.run_parts(parts, "xlsx")))

    def test_valid_shared_strings(self):
        parts = example.package_parts("excel")
        parts["xl/sharedStrings.xml"] = f'<sst xmlns="{example.S}"><si><t>Synthetic label</t></si></sst>'
        parts["xl/_rels/workbook.xml.rels"] = parts["xl/_rels/workbook.xml.rels"].replace('</Relationships>', f'<Relationship Id="rId2" Type="{example.R}/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
        parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace('<c r="A1"><v>12</v>', '<c r="A1" t="s"><v>0</v>')
        self.assertNotIn("shared-string-reference", self.codes(self.run_parts(parts, "xlsx")))

    def test_unlinked_shared_strings_do_not_resolve_indexes(self):
        parts = example.package_parts("excel")
        parts["xl/sharedStrings.xml"] = f'<sst xmlns="{example.S}"><si><t>Synthetic label</t></si></sst>'
        parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace('<c r="A1"><v>12</v>', '<c r="A1" t="s"><v>0</v>')
        self.assertIn("shared-string-reference", self.codes(self.run_parts(parts, "xlsx")))

    def test_review_surfaces_with_nonstandard_part_names(self):
        parts = example.package_parts("powerpoint")
        parts["other/metadata.xml"] = '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"><cp:category>SECRET_VALUE</cp:category></cp:coreProperties>'
        parts["other/notes.xml"] = f'<p:notes xmlns:p="{example.P}"/>'
        parts["other/slide.xml"] = f'<p:sld xmlns:p="{example.P}" show="0"/>'
        parts["other/data.xml"] = '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"/>'
        result = self.run_parts(parts, "pptx")
        self.assertTrue({"document-properties", "speaker-notes", "hidden-slide", "supplemental-data"} <= self.codes(result))
        self.assertNotIn("SECRET_VALUE", json.dumps(result))

    def test_duplicate_shapes_are_detected(self):
        parts = example.package_parts("excel")
        ns = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
        parts["xl/drawings/drawing1.xml"] = f'<wsDr xmlns="{ns}"><oneCellAnchor><sp><nvSpPr><cNvPr id="1"/></nvSpPr></sp></oneCellAnchor><oneCellAnchor><sp><nvSpPr><cNvPr id="1"/></nvSpPr></sp></oneCellAnchor></wsDr>'
        self.assertIn("duplicate-drawing-id", self.codes(self.run_parts(parts, "xlsx")))

    def test_unsupported_and_unreadable_inputs(self):
        self.assertEqual(audit.inspect_file(self.folder / "old.doc")["status"], "unsupported")
        self.assertIn("input-unreadable", self.codes(audit.inspect_file(self.folder / "absent.docx")))
        path = self.folder / "notzip.docx"
        path.write_bytes(b"synthetic nonzip")
        self.assertIn("archive-unreadable", self.codes(audit.inspect_file(path)))

    def test_cli_exit_statuses_and_json(self):
        subprocess.run([sys.executable, str(ROOT / "examples/make_examples.py"), str(self.folder)], check=True, capture_output=True)
        for name, code in [("clean.docx", 0), ("review.xlsx", 1), ("broken.docx", 2)]:
            with self.subTest(name=name):
                result = subprocess.run([sys.executable, str(ROOT / "scripts/audit.py"), str(self.folder / name)], capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data["exit_code"], code)
                self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
