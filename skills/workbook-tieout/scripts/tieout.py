#!/usr/bin/env python3
"""Compare explicitly mapped XLSX cells without changing either workbook."""

import argparse
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
import re
import sys

from openpyxl import load_workbook


class ContractError(ValueError):
    """The mapping or input cannot support a reliable comparison."""


def number(value, label, *, nonnegative=False, nonzero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ContractError(f"{label} must be a finite number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ContractError(f"{label} must be a finite number") from exc
    if not result.is_finite() or (nonnegative and result < 0) or (nonzero and result == 0):
        raise ContractError(f"{label} has an invalid numeric value")
    if len(result.as_tuple().digits) > 1000 or abs(result.as_tuple().exponent) > 1000:
        raise ContractError(f"{label} exceeds the supported 1000-digit/exponent numeric bound")
    return result


def arithmetic_precision(*values):
    return max(28, 2 * sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in values) + 16)


def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported JSON output type: {type(value).__name__}")


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be nonempty text")
    return value


def require_keys(obj, required, optional, label):
    if not isinstance(obj, dict):
        raise ContractError(f"{label} must be an object")
    if set(obj) - required - optional or required - set(obj):
        raise ContractError(f"{label} has missing or unknown fields")


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def reject(value):
        raise ContractError(f"nonfinite JSON number: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=pairs, parse_constant=reject, parse_float=Decimal)


def validate_mapping(mapping):
    require_keys(mapping, {"schema_version", "pairs"}, set(), "mapping")
    if type(mapping["schema_version"]) is not int or mapping["schema_version"] != 1:
        raise ContractError("schema_version must be 1")
    if not isinstance(mapping["pairs"], list) or not mapping["pairs"]:
        raise ContractError("pairs must be a nonempty list; zero comparisons cannot pass")
    ids, used_left, used_right = set(), set(), set()
    for item in mapping["pairs"]:
        require_keys(item, {"id", "left", "right", "comparison_unit"},
                     {"absolute_tolerance", "relative_tolerance"}, "pair")
        name = text(item["id"], "id")
        if name in ids:
            raise ContractError(f"duplicate pair id: {name}")
        ids.add(name)
        unit = text(item["comparison_unit"], "comparison_unit")
        for side, used in (("left", used_left), ("right", used_right)):
            point = item[side]
            require_keys(point, {"sheet", "cell", "period", "unit"}, {"multiplier"}, side)
            for key in ("sheet", "cell", "period", "unit"):
                text(point[key], f"{side}.{key}")
            if not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,6}", point["cell"]):
                raise ContractError(f"{side}.cell must be one uppercase A1 cell reference")
            from openpyxl.utils.cell import coordinate_to_tuple
            row, col = coordinate_to_tuple(point["cell"])
            if row > 1048576 or col > 16384:
                raise ContractError("cell is outside XLSX worksheet bounds")
            key = (point["sheet"], point["cell"])
            if key in used:
                raise ContractError(f"duplicate {side} endpoint: {key}")
            used.add(key)
            if point["unit"] != unit and "multiplier" not in point:
                raise ContractError(f"{name}: a unit conversion requires an explicit multiplier")
            number(point.get("multiplier", 1), f"{side}.multiplier", nonzero=True)
        if item["left"]["period"] != item["right"]["period"]:
            raise ContractError(f"{name}: declared periods differ")
        for key in ("absolute_tolerance", "relative_tolerance"):
            number(item.get(key, 0), key, nonnegative=True)
    return mapping


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def describe(value):
    if value is None:
        return {"type": "blank", "value": None}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, (int, float, Decimal)):
        return {"type": "number", "value": str(number(value, "cell value"))}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"type": "time", "value": value.isoformat()}
    if isinstance(value, str):
        return {"type": "text", "value": value}
    raise ContractError(f"unsupported cell value type: {type(value).__name__}")


def read_cell(formulas, cached, point, allow_cached):
    if point["sheet"] not in formulas.sheetnames:
        return {"status": "INCOMPLETE", "reason": "sheet is missing"}
    cell = formulas[point["sheet"]][point["cell"]]
    is_formula = cell.data_type == "f"
    if is_formula and not allow_cached:
        return {"status": "INCOMPLETE", "reason": "formula requires --allow-cached-values", "formula_present": True}
    value_cell = cached[point["sheet"]][point["cell"]] if is_formula else cell
    if value_cell.data_type == "e":
        return {"status": "INCOMPLETE", "reason": "spreadsheet error value", "formula_present": is_formula}
    if value_cell.value is None:
        return {"status": "INCOMPLETE", "reason": "formula cache is missing" if is_formula else "cell is blank", "formula_present": is_formula}
    try:
        result = describe(value_cell.value)
        multiplier = number(point.get("multiplier", 1), "multiplier", nonzero=True)
        if result["type"] == "number":
            value = Decimal(result["value"])
            with localcontext() as context:
                context.prec = arithmetic_precision(value, multiplier)
                result["normalized_value"] = str(value * multiplier)
        elif multiplier != 1:
            raise ContractError("only numeric cells may use a conversion multiplier")
    except ContractError as exc:
        return {"status": "INCOMPLETE", "reason": str(exc), "formula_present": is_formula}
    result.update(status="READ", formula_cache=is_formula, formula_present=is_formula)
    return result


