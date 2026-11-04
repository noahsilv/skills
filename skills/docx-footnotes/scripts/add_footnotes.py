#!/usr/bin/env python3
"""Insert plain-text native footnotes at explicit markers in a .docx copy.

Standard library only. This edits supported package structure; it does not
validate rendering, remove sensitive content, or execute document content.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from urllib.parse import unquote, urlsplit
from xml.dom import Node, minidom
import zipfile
import zlib

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
MAIN_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
FN_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
REL_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
MAIN = "word/document.xml"
RELS = "word/_rels/document.xml.rels"
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_PART = 32 * 1024 * 1024
MAX_MEMBERS = 2048
XML_SPACE = "http://www.w3.org/XML/1998/namespace"


class DocumentError(ValueError):
    """The input or requested edit is outside this helper's supported scope."""


def elements(node):
    return [c for c in node.childNodes if c.nodeType == Node.ELEMENT_NODE]


def matches(node, namespace, local):
    return node.nodeType == Node.ELEMENT_NODE and node.namespaceURI == namespace and node.localName == local


def text(node):
    return "".join(c.data for c in node.childNodes if c.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE))


def parse_xml(data, name):
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentError(f"{name}: only UTF-8 XML is supported") from exc
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", decoded, re.I):
        raise DocumentError(f"{name}: DTD/entity declarations are unsupported")
    declaration = re.match(r"\s*<\?xml\b[^?]*encoding\s*=\s*['\"]([^'\"]+)", decoded)
    if declaration and declaration.group(1).lower().replace("-", "") != "utf8":
        raise DocumentError(f"{name}: only UTF-8 XML is supported")
    try:
        doc = minidom.parseString(decoded)
        stack, count = [(doc.documentElement, 0)], 0
        while stack:
            node, depth = stack.pop()
            count += 1
            if depth > 128 or count > 250000:
                raise DocumentError(f"{name}: XML depth or node limit exceeded")
            stack.extend((child, depth + 1) for child in node.childNodes)
        return doc
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError(f"{name}: malformed XML") from exc


def part_target(base, target):
    try:
        parsed = urlsplit(target)
    except ValueError as exc:
        raise DocumentError("Malformed relationship target") from exc
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in target:
        raise DocumentError("Unsupported relationship target")
    value = unquote(parsed.path)
    parts = (PurePosixPath(base).parent / value).parts if not value.startswith("/") else PurePosixPath(value[1:]).parts
    if not parts or any(p in (".", "..") for p in parts):
        raise DocumentError("Noncanonical relationship target")
    return "/".join(parts)


def load_package(path):
    if path.suffix.lower() != ".docx" or path.stat().st_size > MAX_FILE:
        raise DocumentError("Expected a .docx of at most 64 MiB")
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_TOTAL:
                raise DocumentError("ZIP member count or expanded size limit exceeded")
            names, data = set(), {}
            for info in infos:
                n = info.filename
                if (not n or n.startswith("/") or "\\" in n or "\x00" in info.orig_filename
                        or any(p in (".", "..", "") for p in n.rstrip("/").split("/"))
                        or ":" in n or n.casefold() in names):
                    raise DocumentError("Duplicate or unsafe ZIP member name")
                names.add(n.casefold())
                if info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16):
                    raise DocumentError("Encrypted or symlink ZIP members are unsupported")
                if info.file_size > MAX_PART or info.file_size > max(1, info.compress_size) * 500:
                    raise DocumentError("ZIP member size or compression-ratio limit exceeded")
                if "vbaproject" in n.casefold() or n.casefold().startswith("_xmlsignatures/"):
                    raise DocumentError("Macros and signed packages are unsupported")
                data[n] = z.read(info)
            return infos, data
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error, EOFError) as exc:
        raise DocumentError("Unreadable or unsupported ZIP package") from exc


def add_element(doc, parent, namespace, name, attributes=None):
    if ":" not in name and doc.documentElement.prefix:
        name = doc.documentElement.prefix + ":" + name
    node = doc.createElementNS(namespace, name)
    for key, value in (attributes or {}).items():
        if key.startswith("w:"):
            node.setAttributeNS(W, key, str(value))
        else:
            node.setAttribute(key, str(value))
    parent.appendChild(node)
    return node


def bind_word_prefix(doc):
    existing = doc.documentElement.getAttribute("xmlns:w")
    if existing and existing != W:
        raise DocumentError("The w prefix is bound to an unsupported namespace")
    doc.documentElement.setAttribute("xmlns:w", W)


def relationships(doc):
    if not matches(doc.documentElement, R, "Relationships"):
        raise DocumentError("Unsupported relationships document")
    rels = elements(doc.documentElement)
    if any(not matches(r, R, "Relationship") for r in rels):
        raise DocumentError("Unsupported relationship element")
    ids = [r.getAttribute("Id") for r in rels]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        raise DocumentError("Missing or duplicate relationship ID")
    return rels


