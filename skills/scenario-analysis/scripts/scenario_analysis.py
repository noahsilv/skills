#!/usr/bin/env python3
"""Evaluate named cases and one-factor sensitivities against a preserved base."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import date
from fractions import Fraction
from pathlib import Path

ASSUMPTIONS = ("volume", "unit_price", "unit_variable_cost", "fixed_cost", "cash_taxes",
               "maintenance_capex", "working_capital_increase", "debt_service")
MONEY_METRICS = ("revenue", "variable_cost", "fixed_cost", "ebitda", "cash_taxes",
                 "maintenance_capex", "working_capital_increase", "cfads",
                 "debt_service", "cash_after_debt_service")
SUMMARY_METRICS = ("revenue", "ebitda", "cfads", "debt_service", "cash_after_debt_service")
OPERATIONS = {"replace", "add", "multiply"}


class InputError(ValueError):
    """An input violates the scenario contract."""


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise InputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise InputError(f"non-finite JSON number: {value}")


def json_integer(value):
    if len(value.lstrip("-")) > 24:
        raise InputError("JSON integer exceeds 24 digits")
    return int(value)


def reject_float(value):
    raise InputError("use decimal strings for financial values; JSON decimal numbers are not accepted")


def read_input(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(1_048_577)
    if len(raw) > 1_048_576:
        raise InputError("input exceeds 1 MiB")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=reject_constant, parse_int=json_integer, parse_float=reject_float)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InputError(f"invalid UTF-8 JSON: {exc}") from exc
    return data, hashlib.sha256(raw).hexdigest()


def keys(value, expected, where):
    if type(value) is not dict or set(value) != set(expected):
        raise InputError(f"{where}: expected exactly {', '.join(sorted(expected))}")


def integer(value, low, high, where):
    if type(value) is not int or not low <= value <= high:
        raise InputError(f"{where}: expected integer {low}..{high}")
    return value


def identifier(value, where):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value):
        raise InputError(f"{where}: expected 1..64 ASCII identifier characters, starting with a letter")
    return value


def decimal(value, where):
    if (type(value) is not str or len(value) > 41
            or not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value)):
        raise InputError(f"{where}: expected a plain decimal string")
    whole, _, tail = value.lstrip("-").partition(".")
    if len(whole) > 24 or len(tail) > 12:
        raise InputError(f"{where}: maximum 24 whole digits and 12 decimal places")
    return Fraction(value)


def vector(value, size, where):
    if type(value) is not list or len(value) != size:
        raise InputError(f"{where}: expected an array with one value for each of {size} periods")
    return tuple(decimal(item, where) for item in value)


def iso_date(value, where):
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise InputError(f"{where}: expected YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputError(f"{where}: invalid calendar date") from exc


def check_assumptions(assumptions, where):
    for key, values in assumptions.items():
        if key != "working_capital_increase" and any(value < 0 for value in values):
            raise InputError(f"{where}.{key}: applied assumptions must be nonnegative")


def validate(data):
    keys(data, {"schema_version", "analysis_id", "currency", "money_decimals", "periods",
                "base_assumptions", "cases", "sensitivities"}, "analysis")
    integer(data["schema_version"], 1, 1, "schema_version")
    identifier(data["analysis_id"], "analysis_id")
    if type(data["currency"]) is not str or not re.fullmatch(r"[A-Z]{3}", data["currency"]):
        raise InputError("currency: expected three uppercase letters")
    places = integer(data["money_decimals"], 0, 6, "money_decimals")
    if type(data["periods"]) is not list or not 1 <= len(data["periods"]) <= 120:
        raise InputError("periods: expected 1..120 entries")
    seen_periods, previous_end = set(), None
    for i, period in enumerate(data["periods"]):
        keys(period, {"id", "start_date", "end_date"}, f"periods[{i}]")
        identifier(period["id"], f"periods[{i}].id")
        if period["id"] in seen_periods:
            raise InputError("duplicate period id")
        seen_periods.add(period["id"])
        start = iso_date(period["start_date"], "period.start_date")
        end = iso_date(period["end_date"], "period.end_date")
        if end <= start or (previous_end is not None and start != previous_end):
            raise InputError("periods must have positive lengths, in order and contiguous")
        previous_end = end
    count = len(data["periods"])
    keys(data["base_assumptions"], ASSUMPTIONS, "base_assumptions")
    base = {key: vector(data["base_assumptions"][key], count, "base_assumptions." + key)
            for key in ASSUMPTIONS}
    check_assumptions(base, "base_assumptions")
    if type(data["cases"]) is not list or not 1 <= len(data["cases"]) <= 32:
        raise InputError("cases: expected 1..32 entries")
    cases, seen = [], set()
    for i, case in enumerate(data["cases"]):
        keys(case, {"id", "overrides"}, f"cases[{i}]")
        name = identifier(case["id"], "case.id")
        if name in seen:
            raise InputError(f"duplicate case id: {name}")
        seen.add(name)
        overrides = case["overrides"]
        if type(overrides) is not dict or not set(overrides).issubset(ASSUMPTIONS):
            raise InputError(f"case {name}: overrides must name known assumptions")
        if i == 0 and (name != "base" or overrides):
            raise InputError("first case must be base with empty overrides")
        parsed = {}
        for key, override in overrides.items():
            keys(override, {"operation", "values"}, f"case {name}.{key}")
            operation = override["operation"]
            if type(operation) is not str or operation not in OPERATIONS:
                raise InputError(f"case {name}.{key}: operation must be replace, add or multiply")
            parsed[key] = (operation, vector(override["values"], count, f"case {name}.{key}.values"))
        cases.append((name, parsed))
    sensitivities = data["sensitivities"]
    if type(sensitivities) is not list or len(sensitivities) > 16:
        raise InputError("sensitivities: expected an array of at most 16 axes")
    axes, seen = [], set()
    for i, axis in enumerate(sensitivities):
        keys(axis, {"id", "assumption", "operation", "values"}, f"sensitivities[{i}]")
        name = identifier(axis["id"], "sensitivity.id")
        if name in seen:
            raise InputError(f"duplicate sensitivity id: {name}")
        seen.add(name)
        if type(axis["assumption"]) is not str or axis["assumption"] not in ASSUMPTIONS:
            raise InputError(f"sensitivity {name}: unknown assumption")
        if type(axis["operation"]) is not str or axis["operation"] not in OPERATIONS:
            raise InputError(f"sensitivity {name}: invalid operation")
        if type(axis["values"]) is not list or not 1 <= len(axis["values"]) <= 21:
            raise InputError(f"sensitivity {name}: expected 1..21 levels")
        values = tuple(decimal(item, f"sensitivity {name}.values") for item in axis["values"])
        if len(set(values)) != len(values):
            raise InputError(f"sensitivity {name}: duplicate numeric levels")
        axes.append((name, axis["assumption"], axis["operation"], values))
    return base, tuple(cases), tuple(axes), places


def apply_overrides(base, overrides, where):
    applied = dict(base)  # Immutable tuples can be shared without modifying the baseline.
    for key, (operation, values) in overrides.items():
        if operation == "replace":
            applied[key] = values
        elif operation == "add":
            applied[key] = tuple(a + b for a, b in zip(base[key], values))
        else:
            applied[key] = tuple(a * b for a, b in zip(base[key], values))
    check_assumptions(applied, where)
    return applied


def fixed(value, places):
    sign = "-" if value < 0 else ""
    numerator = abs(value.numerator) * 10 ** places
    scaled, remainder = divmod(numerator, value.denominator)
    if remainder * 2 >= value.denominator:
        scaled += 1
    if scaled == 0:
        sign = ""
    whole, tail = divmod(scaled, 10 ** places)
    return f"{sign}{whole}" + (f".{tail:0{places}d}" if places else "")


def exact(value):
    return None if value is None else f"{value.numerator}/{value.denominator}"


def evaluate(assumptions):
    rows = []
    for i in range(len(assumptions["volume"])):
        a = {key: values[i] for key, values in assumptions.items()}
        revenue = a["volume"] * a["unit_price"]
        variable_cost = a["volume"] * a["unit_variable_cost"]
        ebitda = revenue - variable_cost - a["fixed_cost"]
        cfads = ebitda - a["cash_taxes"] - a["maintenance_capex"] - a["working_capital_increase"]
        row = {key: a[key] for key in ("fixed_cost", "cash_taxes", "maintenance_capex",
                                      "working_capital_increase", "debt_service")}
        row.update(revenue=revenue, variable_cost=variable_cost, ebitda=ebitda, cfads=cfads,
                   cash_after_debt_service=cfads - a["debt_service"],
                   dscr=cfads / a["debt_service"] if a["debt_service"] else None)
        rows.append(row)
    summary = {key: sum((row[key] for row in rows), Fraction(0)) for key in SUMMARY_METRICS}
    defined = [row["dscr"] for row in rows if row["dscr"] is not None]
    summary["minimum_defined_dscr"] = min(defined) if defined else None
    summary["periods_with_dscr"] = len(defined)
    summary["period_count"] = len(rows)
    return rows, summary


def summary_display(summary, places):
    result = {key: fixed(summary[key], places) for key in SUMMARY_METRICS}
    result["minimum_defined_dscr"] = (fixed(summary["minimum_defined_dscr"], 6)
                                      if summary["minimum_defined_dscr"] is not None else None)
    result["periods_with_dscr"] = summary["periods_with_dscr"]
    result["period_count"] = summary["period_count"]
    return result


def csv_text(rows, fields):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def calculate(data):
    base, cases, axes, places = validate(data)
    base_rows, base_summary = evaluate(base)
    baseline_hash = hashlib.sha256(json.dumps(data["base_assumptions"], sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    results, summaries, period_csv, changes, sensitivity_csv = [], [], [], [], []
    for name, overrides in cases:
        applied = apply_overrides(base, overrides, f"case {name}")
        rows, summary = evaluate(applied)
        changed_keys = [key for key in ASSUMPTIONS if applied[key] != base[key]]
        status = ("BASE" if name == "base" else "NO_ASSUMPTION_CHANGE" if not changed_keys else
                  "OUTPUT_CHANGED" if rows != base_rows else "ASSUMPTIONS_CHANGED_OUTPUT_UNCHANGED")
        if name == "base" and (rows != base_rows or applied != base):
            raise ArithmeticError("base preservation failed")
        display = summary_display(summary, places)
        deltas = {"delta_" + key: fixed(summary[key] - base_summary[key], places) for key in SUMMARY_METRICS}
        summaries.append({"case_id": name, "status": status, **display, **deltas})
        output_rows = []
        for i, (period, row) in enumerate(zip(data["periods"], rows)):
            displayed = {key: fixed(row[key], places) for key in MONEY_METRICS}
            displayed["dscr"] = fixed(row["dscr"], 6) if row["dscr"] is not None else None
            displayed["dscr_status"] = "DEFINED" if row["dscr"] is not None else "ZERO_DEBT_SERVICE"
            period_csv.append({"case_id": name, "period_id": period["id"], **displayed})
            output_rows.append({"period": dict(period), **displayed,
                                "exact_metrics": {key: exact(row[key]) for key in (*MONEY_METRICS, "dscr")}})
            for key in changed_keys:
                if applied[key][i] != base[key][i]:
                    operation, values = overrides[key]
                    changes.append({"case_id": name, "period_id": period["id"], "assumption": key,
                                    "operation": operation, "override_value": exact(values[i]),
                                    "base_value": exact(base[key][i]), "applied_value": exact(applied[key][i]),
                                    "change": exact(applied[key][i] - base[key][i])})
        results.append({"id": name, "status": status, "changed_assumptions": changed_keys,
                        "applied_assumptions": {key: [exact(x) for x in values] for key, values in applied.items()},
                        "summary": display, "delta_from_base": deltas,
                        "exact_summary": {key: exact(summary[key]) for key in (*SUMMARY_METRICS, "minimum_defined_dscr")},
                        "periods": output_rows})
    sensitivity_results = []
    for name, assumption, operation, levels in axes:
        for level in levels:
            values = (level,) * len(data["periods"])
            applied = apply_overrides(base, {assumption: (operation, values)}, f"sensitivity {name}")
            rows, summary = evaluate(applied)
            display = summary_display(summary, places)
            change = summary["cash_after_debt_service"] - base_summary["cash_after_debt_service"]
            displayed = {"sensitivity_id": name, "assumption": assumption, "operation": operation,
                         "level": fixed(level, 12), **display, "delta_cash_after_debt_service": fixed(change, places)}
            sensitivity_csv.append(displayed)
            sensitivity_results.append({**displayed, "level_exact": exact(level),
                                        "exact_summary": {key: exact(summary[key]) for key in (*SUMMARY_METRICS, "minimum_defined_dscr")},
                                        "delta_cash_after_debt_service_exact": exact(change),
                                        "period_metrics_exact": [{key: exact(row[key]) for key in (*MONEY_METRICS, "dscr")}
                                                                 for row in rows]})
    if base != {key: vector(data["base_assumptions"][key], len(data["periods"]), key) for key in ASSUMPTIONS}:
        raise ArithmeticError("baseline changed during calculation")
    return {"schema_version": 1, "model": "operating-cash-bridge-v1",
            "analysis_id": data["analysis_id"], "currency": data["currency"], "unit": "currency units",
            "money_decimals": places, "base_assumptions_sha256": baseline_hash,
            "checks": {"base_preserved": "PASS"}, "cases": results,
            "sensitivities": sensitivity_results, "case_summary_rows": summaries,
            "period_rows": period_csv, "assumption_change_rows": changes, "sensitivity_rows": sensitivity_csv}


def render_report(result):
    lines = [f"# Scenario analysis: {result['analysis_id']}", "",
             f"Amounts: {result['currency']} currency units. Base preservation: PASS.", "",
             "The engine recalculates its declared operating cash bridge for every case. "
             "Each case and sensitivity starts from the same base. Taxes, maintenance capex, "
             "working capital and debt service are explicit inputs and change only when overridden.", "",
             "| Case | Status | Revenue | EBITDA | CFADS | Debt service | Cash after service | Minimum defined DSCR | DSCR periods |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for row in result["case_summary_rows"]:
        lines.append("| " + " | ".join(str(row[k]) if row[k] is not None else "n/a" for k in
                     ("case_id", "status", "revenue", "ebitda", "cfads", "debt_service",
                      "cash_after_debt_service", "minimum_defined_dscr"))
                     + f" | {row['periods_with_dscr']}/{row['period_count']} |")
    lines += ["", "Amounts are totals over the declared periods. DSCR is the minimum of defined period ratios, "
              "not total CFADS divided by total debt service. A period with zero debt service has undefined DSCR; "
              "it is excluded from the minimum and disclosed in the period coverage count.", "",
              "## Effective assumption changes", ""]
    for case in result["cases"]:
        lines.append(f"- {case['id']}: " + (", ".join(case["changed_assumptions"]) or "none") + ".")
    lines += ["", "Exact changes by period are in assumption_changes.csv. A case with no output movement "
              "needs interpretation: it may be a no-op or a changed assumption with no effect at the given base.", "",
              "## One-factor sensitivities", "",
              "Each level changes only the named assumption across all periods from base; axes are not combined.", "",
              "| Axis | Assumption | Operation | Level | Cash after service | Change from base | Minimum defined DSCR |",
              "|---|---|---|---:|---:|---:|---:|"]
    for row in result["sensitivity_rows"]:
        lines.append("| " + " | ".join(str(row[k]) if row[k] is not None else "n/a" for k in
                     ("sensitivity_id", "assumption", "operation", "level", "cash_after_debt_service",
                      "delta_cash_after_debt_service", "minimum_defined_dscr")) + " |")
    if not result["sensitivity_rows"]:
        lines.append("| None requested | | | | | | |")
    lines += ["", "Scope: one currency, volume × price revenue, variable and fixed costs, explicit cash adjustments "
              "and explicit debt service. No tax solver, debt engine, valuation, cash funding plug, "
              "probability weighting, covenant threshold or spreadsheet recalculation is performed. "
              "These results show the stated assumptions, not a forecast validation.", "",
              f"Base assumptions SHA-256: `{result['base_assumptions_sha256']}`", ""]
    if "input_sha256" in result:
        lines += [f"Input SHA-256: `{result['input_sha256']}`", ""]
    return "\n".join(lines)


def run(input_path, output_path):
    data, digest = read_input(input_path)
    result = calculate(data)
    result["input_sha256"] = digest
    summary_fields = ["case_id", "status", *SUMMARY_METRICS, "minimum_defined_dscr", "periods_with_dscr", "period_count",
                      *("delta_" + key for key in SUMMARY_METRICS)]
    files = {"report.json": json.dumps(result, indent=2) + "\n", "report.md": render_report(result),
             "cases.csv": csv_text(result["case_summary_rows"], summary_fields),
             "period_results.csv": csv_text(result["period_rows"], ["case_id", "period_id", *MONEY_METRICS, "dscr", "dscr_status"]),
             "assumption_changes.csv": csv_text(result["assumption_change_rows"],
                    ["case_id", "period_id", "assumption", "operation", "override_value", "base_value", "applied_value", "change"]),
             "sensitivities.csv": csv_text(result["sensitivity_rows"],
                    ["sensitivity_id", "assumption", "operation", "level", *SUMMARY_METRICS,
                     "minimum_defined_dscr", "periods_with_dscr", "period_count", "delta_cash_after_debt_service"])}
    if hashlib.sha256(Path(input_path).read_bytes()).hexdigest() != digest:
        raise InputError("input changed during calculation; no output written")
    output = Path(output_path)
    output.mkdir()
    for name, content in files.items():
        with (output / name).open("x", encoding="utf-8", newline="") as handle:
            handle.write(content)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="UTF-8 JSON assumptions, case registry and sensitivity axes")
    parser.add_argument("--out", required=True, help="new output directory; parent must exist")
    args = parser.parse_args(argv)
    try:
        run(args.input, args.out)
    except (InputError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Scenario outputs written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
