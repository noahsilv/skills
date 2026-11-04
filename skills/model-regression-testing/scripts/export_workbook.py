#!/usr/bin/env python3
"""Export an explicit XLSX watch list to a new regression snapshot; no calculation."""

import argparse
from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
import re
import sys

from openpyxl import load_workbook
from openpyxl.utils.cell import coordinate_to_tuple

from regression import ContractError, fields, kind, label, parse_json, validate_snapshot


def export_snapshot(workbook, watch, name, allow_cached=False):
    fields(watch, {"schema_version", "items"}, set(), "watch list")
    if type(watch["schema_version"]) is not int or watch["schema_version"] != 1:
        raise ContractError("watch schema_version must be 1")
    if not isinstance(watch["items"], list) or not watch["items"]:
        raise ContractError("watch items must be nonempty")
    label(name, "snapshot label")
    ids, endpoints = set(), set()
    for point in watch["items"]:
        fields(point, {"id", "sheet", "cell", "unit", "period"}, set(), "watch item")
        for key in point:
            label(point[key], key)
        if point["id"] in ids or (point["sheet"], point["cell"]) in endpoints:
            raise ContractError("duplicate watch id or cell")
        ids.add(point["id"])
        endpoints.add((point["sheet"], point["cell"]))
        if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,6}", point["cell"]):
            raise ContractError("watch cells must be single uppercase A1 addresses")
        row, col = coordinate_to_tuple(point["cell"])
        if row > 1048576 or col > 16384:
            raise ContractError("cell outside XLSX bounds")
    path = Path(workbook)
    if path.suffix.lower() != ".xlsx":
        raise ContractError("only .xlsx files are supported")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    books = []
    items, cached_used = [], False
    try:
        books.append(load_workbook(path, read_only=True, data_only=False))
        books.append(load_workbook(path, read_only=True, data_only=True))
        for point in watch["items"]:
            if point["sheet"] not in books[0].sheetnames:
                raise ContractError(f"missing sheet for {point['id']}")
            cell = books[0][point["sheet"]][point["cell"]]
            if cell.data_type == "f":
                if not allow_cached:
                    raise ContractError("formula requires --allow-cached-values; no recalculation is performed")
                cell = books[1][point["sheet"]][point["cell"]]
                cached_used = True
            if cell.data_type == "e" or cell.value is None:
                raise ContractError(f"missing value/cache or spreadsheet error for {point['id']}")
            if isinstance(cell.value, (datetime, date, time)):
                raise ContractError("date/time export is unsupported; normalize explicitly in JSON with a declared unit")
            kind(cell.value)
            items.append({"id": point["id"], "value": cell.value, "unit": point["unit"], "period": point["period"]})
    finally:
        for book in books:
            book.close()
    if before != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ContractError("input workbook changed during export")
    snapshot = {"schema_version": 1, "label": name, "source_sha256": before,
                "value_basis": "saved_formula_cache" if cached_used else "literal", "items": items}
    validate_snapshot(snapshot)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook")
    parser.add_argument("--watch", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--allow-cached-values", action="store_true")
    args = parser.parse_args()
    try:
        if Path(args.out).exists():
            raise ContractError("snapshot destination already exists; choose a new filename")
        snapshot = export_snapshot(args.workbook, parse_json(args.watch), args.label, args.allow_cached_values)
        with open(args.out, "x", encoding="utf-8") as stream:
            json.dump(snapshot, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": "EXPORTED", "items": len(snapshot["items"]), "value_basis": snapshot["value_basis"]}))
        return 0
    except Exception as exc:
        # Malformed ZIP/XML packages must fail closed, not resemble an export.
        print(json.dumps({"status": "INCOMPLETE", "error_type": type(exc).__name__, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