def note_ids(fn):
    result = {}
    for node in elements(fn.documentElement):
        if not matches(node, W, "footnote"):
            raise DocumentError("Unexpected element in footnotes part")
        raw = node.getAttributeNS(W, "id")
        if not re.fullmatch(r"-?[0-9]{1,10}", raw):
            raise DocumentError("Invalid footnote ID")
        ident = int(raw)
        if not -(2 ** 31) <= ident < 2 ** 31:
            raise DocumentError("Footnote ID exceeds the supported signed integer range")
        if ident in result:
            raise DocumentError("Duplicate footnote ID")
        kind = node.getAttributeNS(W, "type") or "normal"
        if kind not in ("normal", "separator", "continuationSeparator", "continuationNotice"):
            raise DocumentError("Unsupported footnote type")
        if kind == "normal" and ident < 0:
            raise DocumentError("Negative ordinary footnote ID")
        result[ident] = kind
    return result


def validate_references(document, fn):
    ids = note_ids(fn)
    refs = []
    for ref in document.getElementsByTagNameNS(W, "footnoteReference"):
        raw = ref.getAttributeNS(W, "id")
        if not re.fullmatch(r"[0-9]{1,10}", raw):
            raise DocumentError("Invalid body footnote reference")
        ident = int(raw)
        if ident >= 2 ** 31:
            raise DocumentError("Body footnote reference exceeds the supported integer range")
        refs.append(ident)
    normal = {i for i, kind in ids.items() if kind == "normal"}
    if len(refs) != len(set(refs)) or set(refs) != normal:
        raise DocumentError("Existing notes and body references are not one-to-one")
    return ids


def prepare_notes(notes):
    if not isinstance(notes, list) or not 1 <= len(notes) <= 100:
        raise DocumentError("Supply between 1 and 100 note objects")
    result = {}
    for note in notes:
        if not isinstance(note, dict) or set(note) != {"marker", "text"}:
            raise DocumentError("Each note requires exactly marker and text")
        marker, content = note["marker"], note["text"]
        if not isinstance(marker, str) or not re.fullmatch(r"\[\[fn:[A-Za-z0-9_-]{1,64}\]\]", marker):
            raise DocumentError("Marker must match [[fn:identifier]]")
        if marker in result:
            raise DocumentError("Duplicate requested marker")
        if not isinstance(content, str) or not content.strip() or len(content) > 10000:
            raise DocumentError("Footnote text must be nonempty and at most 10000 characters")
        if any(ord(c) < 32 and c not in "\n\t\r" for c in content) or any(0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in content):
            raise DocumentError("Footnote text contains invalid XML characters")
        result[marker] = content
    return result


