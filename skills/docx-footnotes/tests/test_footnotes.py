"""Structural tests, not a claim of Microsoft Word rendering validation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
from xml.dom import minidom
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


editor = load("footnote_editor", ROOT / "scripts/add_footnotes.py")
example = load("footnote_example", ROOT / "examples/make_example.py")
NOTES = [{"marker": "[[fn:purpose]]", "text": "A & B < C; 'quoted' and \"double\"."},
         {"marker": "[[fn:data]]", "text": "Synthetic evidence."}]


class FootnoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "input.docx"
        self.output = self.folder / "output.docx"
        example.make_example(self.source)

    def parts(self, path=None):
        with zipfile.ZipFile(path or self.source) as z:
            return {n: z.read(n) for n in z.namelist()}

    def rewrite(self, transform):
        parts = self.parts()
        transform(parts)
        with zipfile.ZipFile(self.source, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in parts.items():
                z.writestr(name, data)

    def replace(self, old, new, part="word/document.xml"):
        self.rewrite(lambda p: p.update({part: p[part].replace(old.encode(), new.encode())}))

    def rejects(self, notes=NOTES):
        before = self.source.read_bytes()
        with self.assertRaises(editor.DocumentError):
            editor.insert_footnotes(self.source, self.output, notes)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.source.read_bytes(), before)

    def test_creates_parts_and_escapes_content(self):
        original = self.source.read_bytes()
        result = editor.insert_footnotes(self.source, self.output, NOTES[::-1])
        self.assertEqual([n["marker"] for n in result["inserted"]], [n["marker"] for n in NOTES])
        self.assertEqual([n["footnote_id"] for n in result["inserted"]], [1, 2])
        self.assertEqual(result["visual_validation"], "NOT_RUN")
        self.assertEqual(self.source.read_bytes(), original)
        parts = self.parts(self.output)
        doc = minidom.parseString(parts["word/document.xml"])
        fn = minidom.parseString(parts["word/footnotes.xml"])
        editor.validate_references(doc, fn)
        self.assertIn(NOTES[0]["text"], "".join(editor.text(n) for n in fn.getElementsByTagNameNS(editor.W, "t")))
        self.assertEqual(doc.documentElement.getAttribute("xmlns:w14"), "http://schemas.microsoft.com/office/word/2010/wordml")
        self.assertIn("w14", doc.documentElement.getAttribute("mc:Ignorable"))
        self.assertEqual(parts["_rels/.rels"], self.parts()["_rels/.rels"])

    def test_existing_notes_and_separator_ids_preserved(self):
        editor.insert_footnotes(self.source, self.output, [NOTES[0]])
        self.source.write_bytes(self.output.read_bytes())
        self.output.unlink()
        self.replace('w:id="1"', 'w:id="19"')
        self.replace('w:id="1"', 'w:id="19"', "word/footnotes.xml")
        self.replace('w:id="-1"', 'w:id="-7"', "word/footnotes.xml")
        before_fn = minidom.parseString(self.parts()["word/footnotes.xml"])
        before_nodes = {n.getAttributeNS(editor.W, "id"): n.toxml() for n in editor.elements(before_fn.documentElement)}
        result = editor.insert_footnotes(self.source, self.output, [NOTES[1]])
        self.assertEqual(result["inserted"][0]["footnote_id"], 20)
        after = minidom.parseString(self.parts(self.output)["word/footnotes.xml"])
        after_nodes = {n.getAttributeNS(editor.W, "id"): n.toxml() for n in editor.elements(after.documentElement)}
        for ident, node in before_nodes.items():
            self.assertEqual(after_nodes[ident], node)

    def test_preserves_unrelated_bytes_and_zip_member_metadata(self):
        with zipfile.ZipFile(self.source, "a") as z:
            info = zipfile.ZipInfo("custom/example.bin", (2020, 1, 1, 0, 0, 0))
            info.comment = b"Synthetic member"
            info.external_attr = 0o600 << 16
            z.writestr(info, b"\x00\x01synthetic\xff")
        editor.insert_footnotes(self.source, self.output, NOTES)
        with zipfile.ZipFile(self.source) as a, zipfile.ZipFile(self.output) as b:
            self.assertEqual(a.read("custom/example.bin"), b.read("custom/example.bin"))
            self.assertEqual(a.getinfo("custom/example.bin").comment, b.getinfo("custom/example.bin").comment)
            self.assertEqual(a.getinfo("custom/example.bin").external_attr, b.getinfo("custom/example.bin").external_attr)

    def test_existing_destination_never_overwritten(self):
        self.output.write_bytes(b"existing output")
        with self.assertRaises(editor.DocumentError):
            editor.insert_footnotes(self.source, self.output, NOTES)
        self.assertEqual(self.output.read_bytes(), b"existing output")
        with self.assertRaises(editor.DocumentError):
            editor.insert_footnotes(self.source, self.source, NOTES)

    def test_racing_destination_never_overwritten(self):
        real_link = editor.os.link
        def racing_link(src, dst):
            Path(dst).write_bytes(b"other process output")
            return real_link(src, dst)
        with patch.object(editor.os, "link", side_effect=racing_link):
            with self.assertRaises(FileExistsError):
                editor.insert_footnotes(self.source, self.output, NOTES)
        self.assertEqual(self.output.read_bytes(), b"other process output")
        self.assertEqual(list(self.folder.glob(".footnotes-*")), [])

    def test_repeat_edit_rejected_when_marker_consumed(self):
        editor.insert_footnotes(self.source, self.output, NOTES)
        with self.assertRaises(editor.DocumentError):
            editor.insert_footnotes(self.output, self.folder / "again.docx", NOTES)

    def test_missing_ambiguous_and_split_markers_rejected(self):
        for replacement in ["missing", "[[fn:purpose]][[fn:purpose]]", "prefix [[fn:purpose]]"]:
            with self.subTest(replacement=replacement):
                original = self.source.read_bytes()
                self.replace("[[fn:purpose]]", replacement)
                self.rejects()
                self.source.write_bytes(original)
        self.replace("[[fn:purpose]]", "[[fn:pur</w:t></w:r><w:r><w:t>pose]]")
        self.rejects()

    def test_duplicate_request_and_invalid_text_rejected(self):
        for notes in [NOTES + [NOTES[0]], [], [{"marker": "[[fn:purpose]]", "text": ""}],
                      [{"marker": "[[fn:purpose]]", "text": "bad\x00text"}],
                      [{"marker": "[[fn:purpose]]", "text": "\ud800"}]]:
            with self.subTest(notes=repr(notes)):
                self.rejects(notes)

    def test_revisions_rejected(self):
        self.replace("<w:body>", '<w:body><w:ins w:id="1"/>')
        self.rejects()

    def test_markup_compatibility_wrapper_rejected(self):
        self.replace("<w:r><w:t>[[fn:purpose]]</w:t></w:r>", '<mc:AlternateContent><mc:Fallback><w:r><w:t>[[fn:purpose]]</w:t></w:r></mc:Fallback></mc:AlternateContent>')
        self.rejects()

    def test_dtd_rejected(self):
        self.replace('<w:document', '<!DOCTYPE document [<!ENTITY x "payload">]><w:document')
        self.rejects()

    def test_duplicate_zip_member_and_unsafe_names_rejected(self):
        original = self.source.read_bytes()
        for name in ["word/document.xml", "../outside.xml", "WORD/DOCUMENT.XML"]:
            with self.subTest(name=name):
                self.source.write_bytes(original)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    with zipfile.ZipFile(self.source, "a") as z:
                        z.writestr(name, b"<x/>")
                self.rejects()

    def test_dangling_body_reference_rejected(self):
        self.replace("<w:body>", '<w:body><w:p><w:r><w:footnoteReference w:id="50"/></w:r></w:p>')
        self.rejects()

    def test_macro_and_signature_parts_rejected(self):
        original = self.source.read_bytes()
        for name in ["word/vbaProject.bin", "_xmlsignatures/sig1.xml"]:
            self.source.write_bytes(original)
            with zipfile.ZipFile(self.source, "a") as z:
                z.writestr(name, b"synthetic")
            self.rejects()

    def test_strict_namespace_rejected(self):
        self.replace(editor.W, "http://purl.oclc.org/ooxml/wordprocessingml/main")
        self.rejects()

    def test_xml_depth_limit(self):
        self.rewrite(lambda p: p.update({"custom/deep.xml": b"<a>" * 140 + b"</a>" * 140}))
        self.rejects()

    def test_marker_outside_body_rejected(self):
        self.replace("<w:r><w:t>[[fn:purpose]]</w:t></w:r>", "")
        self.replace("<w:body>", "<w:p><w:r><w:t>[[fn:purpose]]</w:t></w:r></w:p><w:body>")
        self.rejects()

    def test_exhausted_id_range_rejected(self):
        editor.insert_footnotes(self.source, self.output, [NOTES[0]])
        self.source.write_bytes(self.output.read_bytes())
        self.output.unlink()
        self.replace('w:id="1"', 'w:id="2147483647"')
        self.replace('w:id="1"', 'w:id="2147483647"', "word/footnotes.xml")
        self.rejects([NOTES[1]])

    def test_existing_custom_part_and_prefixed_relationships(self):
        editor.insert_footnotes(self.source, self.output, [NOTES[0]])
        self.source.write_bytes(self.output.read_bytes())
        self.output.unlink()
        def transform(parts):
            parts["word/notes-extra.xml"] = parts.pop("word/footnotes.xml")
            parts["word/_rels/document.xml.rels"] = parts["word/_rels/document.xml.rels"].replace(b'footnotes.xml', b'notes-extra.xml')
            parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(b'footnotes.xml', b'notes-extra.xml')
        self.rewrite(transform)
        editor.insert_footnotes(self.source, self.output, [NOTES[1]])
        self.assertIn("word/notes-extra.xml", self.parts(self.output))
        self.assertNotIn("word/footnotes.xml", self.parts(self.output))

    def test_prefixed_types_and_relationships_remain_namespaced(self):
        self.replace('<Types xmlns=', '<c:Types xmlns:c=', "[Content_Types].xml")
        self.replace('</Types>', '</c:Types>', "[Content_Types].xml")
        for local in ["Default", "Override"]:
            self.replace('<' + local, '<c:' + local, "[Content_Types].xml")
        self.rewrite(lambda p: p.update({"word/_rels/document.xml.rels": f'<r:Relationships xmlns:r="{editor.R}"/>'.encode()}))
        editor.insert_footnotes(self.source, self.output, NOTES)
        parts = self.parts(self.output)
        rels = editor.relationships(minidom.parseString(parts["word/_rels/document.xml.rels"]))
        self.assertEqual(len(rels), 1)
        types = minidom.parseString(parts["[Content_Types].xml"])
        self.assertEqual(len(types.getElementsByTagNameNS(editor.CT, "Override")), 2)

    def test_local_word_prefix_shadow_preserves_serialized_namespace(self):
        def transform(parts):
            data = parts[editor.MAIN].replace(b"w:", b"q:").replace(b"xmlns:w=", b"xmlns:q=")
            parts[editor.MAIN] = data.replace(b"<q:p>", b'<q:p xmlns:w="urn:synthetic-unrelated">', 1)
        self.rewrite(transform)
        editor.insert_footnotes(self.source, self.output, NOTES)
        doc = minidom.parseString(self.parts(self.output)[editor.MAIN])
        self.assertEqual(len(doc.getElementsByTagNameNS(editor.W, "footnoteReference")), 2)
        self.assertEqual(len(doc.getElementsByTagNameNS("urn:synthetic-unrelated", "footnoteReference")), 0)
        self.assertEqual(doc.getElementsByTagNameNS(editor.W, "p")[0].getAttribute("xmlns:w"), "urn:synthetic-unrelated")

    def test_missing_default_rels_type_gets_explicit_override(self):
        self.replace('<Default Extension="rels"', '<Override PartName="/_rels/.rels"', "[Content_Types].xml")
        editor.insert_footnotes(self.source, self.output, NOTES)
        types = minidom.parseString(self.parts(self.output)["[Content_Types].xml"])
        overrides = {n.getAttribute("PartName"): n.getAttribute("ContentType") for n in types.getElementsByTagNameNS(editor.CT, "Override")}
        self.assertEqual(overrides["/" + editor.RELS], editor.REL_TYPE)

    def test_invalid_existing_rels_content_type_is_rejected(self):
        self.replace(editor.REL_TYPE, "text/plain", "[Content_Types].xml")
        self.rejects()

    def test_cleanup_failure_reports_published_output_and_warning(self):
        original = self.source.read_bytes()
        unlink = Path.unlink
        def deny_temporary_unlink(path, *args, **kwargs):
            if path.name.startswith(".footnotes-"):
                raise PermissionError("Synthetic cleanup failure")
            return unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", deny_temporary_unlink):
            result = editor.insert_footnotes(self.source, self.output, NOTES)
        self.assertEqual(result["status"], "STRUCTURALLY_CHECKED")
        self.assertEqual(result["warnings"][0]["code"], "TEMPORARY_CLEANUP_FAILED")
        leftover = Path(result["warnings"][0]["path"])
        self.assertTrue(self.output.exists())
        self.assertEqual(leftover.read_bytes(), self.output.read_bytes())
        self.assertEqual(self.source.read_bytes(), original)
        leftover.unlink()

    def cli_rejects(self, notes_bytes=None, notes=NOTES):
        np = self.folder / "notes.json"
        np.write_bytes(notes_bytes if notes_bytes is not None else json.dumps(notes).encode())
        result = subprocess.run([sys.executable, str(ROOT / "scripts/add_footnotes.py"), str(self.source), str(self.output), "--notes", str(np)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "ERROR")
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.output.exists())

    def test_invalid_id_lexical_forms_have_structured_cli_errors(self):
        editor.insert_footnotes(self.source, self.output, [NOTES[0]])
        baseline = self.output.read_bytes()
        self.output.unlink()
        for ident in ["9" * 5000, "\u0661"]:
            for part in [editor.MAIN, "word/footnotes.xml"]:
                with self.subTest(ident_length=len(ident), part=part):
                    self.source.write_bytes(baseline)
                    self.replace('w:id="1"', 'w:id="' + ident + '"', part)
                    self.cli_rejects(notes=[NOTES[1]])

    def test_malformed_relationship_url_has_structured_cli_error(self):
        self.replace('Target="word/document.xml"', 'Target="http://[malformed"', "_rels/.rels")
        self.cli_rejects()

    def test_corrupt_deflate_has_structured_cli_error(self):
        raw = bytearray(self.source.read_bytes())
        with zipfile.ZipFile(self.source) as z:
            info = z.getinfo(editor.MAIN)
        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        raw[start] = 0x07
        self.source.write_bytes(raw)
        self.cli_rejects()

    def test_invalid_notes_encoding_and_json_have_structured_cli_errors(self):
        for data in [b"\xff", b"{", b"[" + b"9" * 5000 + b"]", b"[" * 1500 + b"]" * 1500]:
            with self.subTest(length=len(data)):
                self.cli_rejects(notes_bytes=data)

    def test_invalid_source_encoding_and_doctype_have_structured_cli_errors(self):
        baseline = self.source.read_bytes()
        for value in [b"\xff", b'<!DOCTYPE x [<!ENTITY y "synthetic">]><x/>', '<x/>'.encode("utf-16")]:
            with self.subTest(length=len(value)):
                self.source.write_bytes(baseline)
                self.rewrite(lambda p: p.update({editor.MAIN: value}))
                self.cli_rejects()

    def test_missing_and_nonzip_files_have_structured_cli_errors(self):
        self.source.unlink()
        self.cli_rejects()
        self.source.write_bytes(b"synthetic non-zip input")
        self.cli_rejects()


if __name__ == "__main__":
    unittest.main()
