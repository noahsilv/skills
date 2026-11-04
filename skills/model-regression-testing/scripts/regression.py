#!/usr/bin/env python3
"""Compare immutable, typed JSON snapshots with explicit change declarations."""

import argparse
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
import sys


class ContractError(ValueError):
    pass


def fields(obj, required, optional, label):
    if not isinstance(obj, dict) or required - set(obj) or set(obj) - required - optional:
        raise ContractError(f"{label} must be an object with the documented fields")


def label(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be nonempty text")
    return value


def numeric(value, name, *, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ContractError(f"{name} must be a finite number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ContractError(f"{name} must be a finite number") from exc
    if not result.is_finite() or (nonnegative and result < 0):
        raise ContractError(f"{name} has an invalid numeric value")
    if len(result.as_tuple().digits) > 1000 or abs(result.as_tuple().exponent) > 1000:
        raise ContractError(f"{name} exceeds the supported 1000-digit/exponent numeric bound")
    return result


def arithmetic_precision(*values):
    # Enough digits for exact finite-decimal subtraction and multiplication,
    # including widely separated exponents. Inputs have explicit size bounds.
    return max(28, 2 * sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent) for v in values) + 16)


def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported JSON output type: {type(value).__name__}")


def kind(value):
    if value is None:
        return "missing"
    if type(value) is bool:
        return "boolean"
    if isinstance(value, (int, float, Decimal)):
        numeric(value, "snapshot value")
        return "number"
    if isinstance(value, str):
        return "text"
    raise ContractError("snapshot values must be numbers, booleans, text or null")


def parse_json(path):
    def pairs(items):
        output = {}
        for key, value in items:
            if key in output:
                raise ContractError(f"duplicate JSON key: {key}")
            output[key] = value
        return output
    def invalid(value):
        raise ContractError(f"nonfinite JSON number: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=invalid, parse_float=Decimal)


def validate_snapshot(snapshot):
    fields(snapshot, {"schema_version", "label", "value_basis", "items"}, {"source_sha256"}, "snapshot")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1:
        raise ContractError("snapshot schema_version must be 1")
    label(snapshot["label"], "snapshot label")
    if snapshot["value_basis"] not in ("literal", "saved_formula_cache"):
        raise ContractError("value_basis must be literal or saved_formula_cache; no recalculation is claimed")
    if "source_sha256" in snapshot:
        import re
        if not isinstance(snapshot["source_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", snapshot["source_sha256"]):
            raise ContractError("source_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(snapshot["items"], list) or not snapshot["items"]:
        raise ContractError("items must be nonempty; zero watch items cannot pass")
    result = {}
    for item in snapshot["items"]:
        fields(item, {"id", "value", "unit", "period"}, set(), "watch item")
        for key in ("id", "unit", "period"):
            label(item[key], key)
        kind(item["value"])
        if item["id"] in result:
            raise ContractError(f"duplicate watch id: {item['id']}")
        result[item["id"]] = item
    return result


def validate_declarations(declarations, baseline_ids):
    fields(declarations, {"schema_version", "changes"}, set(), "declarations")
    if type(declarations["schema_version"]) is not int or declarations["schema_version"] != 1:
        raise ContractError("declaration schema_version must be 1")
    if not isinstance(declarations["changes"], list):
        raise ContractError("changes must be a list")
    result = {}
    for item in declarations["changes"]:
        fields(item, {"id", "reason"}, set(), "change declaration")
        name = label(item["id"], "declaration id")
        label(item["reason"], "change reason")
        if name not in baseline_ids or name in result:
            raise ContractError(f"unknown or duplicate declaration id: {name}")
        result[name] = item["reason"]
    return result


def validate_tolerances(tolerances, baseline):
    fields(tolerances, {"schema_version", "items"}, set(), "tolerances")
    if type(tolerances["schema_version"]) is not int or tolerances["schema_version"] != 1:
        raise ContractError("tolerance schema_version must be 1")
    if not isinstance(tolerances["items"], list):
        raise ContractError("tolerance items must be a list")
    output = {}
    for item in tolerances["items"]:
        fields(item, {"id", "absolute", "relative", "reason"}, set(), "tolerance item")
        name = label(item["id"], "tolerance id")
        label(item["reason"], "tolerance reason")
        if name not in baseline or name in output:
            raise ContractError(f"unknown or duplicate tolerance id: {name}")
        if kind(baseline[name]["value"]) != "number":
            raise ContractError("numeric tolerances require numeric baseline values")
        numeric(item["absolute"], "absolute tolerance", nonnegative=True)
        numeric(item["relative"], "relative tolerance", nonnegative=True)
        output[name] = item
    return output


def equal(a, b, tolerance):
    if kind(a) != kind(b):
        return False, {"reason": "value types differ"}
    if kind(a) != "number":
        return a == b, {"reason": "exact typed comparison"}
    current, base = numeric(a, "current"), numeric(b, "baseline")
    absolute = numeric(tolerance.get("absolute", 0), "absolute")
    relative = numeric(tolerance.get("relative", 0), "relative")
    with localcontext() as context:
        context.prec = arithmetic_precision(current, base, absolute, relative)
        delta = current - base
        limit = max(absolute, relative * abs(base))
        return abs(delta) <= limit, {"delta": str(delta), "allowed_difference": str(limit)}


def compare(baseline, current, declarations=None, tolerances=None):
    old, new = validate_snapshot(baseline), validate_snapshot(current)
    declared = validate_declarations(declarations if declarations is not None else {"schema_version": 1, "changes": []}, old)
    limits = validate_tolerances(tolerances if tolerances is not None else {"schema_version": 1, "items": []}, old)
    rows = []
    for name in sorted(set(old) | set(new)):
        row = {"id": name, "declared_reason": declared.get(name),
               "baseline": old.get(name), "current": new.get(name), "tolerance": limits.get(name),
               "baseline_value_type": kind(old[name]["value"]) if name in old else "absent",
               "current_value_type": kind(new[name]["value"]) if name in new else "absent"}
        if name not in old:
            row["status"] = "ADDED"
        elif name not in new:
            row["status"] = "REMOVED"
        elif any(old[name][key] != new[name][key] for key in ("period", "unit")):
            row["status"] = "BASIS_CHANGED"
        elif old[name]["value"] is None or new[name]["value"] is None:
            row["status"] = "INCOMPLETE"
        elif kind(old[name]["value"]) != kind(new[name]["value"]):
            row["status"] = "TYPE_CHANGED"
        else:
            same, detail = equal(new[name]["value"], old[name]["value"], limits.get(name, {}))
            row.update(detail)
            if name in declared:
                row["status"] = "EXPECTED_UNCHANGED" if same else "EXPECTED_CHANGED"
            else:
                row["status"] = "STABLE" if same else "REGRESSION"
        rows.append(row)
    counts = {status: sum(row["status"] == status for row in rows)
              for status in ("STABLE", "REGRESSION", "EXPECTED_CHANGED", "EXPECTED_UNCHANGED",
                             "ADDED", "REMOVED", "BASIS_CHANGED", "TYPE_CHANGED", "INCOMPLETE")}
    regressions = sum(counts[key] for key in ("REGRESSION", "ADDED", "REMOVED", "BASIS_CHANGED", "TYPE_CHANGED"))
    cache = "saved_formula_cache" in (baseline["value_basis"], current["value_basis"])
    status = ("INCOMPLETE" if counts["INCOMPLETE"] else "FAIL" if regressions
              else "REVIEW" if declared or cache else "PASS")
    return {"schema_version": 1, "status": status, "baseline_label": baseline["label"],
            "current_label": current["label"], "baseline_items": len(old), "current_items": len(new),
            "counts": counts, "calculation": "saved_formula_caches_unverified" if cache else "literal_values_only",
            "number_encoding": "Decimal JSON fractions are emitted as exact text; row value_type fields identify numeric values. Integers remain JSON numbers.",
            "scope": "Typed watch snapshots only; source accuracy, recalculation and unlisted outputs are not verified.",
            "results": rows}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("current")
    parser.add_argument("--declarations")
    parser.add_argument("--tolerances")
    parser.add_argument("--out", help="new report file; inputs are never changed")
    args = parser.parse_args()
    try:
        if args.out and Path(args.out).exists():
            raise ContractError("report destination already exists")
        paths = [Path(p) for p in (args.baseline, args.current, args.declarations, args.tolerances) if p]
        before = [digest(p) for p in paths]
        report = compare(parse_json(args.baseline), parse_json(args.current),
                         parse_json(args.declarations) if args.declarations else None,
                         parse_json(args.tolerances) if args.tolerances else None)
        if before != [digest(p) for p in paths]:
            raise ContractError("an input changed during comparison; rerun on stable copies")
        report["inputs"] = [{"file": p.name, "sha256": h} for p, h in zip(paths, before)]
        encoded = json.dumps(report, indent=2, allow_nan=False, default=json_default) + "\n"
        if args.out:
            with open(args.out, "x", encoding="utf-8") as stream:
                stream.write(encoded)
        print(encoded, end="")
        return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2, "REVIEW": 3}[report["status"]]
    except (ContractError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "INCOMPLETE", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