def insert_footnotes(source, destination, notes):
    source, destination = Path(source), Path(destination)
    requested = prepare_notes(notes)
    if destination.suffix.lower() != ".docx":
        raise DocumentError("Output must use the .docx extension")
    if source.resolve() == destination.resolve() or destination.exists() or destination.is_symlink():
        raise DocumentError("Output must be a new file, distinct from the input")
    infos, payload = load_package(source)
    required = {MAIN, "[Content_Types].xml", "_rels/.rels"}
    if not required <= payload.keys():
        raise DocumentError("Required package parts are missing")
    xml = {name: parse_xml(data, name) for name, data in payload.items()
           if name.lower().endswith((".xml", ".rels"))}
    for name, doc in xml.items():
        for node in doc.getElementsByTagNameNS(W, "*"):
            if node.localName in {"ins", "del", "moveFrom", "moveTo", "moveFromRangeStart", "moveToRangeStart", "trackRevisions"} or node.localName.endswith("Change"):
                raise DocumentError("Tracked changes are unsupported; resolve them in an editor first")
        if name != MAIN and doc.getElementsByTagNameNS(W, "footnoteReference"):
            raise DocumentError("Footnote references outside the main document are unsupported")
    root_rels = relationships(xml["_rels/.rels"])
    main_rels = [r for r in root_rels if r.getAttribute("Type") == OFFICE + "officeDocument"]
    if len(main_rels) != 1 or main_rels[0].getAttribute("TargetMode") == "External" or part_target("root.xml", main_rels[0].getAttribute("Target")) != MAIN:
        raise DocumentError("Only a conventional Transitional Word main part is supported")
    document, types = xml[MAIN], xml["[Content_Types].xml"]
    if not matches(document.documentElement, W, "document") or not matches(types.documentElement, CT, "Types"):
        raise DocumentError("Only Transitional WordprocessingML is supported")
    bodies = [n for n in elements(document.documentElement) if matches(n, W, "body")]
    if len(bodies) != 1:
        raise DocumentError("Expected exactly one main document body")
    overrides, defaults = {}, {}
    for item in elements(types.documentElement):
        if matches(item, CT, "Override"):
            part = item.getAttribute("PartName")
            if part in overrides:
                raise DocumentError("Duplicate content-type override")
            overrides[part] = item.getAttribute("ContentType")
        elif matches(item, CT, "Default"):
            extension = item.getAttribute("Extension").lower()
            if not extension or extension in defaults:
                raise DocumentError("Missing or duplicate default content-type extension")
            defaults[extension] = item.getAttribute("ContentType")
        else:
            raise DocumentError("Unsupported content-type element")
        if "macroEnabled" in item.getAttribute("ContentType") or "digital-signature" in item.getAttribute("ContentType"):
            raise DocumentError("Macros and signed packages are unsupported")
    if overrides.get("/" + MAIN) != MAIN_TYPE:
        raise DocumentError("Unsupported main document content type")
    for name in payload:
        if name.lower().endswith(".rels") and overrides.get("/" + name, defaults.get("rels")) != REL_TYPE:
            raise DocumentError("A relationships part has no valid content-type declaration")
    if RELS not in payload and overrides.get("/" + RELS, defaults.get("rels")) != REL_TYPE:
        if "/" + RELS in overrides:
            raise DocumentError("Conflicting content type for the new relationships part")
        add_element(types, types.documentElement, CT, "Override", {"PartName": "/" + RELS, "ContentType": REL_TYPE})
        overrides["/" + RELS] = REL_TYPE
    rel_doc = xml.get(RELS) or parse_xml(f'<Relationships xmlns="{R}"/>'.encode(), RELS)
    rels = relationships(rel_doc)
    fn_rels = [r for r in rels if r.getAttribute("Type") == OFFICE + "footnotes"]
    if len(fn_rels) > 1:
        raise DocumentError("Multiple footnote relationships")
    if fn_rels:
        rel = fn_rels[0]
        if rel.getAttribute("TargetMode") == "External":
            raise DocumentError("External footnotes part is unsupported")
        fn_name = part_target(MAIN, rel.getAttribute("Target"))
        if fn_name not in xml or overrides.get("/" + fn_name) != FN_TYPE:
            raise DocumentError("Footnotes part or content type is missing")
        fn = xml[fn_name]
        if not matches(fn.documentElement, W, "footnotes"):
            raise DocumentError("Invalid footnotes part")
    else:
        fn_name = "word/footnotes.xml"
        if fn_name in payload or any(t == FN_TYPE for t in overrides.values()):
            raise DocumentError("Unlinked footnotes part already exists")
        fn = parse_xml(f'<w:footnotes xmlns:w="{W}"/>'.encode(), fn_name)
        for ident, kind in ((-1, "separator"), (0, "continuationSeparator")):
            entry = add_element(fn, fn.documentElement, W, "w:footnote", {"w:id": ident, "w:type": kind})
            p = add_element(fn, entry, W, "w:p")
            r = add_element(fn, p, W, "w:r")
            add_element(fn, r, W, "w:" + kind)
        existing = {r.getAttribute("Id") for r in rels}
        number = 1
        while f"rId{number}" in existing:
            number += 1
        add_element(rel_doc, rel_doc.documentElement, R, "Relationship", {"Id": f"rId{number}", "Type": OFFICE + "footnotes", "Target": "footnotes.xml"})
        add_element(types, types.documentElement, CT, "Override", {"PartName": "/" + fn_name, "ContentType": FN_TYPE})
    ids = validate_references(document, fn)
    bind_word_prefix(document)
    bind_word_prefix(fn)
    occurrences = {marker: [] for marker in requested}
    joined_text = "".join(text(n) for n in document.getElementsByTagNameNS(W, "t"))
    for node in document.getElementsByTagNameNS(W, "t"):
        value = text(node)
        for marker in requested:
            if marker in value:
                occurrences[marker].append(node)
    for marker, nodes in occurrences.items():
        if len(nodes) != 1 or text(nodes[0]) != marker or joined_text.count(marker) != 1:
            raise DocumentError(f"Marker {marker} must occur once in a standalone text run")
        node, run = nodes[0], nodes[0].parentNode
        if (not matches(run, W, "r") or not matches(run.parentNode, W, "p")
                or any(c is not node and not matches(c, W, "rPr") for c in elements(run))):
            raise DocumentError(f"Marker {marker} must be in a plain paragraph run")
        if run.parentNode.getElementsByTagNameNS(W, "fldChar") or run.parentNode.getElementsByTagNameNS(W, "instrText"):
            raise DocumentError("Markers in paragraphs with complex fields are unsupported")
        ancestor, in_body = run.parentNode, False
        while ancestor is not document.documentElement:
            in_body = in_body or ancestor is bodies[0]
            if matches(ancestor, W, "txbxContent") or matches(ancestor, W, "sdt") or ancestor.namespaceURI == "http://schemas.openxmlformats.org/markup-compatibility/2006":
                raise DocumentError("Markers in text boxes, content controls or alternate content are unsupported")
            ancestor = ancestor.parentNode
            if ancestor is None:
                raise DocumentError("Marker is outside the document body")
        if not in_body:
            raise DocumentError("Marker is outside the document body")
    next_id = max([0, *ids]) + 1
    if next_id + len(requested) - 1 >= 2 ** 31:
        raise DocumentError("No supported footnote ID range remains")
    inserted = []
    for node in list(document.getElementsByTagNameNS(W, "t")):
        marker = text(node)
        if marker not in requested:
            continue
        old_run = node.parentNode
        run = document.createElementNS(W, "w:r")
        # A paragraph may locally rebind w even when the document root does
        # not. Bind it on the new subtree so its serialized meaning is fixed.
        run.setAttribute("xmlns:w", W)
        props = add_element(document, run, W, "w:rPr")
        add_element(document, props, W, "w:vertAlign", {"w:val": "superscript"})
        add_element(document, run, W, "w:footnoteReference", {"w:id": next_id})
        old_run.parentNode.replaceChild(run, old_run)
        entry = add_element(fn, fn.documentElement, W, "w:footnote", {"w:id": next_id})
        p = add_element(fn, entry, W, "w:p")
        mark_run = add_element(fn, p, W, "w:r")
        mark_props = add_element(fn, mark_run, W, "w:rPr")
        add_element(fn, mark_props, W, "w:sz", {"w:val": "20"})
        add_element(fn, mark_props, W, "w:vertAlign", {"w:val": "superscript"})
        add_element(fn, mark_run, W, "w:footnoteRef")
        words_run = add_element(fn, p, W, "w:r")
        word_props = add_element(fn, words_run, W, "w:rPr")
        add_element(fn, word_props, W, "w:sz", {"w:val": "20"})
        content = add_element(fn, words_run, W, "w:t")
        content.setAttributeNS(XML_SPACE, "xml:space", "preserve")
        content.appendChild(fn.createTextNode(" " + requested[marker]))
        inserted.append({"marker": marker, "footnote_id": next_id})
        next_id += 1
    validate_references(document, fn)
    changes = {MAIN: document.toxml(encoding="utf-8"), fn_name: fn.toxml(encoding="utf-8"), RELS: rel_doc.toxml(encoding="utf-8"), "[Content_Types].xml": types.toxml(encoding="utf-8")}
    # Check the serialized bytes, not only namespace-aware in-memory nodes.
    reparsed = {name: parse_xml(data, name) for name, data in changes.items()}
    validate_references(reparsed[MAIN], reparsed[fn_name])
    relationships(reparsed[RELS])
    # Publish an already complete file with an atomic, no-replace hard link.
    # The temporary file is on the destination filesystem. No overwrite path
    # exists, including when another process creates destination during work.
    temporary, warnings = None, []
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".footnotes-", suffix=".tmp", delete=False) as out:
            temporary = Path(out.name)
        with zipfile.ZipFile(temporary, "w") as z:
            for info in infos:
                z.writestr(info, changes.pop(info.filename, payload[info.filename]))
            for name, data in changes.items():
                z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
        with temporary.open("rb") as out:
            os.fsync(out.fileno())
        os.link(temporary, destination)
    except BaseException as exc:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                exc.add_note(f"Temporary file could not be removed: {temporary}")
        raise
    try:
        temporary.unlink(missing_ok=True)
    except OSError:
        # The new output already exists. Preserve the success result and
        # disclose the leftover temporary hard link rather than claim failure.
        warnings.append({"code": "TEMPORARY_CLEANUP_FAILED", "path": str(temporary)})
    return {"status": "STRUCTURALLY_CHECKED", "inserted": inserted, "count": len(inserted), "visual_validation": "NOT_RUN", "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--notes", type=Path, required=True, help="JSON array of marker/text objects")
    args = parser.parse_args()
    try:
        if args.notes.stat().st_size > 2 * 1024 * 1024:
            raise DocumentError("Notes JSON exceeds 2 MiB")
        notes = json.loads(args.notes.read_text(encoding="utf-8"))
        result = insert_footnotes(args.source, args.destination, notes)
    except (ValueError, OSError, RecursionError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc), "warnings": getattr(exc, "__notes__", [])}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