def compare_values(left, right, pair):
    if left["type"] != right["type"]:
        return False, {"reason": "value types differ"}
    if left["type"] != "number":
        if pair.get("absolute_tolerance", 0) or pair.get("relative_tolerance", 0):
            raise ContractError("numeric tolerances cannot be applied to nonnumeric values")
        return left["value"] == right["value"], {"reason": "exact typed comparison"}
    a, b = Decimal(left["normalized_value"]), Decimal(right["normalized_value"])
    absolute = number(pair.get("absolute_tolerance", 0), "absolute_tolerance")
    relative = number(pair.get("relative_tolerance", 0), "relative_tolerance")
    with localcontext() as context:
        context.prec = arithmetic_precision(a, b, absolute, relative)
        delta = a - b
        limit = max(absolute, relative * abs(b))
        return abs(delta) <= limit, {"delta": str(delta), "allowed_difference": str(limit)}


def tieout(left_path, right_path, mapping, allow_cached=False):
    validate_mapping(mapping)
    paths = [Path(left_path), Path(right_path)]
    if any(p.suffix.lower() != ".xlsx" for p in paths):
        raise ContractError("only .xlsx files are supported")
    hashes = [sha256(p) for p in paths]
    books = []
    try:
        for path in paths:
            books.extend([load_workbook(path, read_only=True, data_only=False),
                          load_workbook(path, read_only=True, data_only=True)])
        rows = []
        for pair in mapping["pairs"]:
            left = read_cell(books[0], books[1], pair["left"], allow_cached)
            right = read_cell(books[2], books[3], pair["right"], allow_cached)
            row = {"id": pair["id"], "mapping": pair, "left": left, "right": right}
            if left["status"] != "READ" or right["status"] != "READ":
                row["status"] = "INCOMPLETE"
            else:
                try:
                    same, detail = compare_values(left, right, pair)
                    row.update(detail)
                    row["status"] = "MATCH" if same else "MISMATCH"
                except ContractError as exc:
                    row.update(status="INCOMPLETE", reason=str(exc))
            rows.append(row)
    finally:
        for book in books:
            book.close()
    if hashes != [sha256(p) for p in paths]:
        raise ContractError("an input changed during the comparison; rerun on stable copies")
    counts = {key.lower(): sum(row["status"] == key for row in rows)
              for key in ("MATCH", "MISMATCH", "INCOMPLETE")}
    cached_used = any(row[side].get("formula_cache", False) for row in rows for side in ("left", "right"))
    unavailable_formula = any(row[side].get("formula_present", False) and row[side]["status"] != "READ"
                              for row in rows for side in ("left", "right"))
    status = ("INCOMPLETE" if counts["incomplete"] else "FAIL" if counts["mismatch"]
              else "REVIEW" if cached_used else "PASS")
    return {"schema_version": 1, "status": status, "requested_pairs": len(rows),
            "compared_pairs": counts["match"] + counts["mismatch"], **counts,
            "calculation": ("formula_values_incomplete" if unavailable_formula else
                            "saved_formula_caches_unverified" if cached_used else "literal_values_only"),
            "scope": "Only explicitly mapped cells; headers, source accuracy and unmapped cells are not verified.",
            "number_encoding": "Cell numbers, deltas and decimal mapping numbers are exact text; integer mapping numbers remain JSON numbers.",
            "inputs": [{"file": p.name, "sha256": digest} for p, digest in zip(paths, hashes)],
            "results": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left")
    parser.add_argument("right")
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--allow-cached-values", action="store_true")
    parser.add_argument("--out", help="new report file; existing files are never overwritten")
    args = parser.parse_args()
    try:
        if args.out and Path(args.out).exists():
            raise ContractError("report destination already exists")
        report = tieout(args.left, args.right, load_json(args.mapping), args.allow_cached_values)
        encoded = json.dumps(report, indent=2, allow_nan=False, default=json_default) + "\n"
        if args.out:
            with open(args.out, "x", encoding="utf-8") as stream:
                stream.write(encoded)
        print(encoded, end="")
        return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2, "REVIEW": 3}[report["status"]]
    except Exception as exc:
        # Fail closed for malformed ZIP/XML packages as well as contract errors.
        print(json.dumps({"status": "INCOMPLETE", "error_type": type(exc).__name__, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
