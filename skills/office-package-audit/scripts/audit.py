#!/usr/bin/env python3
"""Read-only, bounded inspection of Office Open XML packages.

Reports structural errors and surfaces that need content review. It never
extracts archive members, follows links, runs macros, or infers authorship.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile
import zlib


CT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
STRICT_REL = "http://purl.oclc.org/ooxml/officeDocument/relationships/"
NAMESPACES = {
    "word": {"http://schemas.openxmlformats.org/wordprocessingml/2006/main",
             "http://purl.oclc.org/ooxml/wordprocessingml/main"},
    "excel": {"http://schemas.openxmlformats.org/spreadsheetml/2006/main",
              "http://purl.oclc.org/ooxml/spreadsheetml/main"},
    "powerpoint": {"http://schemas.openxmlformats.org/presentationml/2006/main",
                   "http://purl.oclc.org/ooxml/presentationml/main"},
}
FORMATS = {
    ".docx": ("word", "document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"),
    ".docm": ("word", "document", "application/vnd.ms-word.document.macroEnabled.main+xml"),
    ".dotx": ("word", "document", "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"),
    ".dotm": ("word", "document", "application/vnd.ms-word.template.macroEnabledTemplate.main+xml"),
    ".xlsx": ("excel", "workbook", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
    ".xlsm": ("excel", "workbook", "application/vnd.ms-excel.sheet.macroEnabled.main+xml"),
    ".xltx": ("excel", "workbook", "application/vnd.openxmlformats-officedocument.spreadsheetml.template.main+xml"),
    ".xltm": ("excel", "workbook", "application/vnd.ms-excel.template.macroEnabled.main+xml"),
    ".pptx": ("powerpoint", "presentation", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
    ".pptm": ("powerpoint", "presentation", "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml"),
    ".potx": ("powerpoint", "presentation", "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"),
    ".potm": ("powerpoint", "presentation", "application/vnd.ms-powerpoint.template.macroEnabled.main+xml"),
}


@dataclass(frozen=True)
class Limits:
    archive_bytes: int = 64 * 1024 * 1024
    members: int = 5000
    member_bytes: int = 16 * 1024 * 1024
    total_bytes: int = 128 * 1024 * 1024
    compression_ratio: int = 200


def split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return "", tag


def safe_name(name: str, *, directory: bool = False) -> bool:
    value = name[:-1] if directory and name.endswith("/") else name
    return bool(value) and not (
        value.startswith("/") or "\\" in value or ":" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
        or any(x in {"", ".", ".."} for x in value.split("/"))
    )


def rel_owner(name: str) -> str | None:
    if name.lower() == "_rels/.rels":
        return ""
    p = PurePosixPath(name)
    if p.parent.name.lower() != "_rels" or not p.name.lower().endswith(".rels"):
        return None
    return str(p.parent.parent / p.name[:-5])


def target_part(owner: str, target: str) -> str | None:
    """Resolve a package URI without allowing traversal above the package root."""
    try:
        uri = urlsplit(target)
    except ValueError:
        return None
    if uri.scheme or uri.netloc or uri.query:
        return None
    value = unquote(uri.path)
    if not value or "\\" in value or "\x00" in value or ":" in value:
        return None
    parts = [] if value.startswith("/") else owner.split("/")[:-1]
    for item in value.split("/"):
        if item in {"", "."}:
            continue
        if item == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(item)
    return "/".join(parts) or None


class Inspector:
    def __init__(self, path: Path, limits: Limits):
        self.path, self.limits = path, limits
        self.result = {
            "schema_version": 1,
            "file": path.name,
            "sha256": None,
            "format": path.suffix.lower().lstrip("."),
            "status": "failed",
            "exit_code": 2,
            "scope": "Selected package checks and review-surface discovery; no content clearance, rendering, recalculation, or authorship inference.",
            "coverage": {"archive_members": 0, "archive_preflight_passed": False, "xml_parts_inspected": 0,
                         "uninspected_parts": []},
            "findings": [],
        }
        self.parts: set[str] = set()
        self.trees: dict[str, ET.Element] = {}
        self.content_types: dict[str, str] = {}
        self.relationships: dict[str, list[tuple[str, str | None]]] = {}
        self.relationship_ids: dict[str, set[str]] = {}

    def finding(self, severity: str, code: str, member: str,
                locator: str, message: str, count: int | None = None):
        item = {"severity": severity, "code": code, "member": member,
                "locator": locator, "message": message}
        if count is not None:
            item["count"] = count
        self.result["findings"].append(item)

    def finish(self, unsupported: bool = False):
        findings = self.result["findings"]
        findings.sort(key=lambda x: (x["member"], x["locator"], x["code"]))
        errors = any(f["severity"] == "error" for f in findings)
        review = any(f["severity"] == "review" for f in findings)
        self.result["status"] = "unsupported" if unsupported else "failed" if errors else "review" if review else "passed"
        self.result["exit_code"] = 2 if unsupported or errors else 1 if review else 0
        return self.result

    def run(self):
        if self.path.suffix.lower() not in FORMATS:
            self.finding("error", "unsupported-format", "", "", "Use an Office Open XML document, workbook, presentation, or template; legacy and other formats are not inspected.")
            return self.finish(unsupported=True)
        try:
            with self.path.open("rb") as stream:
                raw = stream.read(self.limits.archive_bytes + 1)
        except OSError:
            self.finding("error", "input-unreadable", "", "", "The input could not be read.")
            return self.finish()
        if len(raw) > self.limits.archive_bytes:
            self.finding("error", "archive-size-limit", "", "", "Compressed input exceeds the configured limit; inspection did not run.")
            return self.finish()
        self.result["sha256"] = hashlib.sha256(raw).hexdigest()
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if not self.preflight(archive):
                    return self.finish()
                self.result["coverage"]["archive_preflight_passed"] = True
                for entry in archive.infolist():
                    if entry.is_dir():
                        continue
                    name = entry.filename
                    try:
                        with archive.open(entry) as member:
                            data = member.read(self.limits.member_bytes + 1)
                    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError, zlib.error):
                        self.result["coverage"]["uninspected_parts"].append(name)
                        self.finding("error", "member-unreadable", name, "", "Member integrity or decompression failed; its contents were not inspected.")
                        continue
                    if len(data) > self.limits.member_bytes:
                        self.result["coverage"]["uninspected_parts"].append(name)
                        self.finding("error", "member-size-limit", name, "", "Expanded member exceeds the configured limit.")
                        continue
                    if name.lower().endswith((".xml", ".rels", ".vml")):
                        self.parse_xml(name, data)
                    else:
                        self.result["coverage"]["uninspected_parts"].append(name)
                        self.finding("review", "uninspected-nonxml", name, "", "Binary or non-XML content was checked for archive integrity only; inspect it separately before sharing.")
        except (zipfile.BadZipFile, OSError, ValueError):
            self.finding("error", "archive-unreadable", "", "", "Input is not a readable ZIP package; encrypted Office containers are unsupported.")
            return self.finish()
        self.check_content_types()
        self.check_relationships()
        self.check_relationship_references()
        self.check_main_part()
        self.check_surfaces()
        self.check_worksheets()
        self.check_drawings()
        return self.finish()

    def preflight(self, archive: zipfile.ZipFile) -> bool:
        entries = archive.infolist()
        self.result["coverage"]["archive_members"] = len(entries)
        if len(entries) > self.limits.members:
            self.finding("error", "member-count-limit", "", "", "Archive has too many members; inspection did not run.")
            return False
        total = sum(e.file_size for e in entries)
        if total > self.limits.total_bytes:
            self.finding("error", "expanded-size-limit", "", "", "Total expanded size exceeds the configured limit.")
        for name, count in Counter(e.filename for e in entries).items():
            if count > 1:
                self.finding("error", "duplicate-member", name, "", "Duplicate archive member names are ambiguous.", count)
        # OPC part names cannot differ only by ASCII letter case. Do not use
        # Unicode casefolding, which would merge unrelated non-ASCII names.
        ascii_lower = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
        aliases: dict[str, set[str]] = {}
        for e in entries:
            if not e.is_dir():
                aliases.setdefault(e.filename.translate(ascii_lower), set()).add(e.filename)
        for names in aliases.values():
            if len(names) > 1:
                self.finding("error", "case-equivalent-members", sorted(names)[0], "", "Part names differ only by ASCII case and are ambiguous under package name equivalence.", len(names))
        for e in entries:
            name = e.filename
            # ZipInfo truncates filename at a NUL but retains orig_filename.
            # Inspect both rather than accepting the normalized public name.
            if e.orig_filename != name or not safe_name(e.orig_filename, directory=e.is_dir()):
                self.finding("error", "unsafe-member-name", name, "", "Member name is not a safe package path.")
            if stat.S_ISLNK(e.external_attr >> 16):
                self.finding("error", "symlink-member", name, "", "Symbolic-link archive members are unsupported.")
            if e.flag_bits & 1:
                self.finding("error", "encrypted-member", name, "", "Encrypted ZIP members are not inspected.")
            if e.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                self.finding("error", "unsupported-compression", name, "", "Only stored and DEFLATE members are supported.")
            if e.file_size > self.limits.member_bytes:
                self.finding("error", "member-size-limit", name, "", "Expanded member exceeds the configured limit.")
            if e.file_size > max(1, e.compress_size) * self.limits.compression_ratio:
                self.finding("error", "compression-ratio-limit", name, "", "Member compression ratio exceeds the configured limit.")
        self.parts = {e.filename for e in entries if not e.is_dir()}
        return not self.result["findings"]

    def parse_xml(self, name: str, data: bytes):
        # DTDs/entities are unnecessary for these Office parts. Reject even UTF-16
        # declarations before parsing, rather than letting entity expansion run.
        normalized = data.replace(b"\x00", b"").upper()
        if b"<!DOCTYPE" in normalized or b"<!ENTITY" in normalized:
            self.result["coverage"]["uninspected_parts"].append(name)
            self.finding("error", "unsupported-xml-declaration", name, "", "DTD and entity declarations are not processed.")
            return
        try:
            self.trees[name] = ET.fromstring(data)
            self.result["coverage"]["xml_parts_inspected"] += 1
        except (ET.ParseError, ValueError):
            self.result["coverage"]["uninspected_parts"].append(name)
            self.finding("error", "invalid-xml", name, "", "XML could not be parsed.")

    def check_content_types(self):
        root = self.trees.get("[Content_Types].xml")
        if root is None or root.tag != f"{{{CT}}}Types":
            self.finding("error", "missing-content-types", "[Content_Types].xml", "/", "A valid package content-types part is required.")
            return
        defaults, overrides = {}, {}
        for i, item in enumerate(root, 1):
            ns, kind = split_tag(item.tag)
            key = item.get("Extension", "").lower() if kind == "Default" else item.get("PartName", "")
            typ = item.get("ContentType", "")
            if ns != CT or kind not in {"Default", "Override"} or not key or not typ:
                self.finding("error", "invalid-content-type", "[Content_Types].xml", f"/*[{i}]", "Content-type declaration is incomplete or unrecognized.")
                continue
            target = defaults if kind == "Default" else overrides
            if key in target:
                self.finding("error", "duplicate-content-type", "[Content_Types].xml", f"/*[{i}]", "Content-type declaration is duplicated.")
            target[key] = typ
        for name in sorted(self.parts - {"[Content_Types].xml"}):
            typ = overrides.get("/" + name) or defaults.get(name.rsplit(".", 1)[-1].lower())
            if not typ:
                self.finding("error", "undeclared-content-type", name, "", "No content type is declared for this member.")
            else:
                self.content_types[name] = typ
                if name.lower().endswith(".rels") and typ != "application/vnd.openxmlformats-package.relationships+xml":
                    self.finding("error", "relationship-content-type", name, "", "Relationship parts require the package relationships content type.")

    def check_relationships(self):
        for name in sorted(n for n in self.parts if n.lower().endswith(".rels")):
            tree = self.trees.get(name)
            if tree is None:
                continue
            owner = rel_owner(name)
            if owner is None or (owner and owner not in self.parts):
                self.finding("error", "invalid-relationship-owner", name, "/", "Relationship part has no valid source part.")
                continue
            if tree.tag != f"{{{REL}}}Relationships":
                self.finding("error", "invalid-relationship-root", name, "/", "Relationship part has an unexpected XML root.")
                continue
            seen = set()
            self.relationships[owner] = []
            self.relationship_ids[owner] = seen
            for i, r in enumerate(tree, 1):
                loc = f"/Relationships/Relationship[{i}]"
                rid, typ, target = r.get("Id"), r.get("Type"), r.get("Target")
                if r.tag != f"{{{REL}}}Relationship" or not all((rid, typ, target)):
                    self.finding("error", "invalid-relationship", name, loc, "Relationship lacks a required attribute or has an unexpected tag.")
                    continue
                if rid in seen:
                    self.finding("error", "duplicate-relationship-id", name, loc + "/@Id", "Relationship ID is duplicated in this part.")
                seen.add(rid)
                mode = r.get("TargetMode", "Internal")
                if mode == "External":
                    self.finding("review", "external-relationship", name, loc + "/@Target", "External target is present; the target was not opened or reproduced in this report.")
                    self.relationships[owner].append((typ, None))
                    continue
                if mode != "Internal":
                    self.finding("error", "invalid-target-mode", name, loc + "/@TargetMode", "Unknown relationship target mode.")
                    continue
                resolved = target_part(owner, target)
                self.relationships[owner].append((typ, resolved))
                if resolved is None:
                    self.finding("error", "invalid-internal-target", name, loc + "/@Target", "Target is not a valid internal package path.")
                elif resolved not in self.parts:
                    self.finding("error", "missing-relationship-target", name, loc + "/@Target", "Internal target part is missing.")

    def check_relationship_references(self):
        """Check consuming XML attributes against their own source-part IDs."""
        reference_namespaces = {OFFICE_REL.rstrip("/"), STRICT_REL.rstrip("/")}
        for name, tree in sorted(self.trees.items()):
            declared = self.relationship_ids.get(name, set())
            for index, element in enumerate(tree.iter(), 1):
                for attribute, value in element.attrib.items():
                    namespace, local = split_tag(attribute)
                    if namespace in reference_namespaces and local in {"id", "embed", "link"} and value not in declared:
                        self.finding("error", "unresolved-relationship-reference", name,
                                     f"element()[{index}]/@relationships:{local}",
                                     "Consuming relationship reference has no declaration in this source part's relationship file.")

    def check_main_part(self):
        mains = [target for typ, target in self.relationships.get("", [])
                 if typ in {OFFICE_REL + "officeDocument", STRICT_REL + "officeDocument"}]
        if len(mains) != 1 or not mains[0] or mains[0] not in self.trees:
            self.finding("error", "missing-office-main-part", "_rels/.rels", "/Relationships", "Exactly one internal, readable Office document relationship is required.")
            return
        main = mains[0]
        family, local, expected_type = FORMATS[self.path.suffix.lower()]
        namespace, root_name = split_tag(self.trees[main].tag)
        if namespace not in NAMESPACES[family] or root_name != local:
            self.finding("error", "main-part-format-mismatch", main, "/", "Main XML root does not match the file extension.")
        if self.content_types.get(main) != expected_type:
            self.finding("error", "main-content-type-mismatch", main, "/", "Main content type does not match the file extension.")

    def check_surfaces(self):
        targets_by_kind: dict[str, set[str]] = {}
        for relationships in self.relationships.values():
            for typ, target in relationships:
                if target:
                    targets_by_kind.setdefault(typ.rsplit("/", 1)[-1], set()).add(target)
        metadata_namespaces = {
            "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
            "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
            "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties",
            "http://purl.oclc.org/ooxml/officeDocument/extendedProperties",
            "http://purl.oclc.org/ooxml/officeDocument/customProperties",
        }
        for name, tree in sorted(self.trees.items()):
            lower = name.lower()
            root_ns, root_local = split_tag(tree.tag)
            if lower.startswith("docprops/") or root_ns in metadata_namespaces or any(name in targets_by_kind.get(kind, set()) for kind in {"core-properties", "extended-properties", "custom-properties", "extendedProperties", "customProperties"}):
                self.finding("review", "document-properties", name, "/", "Document metadata is present; review fields and values before sharing.", len(list(tree)))
            if lower.startswith("customxml/") or name in targets_by_kind.get("customXml", set()):
                self.finding("review", "custom-xml", name, "/", "Custom XML may contain additional data outside the visible document.")
            if ("comments" in PurePosixPath(lower).name and lower.endswith(".xml")) or root_local in {"comments", "cmLst", "cmAuthorLst", "ThreadedComments"}:
                self.finding("review", "comments-part", name, "/", "Comment-related XML is present; review text, authors and dates.")
            if (lower.startswith("ppt/notesslides/") and lower.endswith(".xml")) or (root_ns in NAMESPACES["powerpoint"] and root_local == "notes"):
                self.finding("review", "speaker-notes", name, "/", "Speaker-note XML is present and may contain content outside slides.")
            if root_ns in NAMESPACES["powerpoint"] and root_local == "sld" and tree.get("show", "1").lower() in {"0", "false", "off"}:
                self.finding("review", "hidden-slide", name, "/sld/@show", "A slide is marked hidden.")
            if root_local in {"chartSpace", "pivotCacheDefinition", "pivotCacheRecords", "connections", "externalLink"}:
                self.finding("review", "supplemental-data", name, "/", "Chart caches, pivot data or connection information may contain data outside visible cells or text.")
            tracked, hidden_text, hidden_items = 0, 0, 0
            for element in tree.iter():
                ns, local = split_tag(element.tag)
                if ns in NAMESPACES["word"]:
                    if local in {"ins", "del", "moveFrom", "moveTo", "pPrChange", "rPrChange", "tblPrChange", "trPrChange", "tcPrChange", "sectPrChange"}:
                        tracked += 1
                    if local in {"vanish", "webHidden"} and element.get(f"{{{ns}}}val", "true").lower() not in {"0", "false", "off"}:
                        hidden_text += 1
                if ns in NAMESPACES["excel"]:
                    if local == "sheet" and element.get("state") in {"hidden", "veryHidden"}:
                        hidden_items += 1
                    elif local in {"row", "col", "definedName"} and element.get("hidden", "0").lower() in {"1", "true", "on"}:
                        hidden_items += 1
            if tracked:
                self.finding("review", "tracked-changes", name, "//*[revision element]", "Revision markup is present; deleted or superseded content may remain.", tracked)
            if hidden_text:
                self.finding("review", "hidden-text-property", name, "//*[hidden text property]", "Hidden text properties are present; inspect their application and text.", hidden_text)
            if hidden_items:
                self.finding("review", "hidden-workbook-items", name, "//*[hidden attribute]", "Hidden sheets, rows, columns or defined names are present.", hidden_items)
            if lower.endswith("calcchain.xml"):
                self.finding("review", "calculation-chain", name, "/", "A calculation chain is present; this tool does not verify its freshness or calculate formulas.")

    def check_worksheets(self):
        string_targets = [target for owner, relationships in self.relationships.items()
                          if owner in self.trees and split_tag(self.trees[owner].tag)[0] in NAMESPACES["excel"]
                          and split_tag(self.trees[owner].tag)[1] == "workbook"
                          for typ, target in relationships
                          if typ in {OFFICE_REL + "sharedStrings", STRICT_REL + "sharedStrings"}]
        strings = [self.trees[target] for target in string_targets if target in self.trees
                   and split_tag(self.trees[target].tag)[0] in NAMESPACES["excel"]
                   and split_tag(self.trees[target].tag)[1] == "sst"]
        string_count = sum(1 for child in strings[0] if split_tag(child.tag)[1] == "si") if len(strings) == 1 else None
        for name, tree in sorted(self.trees.items()):
            ns, local = split_tag(tree.tag)
            if ns not in NAMESPACES["excel"] or local != "worksheet":
                continue
            previous_row = 0
            for ri, row in enumerate(tree.findall(f"{{{ns}}}sheetData/{{{ns}}}row"), 1):
                loc = f"/worksheet/sheetData/row[{ri}]"
                r = row.get("r")
                row_number = None
                if r is not None:
                    if len(r) > 7 or not r.isascii() or not r.isdigit() or not 1 <= int(r) <= 1048576:
                        self.finding("error", "invalid-row-index", name, loc + "/@r", "Row index is outside the worksheet range.")
                    else:
                        row_number = int(r)
                        if row_number <= previous_row:
                            self.finding("error", "row-order", name, loc, "Explicit row indexes are duplicated or out of order.")
                        previous_row = row_number
                last_column = 0
                for ci, cell in enumerate(row.findall(f"{{{ns}}}c"), 1):
                    cloc = loc + f"/c[{ci}]"
                    ref = cell.get("r")
                    if ref is not None:
                        match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", ref)
                        if not match:
                            self.finding("error", "invalid-cell-reference", name, cloc + "/@r", "Cell reference is malformed.")
                        else:
                            column = 0
                            for letter in match[1]:
                                column = column * 26 + ord(letter) - 64
                            cell_row = int(match[2])
                            if column > 16384 or cell_row > 1048576 or (row_number is not None and cell_row != row_number):
                                self.finding("error", "cell-reference-range", name, cloc + "/@r", "Cell reference exceeds bounds or disagrees with its row.")
                            if column <= last_column:
                                self.finding("error", "cell-order", name, cloc, "Explicit cell columns are duplicated or out of order.")
                            last_column = column
                    formula = cell.find(f"{{{ns}}}f")
                    if formula is not None and (formula.text or "").startswith("="):
                        self.finding("error", "formula-leading-equals", name, cloc + "/f", "Stored formula text contains a leading equals sign.")
                    if cell.get("t") == "s":
                        value = cell.findtext(f"{{{ns}}}v", "")
                        if len(value) > 10 or not value.isascii() or not value.isdigit() or string_count is None or int(value) >= string_count:
                            self.finding("error", "shared-string-reference", name, cloc + "/v", "Shared-string index cannot be resolved to one available table.")

    def check_drawings(self):
        for name, root in sorted(self.trees.items()):
            ns, local = split_tag(root.tag)
            if local != "wsDr" or ns not in {
                "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
                "http://purl.oclc.org/ooxml/drawingml/spreadsheetDrawing",
            }:
                continue
            ids = []
            for anchor in root:
                if split_tag(anchor.tag)[1] not in {"oneCellAnchor", "twoCellAnchor", "absoluteAnchor"}:
                    continue
                ids.extend(e.get("id") for e in anchor.iter()
                           if split_tag(e.tag) == (ns, "cNvPr") and e.get("id") is not None)
            duplicates = sum(count - 1 for count in Counter(ids).values() if count > 1)
            if duplicates:
                self.finding("error", "duplicate-drawing-id", name, "//cNvPr/@id", "Drawing shape identifiers are duplicated across anchors.", duplicates)


def inspect_file(path: str | Path, limits: Limits | None = None) -> dict:
    return Inspector(Path(path), limits or Limits()).run()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    report = inspect_file(args.file)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
