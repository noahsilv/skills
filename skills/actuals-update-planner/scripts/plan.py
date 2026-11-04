#!/usr/bin/env python3
"""Build a source-linked actuals update plan; never save or recalculate a workbook."""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string, get_column_letter, range_boundaries


class InputError(ValueError):
    pass


def obj(value, keys, where):
    if type(value) is not dict or set(value) != set(keys):
        raise InputError(f"{where}: expected exactly fields {', '.join(sorted(keys))}")
    return value


def text(value, where):
    if type(value) is not str or not value.strip() or len(value) > 2000 or any(ord(c) < 32 for c in value):
        raise InputError(f"{where}: expected nonempty plain text (max 2000)")
    return value


def identifier(value, where):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", value):
        raise InputError(f"{where}: expected an identifier")
    return value


def integer(value, where, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise InputError(f"{where}: expected integer 1..{maximum}")
    return value


def decimal(value, where):
    if type(value) is not str or not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,23})(?:\.[0-9]{1,12})?", value):
        raise InputError(f"{where}: expected decimal string (24 integer / 12 fractional digits max)")
    return Decimal(value)


def array(value, where, minimum=1, maximum=1000):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise InputError(f"{where}: expected {minimum}..{maximum} entries")
    return value


def date_value(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise InputError("Period dates must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputError("Invalid calendar date") from exc


def period(value):
    obj(value, {"start", "end"}, "period")
    start, end = date_value(value["start"]), date_value(value["end"])
    if start > end or (end-start).days > 371:
        raise InputError("Period must be ordered and span at most 372 days")
    return start, end


def column(value):
    if type(value) is not str or not re.fullmatch("[A-Z]{1,3}", value) or column_index_from_string(value) > 16384:
        raise InputError("Invalid Excel column")
    return column_index_from_string(value)


def coordinate(value):
    if type(value) is not str or not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,6}", value):
        raise InputError("Invalid Excel coordinate")
    parts = re.fullmatch(r"([A-Z]+)([0-9]+)", value)
    column(parts[1])
    integer(int(parts[2]), "cell row", 1048576)
    return value


def hash_value(value):
    if type(value) is not str or not re.fullmatch("[a-f0-9]{64}", value):
        raise InputError("Expected lowercase SHA-256 digest")
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def loads(raw):
    try:
        return json.loads(raw, object_pairs_hook=no_duplicates,
                          parse_constant=lambda x: (_ for _ in ()).throw(InputError(f"Invalid JSON constant: {x}")))
    except InputError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InputError(f"Invalid UTF-8 JSON: {exc}") from exc


def unique(values, where):
    if len(values) != len(set(values)):
        raise InputError(f"{where}: duplicate entries")


def scale(value):
    if value not in ("1", "1000", "1000000", "1000000000"):
        raise InputError("Scale must be a decimal string: 1, 1000, 1000000 or 1000000000")
    return Decimal(value)


def currency(value):
    if type(value) is not str or not re.fullmatch("[A-Z]{3}", value):
        raise InputError("Currency must be an explicit three-letter code")


def quoted_sheet(name):
    return "'" + name.replace("'", "''") + "'"


def plain_number(cell, expected, where):
    if cell.data_type == "f" or type(cell.value) not in (int, float):
        raise InputError(f"{where}: must contain a numeric hardcode; formulas, booleans and blanks are protected")
    actual = Decimal(str(cell.value))
    if not actual.is_finite() or actual != decimal(expected, where + ".expected"):
        raise InputError(f"{where}: value differs from the mapped pre-update snapshot")
    return actual


def literal_text(cell, expected, where):
    if cell.data_type not in ("s", "inlineStr") or type(cell.value) is not str or cell.value != expected:
        raise InputError(f"{where}: expected matching literal text; formulas and error cells remain protected")


def evidence(reference, pages, where):
    obj(reference, {"page", "excerpt"}, where)
    page = integer(reference["page"], where + ".page", len(pages))
    excerpt = text(reference["excerpt"], where + ".excerpt")
    normalize = lambda s: " ".join(s.split())
    if normalize(excerpt) not in normalize(pages[page - 1]):
        raise InputError(f"{where}: excerpt absent from cited physical text page {page}")
    return excerpt


def validate_map(mapping):
    obj(mapping, {"schema_version", "entity", "scope", "model_sha256", "sheet", "model_context",
                  "label_column", "header_row", "target", "source_sheet", "forecast_columns",
                  "sources", "mappings", "excluded_rows"}, "mapping")
    if type(mapping["schema_version"]) is not int or mapping["schema_version"] != 1:
        raise InputError("schema_version: expected integer 1")
    text(mapping["entity"], "entity")
    if mapping["scope"] not in ("standalone", "consolidated"):
        raise InputError("scope: expected standalone or consolidated")
    hash_value(mapping["model_sha256"])
    text(mapping["sheet"], "sheet")
    context = obj(mapping["model_context"], {"entity_cell", "scope_cell", "unit_cell", "unit_label"}, "model_context")
    for key in ("entity_cell", "scope_cell", "unit_cell"):
        coordinate(context[key])
    unique([context[k] for k in ("entity_cell", "scope_cell", "unit_cell")], "model context cells")
    text(context["unit_label"], "unit_label")
    column(mapping["label_column"])
    header = integer(mapping["header_row"], "header_row", 10000)
    target = obj(mapping["target"], {"column", "expected_header", "actual_header", "period", "currency", "scale"}, "target")
    target_col = column(target["column"])
    if column(mapping["label_column"]) >= target_col:
        raise InputError("Label column must precede target column")
    for key in ("expected_header", "actual_header"):
        text(target[key], key)
    if target["expected_header"] == target["actual_header"]:
        raise InputError("Target header must change from its estimate label to a distinct actual label")
    period(target["period"])
    currency(target["currency"])
    scale(target["scale"])
    scale_labels = {"1": "units", "1000": "thousands", "1000000": "millions", "1000000000": "billions"}
    if context["unit_label"] != f"{target['currency']} {scale_labels[target['scale']]}":
        raise InputError("model_context.unit_label must match the target currency and scale, e.g. USD millions")
    if type(mapping["source_sheet"]) is not str or not re.fullmatch(r"[A-Za-z0-9 _-]{1,31}", mapping["source_sheet"]):
        raise InputError("source_sheet: use 1..31 ASCII letters, numbers, spaces, underscores or hyphens")
    for forecast in array(mapping["forecast_columns"], "forecast_columns", maximum=100):
        obj(forecast, {"column", "expected_header"}, "forecast column")
        if column(forecast["column"]) <= target_col:
            raise InputError("Forecast columns must follow the target column")
        text(forecast["expected_header"], "forecast.expected_header")
    unique([f["column"] for f in mapping["forecast_columns"]], "forecast_columns")
    for source in array(mapping["sources"], "sources", maximum=100):
        obj(source, {"id", "file", "sha256", "entity", "scope", "currency", "scale", "period",
                     "audit_status", "context_evidence", "audit_evidence"}, "source")
        identifier(source["id"], "source.id")
        if type(source["file"]) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.txt", source["file"]):
            raise InputError("Source file must be a plain .txt basename under --sources")
        hash_value(source["sha256"])
        if source["entity"] != mapping["entity"] or source["scope"] != mapping["scope"]:
            raise InputError("Source entity or scope differs from the model mapping")
        currency(source["currency"])
        if source["currency"] != target["currency"]:
            raise InputError("FX conversion is unsupported; source and model currency must agree")
        scale(source["scale"])
        period(source["period"])
        if source["audit_status"] not in ("audited", "unaudited", "interim"):
            raise InputError("Source audit_status must be explicit: audited, unaudited or interim")
    unique([s["id"] for s in mapping["sources"]], "sources.id")
    unique([s["file"] for s in mapping["sources"]], "sources.file")
    for item in array(mapping["mappings"], "mappings"):
        obj(item, {"id", "row", "label", "expected_estimate", "source_id", "source_label", "source_value",
                   "reported_as", "citation", "kind", "basis", "sign_multiplier", "prior_periods"}, "mapped input")
        identifier(item["id"], "mapping.id")
        if integer(item["row"], "mapping.row", 10000) <= header:
            raise InputError("Mapped rows must follow the header row")
        text(item["label"], "mapping.label")
        decimal(item["expected_estimate"], "expected_estimate")
        identifier(item["source_id"], "source_id")
        text(item["source_label"], "source_label")
        decimal(item["source_value"], "source_value")
        text(item["reported_as"], "reported_as")
        if item["kind"] not in ("flow", "stock") or item["basis"] not in ("standalone", "cumulative"):
            raise InputError("Only monetary flow/stock inputs with standalone/cumulative basis are supported")
        if type(item["sign_multiplier"]) is not int or item["sign_multiplier"] not in (-1, 1):
            raise InputError("sign_multiplier must be integer +1 or -1")
        priors = array(item["prior_periods"], "prior_periods", minimum=0, maximum=12)
        for prior in priors:
            obj(prior, {"column", "expected_header", "period", "expected_value"}, "prior period")
            if not column(mapping["label_column"]) < column(prior["column"]) < target_col:
                raise InputError("Prior columns must lie between label and target columns")
            text(prior["expected_header"], "prior.expected_header")
            period(prior["period"])
            decimal(prior["expected_value"], "prior.expected_value")
        unique([p["column"] for p in priors], "prior columns")
    unique([m["id"] for m in mapping["mappings"]], "mappings.id")
    unique([m["row"] for m in mapping["mappings"]], "mappings.row")
    for excluded in array(mapping["excluded_rows"], "excluded_rows", minimum=0):
        obj(excluded, {"row", "label", "reason"}, "excluded row")
        if integer(excluded["row"], "excluded.row", 10000) <= header:
            raise InputError("Excluded rows must follow the header row")
        text(excluded["label"], "excluded.label")
        text(excluded["reason"], "excluded.reason")
    unique([e["row"] for e in mapping["excluded_rows"]] + [m["row"] for m in mapping["mappings"]], "mapped and excluded rows")


def verify_sources(mapping, source_dir):
    loaded, snapshots = {}, {}
    base = Path(source_dir).resolve(strict=True)
    for source in mapping["sources"]:
        path = base / source["file"]
        if path.is_symlink() or path.resolve(strict=True).parent != base:
            raise InputError("Sources must be regular files immediately under --sources")
        raw = path.read_bytes()
        if len(raw) > 5_000_000:
            raise InputError("Source text exceeds 5 MB limit")
        if digest(raw) != source["sha256"]:
            raise InputError(f"Source hash changed: {source['id']}")
        try:
            pages = raw.decode("utf-8").split("\f")
        except UnicodeError as exc:
            raise InputError("Source must be UTF-8 text") from exc
        context = evidence(source["context_evidence"], pages, "source.context_evidence")
        for token in (source["entity"], source["scope"], source["currency"],
                      source["period"]["start"], source["period"]["end"]):
            if not re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", context):
                raise InputError("Source context excerpt must identify entity, scope, currency, scale and coverage dates")
        if not re.search(r"\bscale\s*[:=]?\s*" + re.escape(source["scale"]) + r"(?=$|[\s;])", context, flags=re.I):
            raise InputError("Source context excerpt must identify the complete scale declaration, e.g. scale 1000;")
        audit = evidence(source["audit_evidence"], pages, "source.audit_evidence")
        if not re.search(r"(?<![A-Za-z])" + re.escape(source["audit_status"]) + r"(?![A-Za-z])", audit, flags=re.I):
            raise InputError("Audit evidence must explicitly contain the declared status as a word")
        loaded[source["id"]] = (source, pages)
        snapshots[path] = raw
    return loaded, snapshots


def verify_worksheet_bounds(package, workbook):
    """Check real cell coordinates before trusting a reader's cached dimensions."""
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    total_area = 0
    for sheet in workbook.worksheets:
        # The supported openpyxl version exposes the actual relationship target
        # on its read-only worksheet, so custom worksheet part names are covered.
        raw = package.read(sheet._worksheet_path)
        if b"<!DOCTYPE" in raw.upper():
            raise InputError("Worksheet document-type declarations are unsupported")
        bounds = None
        positions, row_ids = set(), set()
        current_row = None
        max_row = max_col = 0
        try:
            for event, node in ET.iterparse(io.BytesIO(raw), events=("start", "end")):
                if event == "start" and node.tag == namespace + "dimension":
                    if bounds is not None:
                        raise InputError("Duplicate worksheet dimension declaration")
                    reference = node.attrib.get("ref", "")
                    for address in reference.split(":"):
                        coordinate(address)
                    if len(reference.split(":")) > 2:
                        raise InputError("Invalid worksheet dimension range")
                    bounds = range_boundaries(reference)
                elif event == "start" and node.tag == namespace + "row":
                    row_text = node.attrib.get("r", "")
                    if not re.fullmatch(r"[1-9][0-9]*", row_text):
                        raise InputError("Worksheet rows must have explicit positive indices")
                    current_row = integer(int(row_text), "worksheet row", 10000)
                    if current_row in row_ids:
                        raise InputError("Duplicate worksheet row index")
                    row_ids.add(current_row)
                elif event == "start" and node.tag == namespace + "c":
                    address = coordinate(node.attrib.get("r"))
                    col, row, _, _ = range_boundaries(address)
                    if row != current_row:
                        raise InputError("Worksheet cell row differs from its containing row")
                    if address in positions:
                        raise InputError("Duplicate worksheet cell coordinate")
                    positions.add(address)
                    if row > 10000 or col > 200:
                        raise InputError("Actual worksheet coordinates exceed the inspection limit")
                    max_row, max_col = max(max_row, row), max(max_col, col)
                    if bounds is None or not (bounds[0] <= col <= bounds[2] and bounds[1] <= row <= bounds[3]):
                        raise InputError("Actual worksheet cell falls outside declared dimensions")
                elif event == "end":
                    if node.tag == namespace + "row":
                        current_row = None
                    node.clear()
        except ET.ParseError as exc:
            raise InputError("Malformed worksheet XML") from exc
        if bounds is None or bounds[0] > bounds[2] or bounds[1] > bounds[3]:
            raise InputError("Missing or invalid worksheet dimensions")
        total_area += max_row * max_col
        if total_area > 250000:
            raise InputError("Actual worksheet cells exceed the 250000-cell inspection limit")


def build_plan(workbook, mapping, loaded):
    if mapping["sheet"] not in workbook.sheetnames:
        raise InputError("Mapped model sheet does not exist")
    if mapping["source_sheet"].casefold() in {s.casefold() for s in workbook.sheetnames}:
        raise InputError("Proposed source sheet already exists")
    if any(ws.max_row > 10000 or ws.max_column > 200 for ws in workbook.worksheets):
        raise InputError("Workbook exceeds bounded inspection limit: 10000 rows / 200 columns per sheet")
    if sum(ws.max_row * ws.max_column for ws in workbook.worksheets) > 250000:
        raise InputError("Workbook exceeds 250000-cell inspection limit")
    ws = workbook[mapping["sheet"]]
    cells = {cell.coordinate: cell for row in ws.iter_rows() for cell in row if cell.value is not None}
    def cell(address):
        if address not in cells:
            raise InputError(f"Required workbook cell is blank: {ws.title}!{address}")
        return cells[address]
    ctx, target = mapping["model_context"], mapping["target"]
    for key, expected in (("entity_cell", mapping["entity"]), ("scope_cell", mapping["scope"]), ("unit_cell", ctx["unit_label"])):
        literal_text(cell(ctx[key]), expected, f"Model context {ctx[key]}")
    header_cell = f"{target['column']}{mapping['header_row']}"
    literal_text(cell(header_cell), target["expected_header"], "Target header")
    for forecast in mapping["forecast_columns"]:
        address = f"{forecast['column']}{mapping['header_row']}"
        literal_text(cell(address), forecast["expected_header"], "Forecast header")
    protected_formulas = []
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for current in row:
                if current.data_type == "f":
                    protected_formulas.append({"sheet": sheet.title, "cell": current.coordinate, "formula": str(current.value)})
    for excluded in mapping["excluded_rows"]:
        literal_text(cell(f"{mapping['label_column']}{excluded['row']}"), excluded["label"], "Excluded row label")
    accounted_rows = {item["row"] for item in mapping["mappings"] + mapping["excluded_rows"]}
    target_index = column(target["column"])
    numeric_rows = {c.row for c in cells.values() if c.column == target_index and c.row > mapping["header_row"] and type(c.value) in (int, float)}
    if numeric_rows - accounted_rows:
        raise InputError(f"Unmapped target hardcodes require explicit exclusions: rows {sorted(numeric_rows - accounted_rows)}")
    result = {"schema_version": 1, "status": "PLAN_READY", "workbook_mutated": False, "recalculated": False,
              "entity": mapping["entity"], "scope": mapping["scope"], "period": target["period"],
              "currency": target["currency"], "scale": target["scale"], "model_sheet": ws.title,
              "source_sheet": mapping["source_sheet"], "sources": mapping["sources"],
              "evidence_limits": "Text excerpts and hashes verified. Source authenticity, audit opinion and original PDF-to-text transcription are not authenticated.",
              "coverage": {"mapped_inputs": len(mapping["mappings"]), "target_numeric_inputs": len(numeric_rows),
                           "excluded_rows": mapping["excluded_rows"], "unused_source_ids": sorted(set(loaded) - {m["source_id"] for m in mapping["mappings"]})},
              "protected": {"rule": "All existing cells except the enumerated proposed model edits remain protected; every existing formula remains protected.",
                            "forecast_columns": mapping["forecast_columns"], "formulas": protected_formulas},
              "proposed_source_cells": [], "proposed_model_edits": [], "variances": []}
    def source_cell(address, kind, value):
        result["proposed_source_cells"].append({"sheet": mapping["source_sheet"], "cell": address, "kind": kind, "value": value})
    source_cell("A1", "text", "Reported actuals, conversion, estimate snapshot and variance")
    for i, title in enumerate(("Line", "Reported value", "Conversion factor", "Converted reported", "Prior actuals", "Standalone actual", "Estimate snapshot", "Variance", "Variance %", "Citation"), 1):
        source_cell(f"{get_column_letter(i)}2", "text", title)
    start, end = period(target["period"])
    with localcontext() as context:
        context.prec, context.rounding = 80, ROUND_HALF_EVEN
        for source_row, item in enumerate(mapping["mappings"], 3):
            address = f"{target['column']}{item['row']}"
            if address in (ctx["entity_cell"], ctx["scope_cell"], ctx["unit_cell"], header_cell):
                raise InputError("Mapped edit overlaps a context or header cell")
            literal_text(cell(f"{mapping['label_column']}{item['row']}"), item["label"], "Model row label")
            estimate = plain_number(cell(address), item["expected_estimate"], address)
            if item["source_id"] not in loaded:
                raise InputError(f"Unknown source ID: {item['source_id']}")
            source, pages = loaded[item["source_id"]]
            excerpt = evidence(item["citation"], pages, item["id"] + ".citation")
            if item["source_label"] not in excerpt:
                raise InputError("Source label is absent from cited excerpt")
            printed = item["reported_as"]
            if not re.fullmatch(r"-?(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)(?:\.[0-9]+)?|\((?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)(?:\.[0-9]+)?\)", printed):
                raise InputError("reported_as must be a plain number, optionally grouped or parenthesized")
            if not re.search(r"(?<![0-9.,()\-])" + re.escape(printed) + r"(?![0-9.,()])", excerpt):
                raise InputError("Printed value is not a complete number in the cited excerpt")
            if not re.search(re.escape(item["source_label"]) + r"\s*[:|]?\s+" + re.escape(printed) + r"(?![0-9.,()])", excerpt):
                raise InputError("Printed value must immediately follow its source label in the cited text row")
            parsed = "-" + printed[1:-1] if printed.startswith("(") else printed
            if decimal(parsed.replace(",", ""), "reported_as") != decimal(item["source_value"], "source_value"):
                raise InputError("Printed number differs from source_value")
            source_start, source_end = period(source["period"])
            if source_end != end:
                raise InputError("Source end date differs from target end date")
            prior_values, prior_cells = [], []
            if item["basis"] == "standalone":
                if item["prior_periods"] or (item["kind"] == "flow" and source_start != start):
                    raise InputError("Standalone flow requires the exact target coverage and no prior deductions")
            else:
                if item["kind"] != "flow" or source_start >= start or not item["prior_periods"]:
                    raise InputError("Cumulative subtraction requires an additive flow and earlier covered periods")
                cursor = source_start
                for prior in sorted(item["prior_periods"], key=lambda p: p["period"]["start"]):
                    pstart, pend = period(prior["period"])
                    if pstart != cursor or pend >= start:
                        raise InputError("Prior periods must partition the cumulative period without overlaps or gaps")
                    cursor = pend + timedelta(days=1)
                    literal_text(cell(f"{prior['column']}{mapping['header_row']}"), prior["expected_header"], "Prior header")
                    prior_address = f"{prior['column']}{item['row']}"
                    prior_values.append(plain_number(cell(prior_address), prior["expected_value"], prior_address))
                    prior_cells.append(f"{quoted_sheet(ws.title)}!{prior_address}")
                if cursor != start:
                    raise InputError("Prior periods do not fully bridge source start to target start")
            factor = scale(source["scale"]) / scale(target["scale"]) * item["sign_multiplier"]
            converted = decimal(item["source_value"], "source_value") * factor
            actual = converted - sum(prior_values, Decimal(0))
            delta = actual - estimate
            pct = None if estimate == 0 else (delta / abs(estimate) * 100).quantize(Decimal("0.000001"))
            citation = f"{source['file']} | physical text page {item['citation']['page']} | {excerpt}"
            content = {"A": ("text", item["label"]), "B": ("number", item["source_value"]),
                       "C": ("number", format(factor, "f")), "D": ("formula", f"=B{source_row}*C{source_row}"),
                       "E": ("formula", "=" + "+".join(prior_cells) if prior_cells else "=0"),
                       "F": ("formula", f"=D{source_row}-E{source_row}"), "G": ("number", format(estimate, "f")),
                       "H": ("formula", f"=F{source_row}-G{source_row}"),
                       "I": ("formula", f'=IF(G{source_row}=0,"undefined",H{source_row}/ABS(G{source_row})*100)'),
                       "J": ("text", citation)}
            for col, (kind, value) in content.items():
                source_cell(f"{col}{source_row}", kind, value)
            result["proposed_model_edits"].append({"sheet": ws.title, "cell": address, "before_kind": "number", "before": format(estimate, "f"),
                                                    "after_kind": "formula", "after": f"={quoted_sheet(mapping['source_sheet'])}!F{source_row}",
                                                    "prospective_value": format(actual, "f"), "mapping_id": item["id"]})
            result["variances"].append({"id": item["id"], "label": item["label"], "model_cell": address,
                                        "estimate": format(estimate, "f"), "actual": format(actual, "f"),
                                        "delta": format(delta, "f"), "variance_percent": None if pct is None else format(pct, "f"),
                                        "percent_status": "ZERO_ESTIMATE" if pct is None else "CALCULATED",
                                        "source_id": item["source_id"], "citation": item["citation"],
                                        "source_value": item["source_value"], "conversion_factor": format(factor, "f"),
                                        "basis": item["basis"], "prior_cells": prior_cells,
                                        "prior_values": [format(p, "f") for p in prior_values]})
    if header_cell in (ctx["entity_cell"], ctx["scope_cell"], ctx["unit_cell"]):
        raise InputError("Header edit overlaps protected model context")
    result["proposed_model_edits"].append({"sheet": ws.title, "cell": header_cell, "before_kind": "text", "before": target["expected_header"],
                                            "after_kind": "text", "after": target["actual_header"]})
    edits = {(edit["sheet"], edit["cell"]) for edit in result["proposed_model_edits"]}
    if edits & {(item["sheet"], item["cell"]) for item in protected_formulas}:
        raise InputError("Proposed edits overlap protected formulas")
    return result


def clean(value):
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", " ")


def markdown(report):
    lines = ["# Actuals update plan", "", "Status: **PLAN_READY — review required before application**.", "",
             "No workbook was changed or recalculated. The amounts below were computed from the declared inputs using decimal arithmetic; forecast and calculated-row effects are unknown.",
             f"{clean(report['entity'])}; {report['scope']}; {report['period']['start']} to {report['period']['end']}; {report['currency']} scale {report['scale']}.",
             clean(report["evidence_limits"]), "", "## Proposed model edits", "",
             "| Sheet / cell | Before | Proposed value / formula |", "|---|---|---|"]
    for edit in report["proposed_model_edits"]:
        lines.append(f"| {clean(edit['sheet'])}!{edit['cell']} | {clean(edit['before'])} | {clean(edit['after'])} |")
    lines += ["", f"Create source sheet `{report['source_sheet']}` only after review. The complete typed cell instructions, including estimate snapshots and citations, are in plan.json/proposed_source_cells.", "",
              "## Input variances", "", "Percent = (actual − estimate) / abs(estimate) × 100; a zero estimate gives an undefined percentage. Positive does not imply favorable.", "",
              "| Line | Estimate | Actual | Delta | Variance % | Evidence |", "|---|---:|---:|---:|---:|---|"]
    source_by_id = {s["id"]: s for s in report["sources"]}
    for row in report["variances"]:
        source = source_by_id[row["source_id"]]
        citation = f"{source['file']} p. {row['citation']['page']}: {row['citation']['excerpt']}"
        lines.append(f"| {clean(row['label'])} | {row['estimate']} | {row['actual']} | {row['delta']} | {row['variance_percent'] if row['variance_percent'] is not None else 'undefined (zero estimate)'} | {clean(citation)} |")
    lines += ["", "## Protection and coverage", "", clean(report["protected"]["rule"]),
              f"Mapped inputs: {report['coverage']['mapped_inputs']}. Target numeric hardcodes: {report['coverage']['target_numeric_inputs']}. Protected existing formulas: {len(report['protected']['formulas'])}.",
              "Declared forecast columns: " + ", ".join(f"{x['column']} ({clean(x['expected_header'])})" for x in report['protected']['forecast_columns']) + ".",
              "", "Excluded rows:", ""]
    for excluded in report["coverage"]["excluded_rows"]:
        lines.append(f"- Row {excluded['row']}, {clean(excluded['label'])}: {clean(excluded['reason'])}")
    if not report["coverage"]["excluded_rows"]:
        lines.append("- None.")
    lines += ["", "Declared source status:", ""]
    for source in report["sources"]:
        lines.append(f"- {clean(source['id'])}: {source['audit_status']}; {clean(source['file'])}; SHA-256 {source['sha256']}.")
    lines += ["", "Before applying: inspect the original audited report and the chosen source vintage, resolve exclusions, confirm period and sign conventions, and verify that current file hashes and cell contents still match this plan. Prior-period deductions use existing model hardcodes; their source accuracy requires separate review.",
              "Apply only in an authorized copy using a suitable spreadsheet application. Recalculate there, verify the source links and changed period label, compare protected formulas/forecast inputs, and reconcile the completed workbook to the statements. This helper performs none of those application or post-change checks.", ""]
    return "\n".join(lines)


def run(model_path, map_path, source_dir, output_dir):
    model_path, map_path, output_dir = Path(model_path), Path(map_path), Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise InputError("Output directory must be new; existing plans are never overwritten")
    if model_path.suffix.lower() != ".xlsx":
        raise InputError("This bounded reader accepts .xlsx only")
    model_raw, map_raw = model_path.read_bytes(), map_path.read_bytes()
    if len(model_raw) > 25_000_000 or len(map_raw) > 5_000_000:
        raise InputError("Input exceeds 25 MB workbook / 5 MB map limit")
    mapping = loads(map_raw)
    validate_map(mapping)
    if digest(model_raw) != mapping["model_sha256"]:
        raise InputError("Model hash differs from the workbook used to prepare the map")
    loaded, snapshots = verify_sources(mapping, source_dir)
    try:
        with zipfile.ZipFile(io.BytesIO(model_raw)) as package:
            names = [item.filename for item in package.infolist()]
            if len(names) != len(set(names)):
                raise InputError("Duplicate workbook package members")
            if sum(item.file_size for item in package.infolist()) > 100_000_000:
                raise InputError("Workbook package expands beyond 100 MB")
            workbook = load_workbook(io.BytesIO(model_raw), read_only=True, data_only=False, keep_links=False)
            try:
                verify_worksheet_bounds(package, workbook)
                report = build_plan(workbook, mapping, loaded)
            finally:
                workbook.close()
    except (zipfile.BadZipFile, KeyError, ValueError, TypeError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError(f"Unreadable or unsupported workbook: {exc}") from exc
    snapshots.update({model_path: model_raw, map_path: map_raw})
    for path, raw in snapshots.items():
        if path.read_bytes() != raw:
            raise InputError(f"Input changed while planning: {path.name}")
    report["inputs"] = {"model": {"file": model_path.name, "sha256": digest(model_raw)},
                        "mapping": {"file": map_path.name, "sha256": digest(map_raw)}}
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "plan.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / "plan.md").write_text(markdown(report), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--sources", required=True)
    parser.add_argument("--out", required=True, help="New output directory")
    args = parser.parse_args(argv)
    try:
        report = run(args.model, args.mapping, args.sources, args.out)
    except (InputError, OSError) as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 2
    print(f"PLAN_READY: {report['coverage']['mapped_inputs']} input edits; {Path(args.out) / 'plan.md'}; workbook untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
