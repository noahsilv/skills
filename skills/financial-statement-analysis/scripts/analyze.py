#!/usr/bin/env python3
"""Analyze explicitly normalized historical statements; never infer missing inputs."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path


class InputError(ValueError):
    pass


FIELDS = {
    "total_assets", "total_liabilities", "total_equity", "current_assets",
    "current_liabilities", "cash_and_equivalents", "debt_current",
    "debt_noncurrent", "leases_current", "leases_noncurrent", "revenue",
    "cost_of_sales", "gross_profit", "operating_expenses", "operating_profit",
    "net_income", "opening_cash", "closing_cash", "cash_from_operations",
    "cash_from_investing", "cash_from_financing", "fx_cash_movement",
    "opening_equity", "other_comprehensive_income", "owner_contributions",
    "dividends",
}
NONNEGATIVE = {
    "total_assets", "total_liabilities", "current_assets", "current_liabilities",
    "cash_and_equivalents", "debt_current", "debt_noncurrent", "leases_current",
    "leases_noncurrent", "cost_of_sales", "operating_expenses", "opening_cash",
    "closing_cash", "owner_contributions", "dividends",
}
# Each reconciliation is the sum of these signed terms, expected to equal zero.
CHECKS = {
    "balance_sheet": {"total_assets": 1, "total_liabilities": -1, "total_equity": -1},
    "gross_profit": {"gross_profit": 1, "revenue": -1, "cost_of_sales": 1},
    "operating_profit": {"operating_profit": 1, "gross_profit": -1, "operating_expenses": 1},
    "cash_rollforward": {"closing_cash": 1, "opening_cash": -1,
                         "cash_from_operations": -1, "cash_from_investing": -1,
                         "cash_from_financing": -1, "fx_cash_movement": -1},
    "cash_to_balance_sheet": {"cash_and_equivalents": 1, "closing_cash": -1},
    "equity_rollforward": {"total_equity": 1, "opening_equity": -1,
                           "net_income": -1, "other_comprehensive_income": -1,
                           "owner_contributions": -1, "dividends": 1},
}
DEBT = {"debt_current": 1, "debt_noncurrent": 1, "leases_current": 1, "leases_noncurrent": 1}
METRICS = {
    "gross_margin": ({"gross_profit": 1}, "revenue", "fraction"),
    "operating_margin": ({"operating_profit": 1}, "revenue", "fraction"),
    "net_margin": ({"net_income": 1}, "revenue", "fraction"),
    "operating_cash_margin": ({"cash_from_operations": 1}, "revenue", "fraction"),
    "current_ratio": ({"current_assets": 1}, "current_liabilities", "multiple"),
    "gross_debt": (DEBT, None, "reporting_units"),
    "net_debt": ({**DEBT, "cash_and_equivalents": -1}, None, "reporting_units"),
    "debt_to_equity": (DEBT, "total_equity", "multiple"),
}


def obj(value, keys, where):
    if type(value) is not dict or set(value) != set(keys):
        raise InputError(f"{where}: expected exactly fields {', '.join(sorted(keys))}")
    return value


def string(value, where):
    if type(value) is not str or not value.strip() or len(value) > 2000 or any(ord(c) < 32 for c in value):
        raise InputError(f"{where}: expected nonempty text without control characters (max 2000)")
    return value


def identifier(value, where):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", value):
        raise InputError(f"{where}: expected an identifier")
    return value


def decimal(value, where):
    if type(value) is not str or not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,23})(?:\.[0-9]{1,12})?", value):
        raise InputError(f"{where}: expected a decimal string (24 integer / 12 fractional digits max)")
    return Decimal(value)


def iso_date(value, where):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise InputError(f"{where}: expected YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputError(f"{where}: invalid calendar date") from exc


def unique(items, key, where):
    seen = set()
    for item in items:
        val = item[key]
        if val in seen:
            raise InputError(f"{where}: duplicate {key} {val!r}")
        seen.add(val)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def loads(raw):
    try:
        value = json.loads(raw, object_pairs_hook=no_duplicates,
                          parse_constant=lambda x: (_ for _ in ()).throw(InputError(f"Invalid JSON constant: {x}")))
        # Bound nesting explicitly; JSON parser recursion limits differ by Python version.
        stack = [(value, 0)]
        while stack:
            item, depth = stack.pop()
            if depth > 100:
                raise ValueError("JSON nesting exceeds 100 levels")
            if isinstance(item, dict):
                stack.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                stack.extend((child, depth + 1) for child in item)
        return value
    except InputError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InputError(f"Invalid UTF-8 JSON: {exc}") from exc


def array(value, where, minimum=1, maximum=100):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise InputError(f"{where}: expected {minimum}..{maximum} entries")
    return value


def validate(data):
    obj(data, {"schema_version", "entity", "currency", "scale", "reporting_basis",
               "sign_convention", "reconciliation_tolerance", "tolerance_reason", "sources", "periods"}, "input")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise InputError("schema_version: expected integer 1")
    obj(data["entity"], {"id", "name", "scope"}, "entity")
    identifier(data["entity"]["id"], "entity.id")
    string(data["entity"]["name"], "entity.name")
    if data["entity"]["scope"] not in ("standalone", "consolidated"):
        raise InputError("entity.scope: expected standalone or consolidated")
    if type(data["currency"]) is not str or not re.fullmatch("[A-Z]{3}", data["currency"]):
        raise InputError("currency: expected an explicit three-letter code")
    if data["scale"] not in ("1", "1000", "1000000", "1000000000"):
        raise InputError("scale: expected decimal string 1, 1000, 1000000 or 1000000000")
    string(data["reporting_basis"], "reporting_basis")
    if data["sign_convention"] != "expenses_positive_cash_flows_signed":
        raise InputError("sign_convention: expected expenses_positive_cash_flows_signed")
    tolerance = decimal(data["reconciliation_tolerance"], "reconciliation_tolerance")
    if tolerance < 0:
        raise InputError("reconciliation_tolerance cannot be negative")
    string(data["tolerance_reason"], "tolerance_reason")
    sources = array(data["sources"], "sources")
    for source in sources:
        obj(source, {"id", "document", "title", "audit_status", "sha256"}, "source")
        identifier(source["id"], "source.id")
        string(source["document"], "source.document")
        string(source["title"], "source.title")
        if type(source["sha256"]) is not str or not re.fullmatch("[a-f0-9]{64}", source["sha256"]):
            raise InputError("source.sha256: expected the declared document's lowercase SHA-256 digest")
        if source["audit_status"] not in ("audited", "unaudited", "interim", "unknown"):
            raise InputError("source.audit_status is invalid")
    unique(sources, "id", "sources")
    source_ids = {source["id"] for source in sources}
    periods = array(data["periods"], "periods", maximum=50)
    dates = set()
    for period in periods:
        obj(period, {"id", "label", "start", "end", "kind", "basis", "values"}, "period")
        identifier(period["id"], "period.id")
        string(period["label"], "period.label")
        start, end = iso_date(period["start"], "period.start"), iso_date(period["end"], "period.end")
        if start > end or (end - start).days > 371:
            raise InputError("period: dates must be ordered and cover at most 372 days")
        if period["kind"] not in ("annual", "interim") or period["basis"] not in ("as_reported", "restated"):
            raise InputError("period: invalid kind or basis")
        if period["kind"] == "annual" and not 350 <= (end-start).days + 1 <= 372:
            raise InputError("annual period must cover 350..372 days; shorter periods use interim")
        if (start, end) in dates:
            raise InputError("Duplicate period coverage; select one comparative vintage before analysis")
        dates.add((start, end))
        values = period["values"]
        if type(values) is not dict or not values or not set(values) <= FIELDS:
            raise InputError("period.values: expected nonempty mapping of documented field names")
        for field, record in values.items():
            obj(record, {"value", "sources", "note"}, f"values.{field}")
            if type(record["note"]) is not str or len(record["note"]) > 2000 or any(ord(c) < 32 for c in record["note"]):
                raise InputError(f"{field}.note: expected plain text")
            refs = array(record["sources"], f"{field}.sources", minimum=0)
            refs_seen = set()
            for ref in refs:
                obj(ref, {"source_id", "locator"}, "source reference")
                identifier(ref["source_id"], "reference.source_id")
                string(ref["locator"], "reference.locator")
                if ref["source_id"] not in source_ids:
                    raise InputError(f"{field}: unknown source reference")
                pair = (ref["source_id"], ref["locator"])
                if pair in refs_seen:
                    raise InputError(f"{field}: duplicate source reference")
                refs_seen.add(pair)
            if record["value"] is None:
                if not record["note"].strip():
                    raise InputError(f"{field}: an explicit missing value requires a note")
            else:
                val = decimal(record["value"], f"{field}.value")
                if not refs:
                    raise InputError(f"{field}: a reported value requires source references")
                if field in NONNEGATIVE and val < 0:
                    raise InputError(f"{field}: negative value conflicts with the declared sign convention")
    unique(periods, "id", "periods")
    return tolerance


def number(value):
    return format(value, "f") if value is not None else None


def analyze(data):
    tolerance = validate(data)
    output = {"schema_version": 1, "status": "COMPLETE", "entity": data["entity"],
              "currency": data["currency"], "scale": data["scale"],
              "reporting_basis": data["reporting_basis"], "sign_convention": data["sign_convention"],
              "sources": data["sources"], "source_evidence": "DECLARED_REFERENCES_NOT_VERIFIED",
              "reconciliation_tolerance": number(tolerance), "tolerance_reason": data["tolerance_reason"],
              "ratio_precision": "6 decimal places, ROUND_HALF_EVEN; fractions are not percentages",
              "periods": []}
    failed = incomplete = False
    with localcontext() as context:
        context.prec = 80
        context.rounding = ROUND_HALF_EVEN
        for period in data["periods"]:
            vals = {k: decimal(v["value"], k) for k, v in period["values"].items() if v["value"] is not None}
            result = {k: period[k] for k in ("id", "label", "start", "end", "kind", "basis")}
            result["normalized_values"] = period["values"]
            result["coverage"] = {
                "fields_in_scope": len(FIELDS), "reported": len(vals),
                "explicit_missing": sorted(k for k, v in period["values"].items() if v["value"] is None),
                "absent": sorted(FIELDS - period["values"].keys()),
            }

            def evidence(fields):
                refs = {(r["source_id"], r["locator"]) for field in fields
                        for r in period["values"].get(field, {}).get("sources", [])}
                return [{"source_id": sid, "locator": loc} for sid, loc in sorted(refs)]

            result["checks"] = []
            for name, terms in CHECKS.items():
                missing = sorted(set(terms) - vals.keys())
                residual = None if missing else sum((vals[k] * weight for k, weight in terms.items()), Decimal(0))
                status = "UNKNOWN" if missing else ("PASS" if abs(residual) <= tolerance else "FAIL")
                result["checks"].append({"id": name, "status": status, "signed_terms": terms,
                                         "residual": number(residual), "missing": missing,
                                         "sources": evidence(terms)})
                failed |= status == "FAIL"
                incomplete |= status == "UNKNOWN"
            result["metrics"] = []
            for name, (terms, denominator, unit) in METRICS.items():
                required = set(terms) | ({denominator} if denominator else set())
                missing = sorted(required - vals.keys())
                metric = {"id": name, "status": "CALCULATED", "value": None, "unit": unit,
                          "numerator_terms": terms, "denominator": denominator,
                          "missing": missing, "reason": "", "sources": evidence(required)}
                if missing:
                    metric.update(status="UNKNOWN", reason="Required values are missing")
                elif denominator and vals[denominator] <= 0:
                    metric.update(status="UNDEFINED", reason="Denominator is zero or negative; this ratio is not interpreted")
                else:
                    numerator = sum((vals[k] * weight for k, weight in terms.items()), Decimal(0))
                    value = (numerator / vals[denominator]).quantize(Decimal("0.000001")) if denominator else numerator
                    metric["value"] = number(value)
                incomplete |= metric["status"] != "CALCULATED"
                result["metrics"].append(metric)
            result["coverage"].update(checks_evaluated=sum(c["status"] != "UNKNOWN" for c in result["checks"]),
                                      checks_in_scope=len(CHECKS),
                                      metrics_calculated=sum(m["status"] == "CALCULATED" for m in result["metrics"]),
                                      metrics_in_scope=len(METRICS))
            output["periods"].append(result)
    output["status"] = "DISCREPANCY" if failed else "INCOMPLETE" if incomplete else "COMPLETE"
    return output


def clean(value):
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", " ")


def markdown(report):
    lines = ["# Historical statement analysis", "", f"Status: **{report['status']}**", "",
             f"{clean(report['entity']['name'])}; {report['entity']['scope']}; {report['currency']}, scale {report['scale']}.",
             f"Reporting basis: {clean(report['reporting_basis'])}.", "",
             "Source references are supplied declarations, not independently verified evidence. A complete result means only that the listed checks and metrics could be evaluated. No credit opinion or universal benchmark is assigned.",
             f"Reconciliation tolerance: {report['reconciliation_tolerance']} reporting units. Reason: {clean(report['tolerance_reason'])}", ""]
    for period in report["periods"]:
        cov = period["coverage"]
        lines += [f"## {clean(period['label'])}", "",
                  f"{period['start']} to {period['end']}; {period['kind']}; {period['basis']}; flows are not annualized.",
                  f"Coverage: {cov['reported']}/{cov['fields_in_scope']} fields; {cov['checks_evaluated']}/{cov['checks_in_scope']} checks; {cov['metrics_calculated']}/{cov['metrics_in_scope']} metrics.",
                  f"Explicit missing: {', '.join(cov['explicit_missing']) or 'none'}. Absent: {', '.join(cov['absent']) or 'none'}.", "",
                  "| Reconciliation | Status | Residual | Missing inputs |", "|---|---|---:|---|"]
        for check in period["checks"]:
            lines.append(f"| {check['id']} | {check['status']} | {check['residual'] if check['residual'] is not None else '—'} | {', '.join(check['missing']) or '—'} |")
        lines += ["", "| Metric | Status | Value | Unit / reason |", "|---|---|---:|---|"]
        for metric in period["metrics"]:
            lines.append(f"| {metric['id']} | {metric['status']} | {metric['value'] if metric['value'] is not None else '—'} | {metric['unit']}; {clean(metric['reason']) or 'calculated'} |")
        lines += ["", "See report.json for normalized values, exact formulas and source references for every check and metric.", ""]
    lines += ["## Declared source register", "", "| ID | Document | Audit status |", "|---|---|---|"]
    for source in report["sources"]:
        lines.append(f"| {clean(source['id'])} | {clean(source['document'])}: {clean(source['title'])} | {source['audit_status']} |")
    return "\n".join(lines) + "\n"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def run(input_path, output_dir):
    input_path, output_dir = Path(input_path), Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise InputError("Output directory must be new; existing outputs are never overwritten")
    raw = input_path.read_bytes()
    if len(raw) > 5_000_000:
        raise InputError("Input exceeds the 5 MB normalized-data limit")
    report = analyze(loads(raw))
    if input_path.read_bytes() != raw:
        raise InputError("Input changed during analysis; rerun on stable inputs")
    report["input"] = {"file": input_path.name, "sha256": digest(raw)}
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(markdown(report), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Normalized statement JSON")
    parser.add_argument("--out", required=True, help="New directory for report.json and report.md")
    args = parser.parse_args(argv)
    try:
        report = run(args.input, args.out)
    except (InputError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"{report['status']}: {len(report['periods'])} period(s); {Path(args.out) / 'report.md'}")
    return {"COMPLETE": 0, "DISCREPANCY": 1, "INCOMPLETE": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
