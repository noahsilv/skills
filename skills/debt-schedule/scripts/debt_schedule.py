#!/usr/bin/env python3
"""An exact, event-dated schedule for one fixed-rate non-revolving facility."""

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


class InputError(ValueError):
    """An input does not satisfy the documented contract."""


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
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
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs,
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


def decimal(value, where, *, places=12, positive=False):
    # Decimal strings avoid binary floating point and implicit coercion of booleans.
    if (type(value) is not str or len(value) > 40
            or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value)):
        raise InputError(f"{where}: expected a nonnegative plain decimal string")
    whole, _, tail = value.partition(".")
    if len(whole) > 24 or len(tail) > places:
        raise InputError(f"{where}: maximum 24 whole digits and {places} decimal places")
    result = Fraction(value)
    if positive and result <= 0:
        raise InputError(f"{where}: must be positive")
    return result


def iso_date(value, where):
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise InputError(f"{where}: expected YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InputError(f"{where}: invalid calendar date") from exc


def validate(data):
    keys(data, {"schema_version", "facility_id", "currency", "money_decimals",
                "start_date", "maturity_date", "commitment", "opening_balance", "prior_drawdowns",
                "annual_rate", "day_count", "payment_dates", "events"}, "facility")
    integer(data["schema_version"], 1, 1, "schema_version")
    if (type(data["facility_id"]) is not str
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", data["facility_id"])):
        raise InputError("facility_id: use 1..64 ASCII letters, digits, underscores or hyphens; begin with a letter")
    if type(data["currency"]) is not str or not re.fullmatch(r"[A-Z]{3}", data["currency"]):
        raise InputError("currency: expected three uppercase letters (a label, not a currency lookup)")
    places = integer(data["money_decimals"], 0, 6, "money_decimals")
    start = iso_date(data["start_date"], "start_date")
    maturity = iso_date(data["maturity_date"], "maturity_date")
    if maturity <= start:
        raise InputError("maturity_date must follow start_date")
    commitment = decimal(data["commitment"], "commitment", places=places, positive=True)
    opening = decimal(data["opening_balance"], "opening_balance", places=places)
    prior_draws = decimal(data["prior_drawdowns"], "prior_drawdowns", places=places)
    if not opening <= prior_draws <= commitment:
        raise InputError("require opening_balance <= prior_drawdowns <= commitment")
    rate = decimal(data["annual_rate"], "annual_rate")
    if type(data["day_count"]) is not str or data["day_count"] not in {"ACT/365F", "ACT/360"}:
        raise InputError("day_count must be ACT/365F or ACT/360")
    if type(data["payment_dates"]) is not list or not 1 <= len(data["payment_dates"]) <= 1000:
        raise InputError("payment_dates must contain 1..1000 dates")
    payments = tuple(iso_date(v, "payment_dates") for v in data["payment_dates"])
    if payments != tuple(sorted(set(payments))) or payments[0] <= start or payments[-1] != maturity:
        raise InputError("payment_dates must strictly increase after start_date and end at maturity_date")
    if type(data["events"]) is not list or len(data["events"]) > 5000:
        raise InputError("events must be an array of at most 5000 entries")
    grouped = {}
    for i, event in enumerate(data["events"]):
        where = f"events[{i}]"
        keys(event, {"date", "type", "amount"}, where)
        day = iso_date(event["date"], where + ".date")
        kind = event["type"]
        if type(kind) is not str or kind not in {"drawdown", "repayment"}:
            raise InputError(f"{where}.type: expected drawdown or repayment")
        if not start <= day <= maturity or (day == maturity and kind == "drawdown"):
            raise InputError(f"{where}: event outside facility term or drawdown at maturity")
        amount = decimal(event["amount"], where + ".amount", places=places, positive=True)
        bucket = grouped.setdefault(day, {})
        if kind in bucket:
            raise InputError(f"{where}: duplicate event date/type; combine explicitly")
        bucket[kind] = amount
    return {"id": data["facility_id"], "currency": data["currency"], "places": places,
            "start": start, "maturity": maturity, "commitment": commitment,
            "opening": opening, "prior_draws": prior_draws, "rate": rate,
            "basis": 365 if data["day_count"] == "ACT/365F" else 360,
            "day_count": data["day_count"], "payments": payments, "events": grouped}


def rounded(value, places):
    """Round a Fraction halfway away from zero, without Decimal context loss."""
    sign = -1 if value < 0 else 1
    numerator = abs(value.numerator) * 10 ** places
    quotient, remainder = divmod(numerator, value.denominator)
    if remainder * 2 >= value.denominator:
        quotient += 1
    return Fraction(sign * quotient, 10 ** places)


def fixed(value, places):
    value = rounded(Fraction(value), places)
    scaled = abs(value.numerator * 10 ** places // value.denominator)
    whole, decimals = divmod(scaled, 10 ** places)
    sign = "-" if value < 0 else ""
    return f"{sign}{whole}" + (f".{decimals:0{places}d}" if places else "")


def exact(value):
    return f"{value.numerator}/{value.denominator}"


def calculate(data):
    """Validate and calculate; never mutate the supplied mapping or arrays."""
    terms = validate(data)
    balance = terms["opening"]
    used = terms["prior_draws"]  # Historical repayments do not restore non-revolving capacity.
    period_opening = balance
    draws = repaid = accrued = Fraction(0)
    start = cursor = terms["start"]
    periods, segments = [], []
    payment_set = set(terms["payments"])
    timeline = sorted(set(terms["events"]) | payment_set | {start})
    for day in timeline:
        if day > cursor:
            days = (day - cursor).days
            interest = balance * terms["rate"] * Fraction(days, terms["basis"])
            accrued += interest
            segments.append({"period_end": next(p for p in terms["payments"] if p >= day).isoformat(),
                             "start_date": cursor.isoformat(), "end_date": day.isoformat(),
                             "days": days, "principal": fixed(balance, terms["places"]),
                             "interest_exact": exact(interest), "interest_display": fixed(interest, 12)})
        event = terms["events"].get(day, {})
        draw = event.get("drawdown", Fraction(0))
        repayment = event.get("repayment", Fraction(0))
        used += draw
        if used > terms["commitment"]:
            raise InputError(f"{day}: cumulative draws including prior_drawdowns exceed non-revolving commitment")
        balance += draw
        if repayment > balance:
            raise InputError(f"{day}: repayment exceeds outstanding principal after same-day drawdown")
        balance -= repayment
        draws += draw
        repaid += repayment
        if day in payment_set:
            paid_interest = rounded(accrued, terms["places"])
            if period_opening + draws - repaid != balance:
                raise ArithmeticError("principal reconciliation failed")
            periods.append({"start_date": start.isoformat(), "end_date": day.isoformat(),
                            "days": (day - start).days,
                            "opening_balance": fixed(period_opening, terms["places"]),
                            "drawdowns": fixed(draws, terms["places"]),
                            "repayments": fixed(repaid, terms["places"]),
                            "closing_balance": fixed(balance, terms["places"]),
                            "interest_exact": exact(accrued),
                            "interest_paid": fixed(paid_interest, terms["places"]),
                            "debt_service": fixed(repaid + paid_interest, terms["places"])})
            start = day
            period_opening = balance
            draws = repaid = accrued = Fraction(0)
        cursor = day
    if balance:
        raise InputError("explicit repayments leave outstanding principal at maturity; no balancing repayment is inserted")
    totals = {key: fixed(sum((Fraction(row[key]) for row in periods), Fraction(0)), terms["places"])
              for key in ("drawdowns", "repayments", "interest_paid", "debt_service")}
    return {"schema_version": 1, "model": "fixed-rate-non-revolving-v1",
            "facility_id": terms["id"], "currency": terms["currency"],
            "unit": "currency units", "money_decimals": terms["places"],
            "annual_rate": data["annual_rate"], "day_count": terms["day_count"],
            "commitment": data["commitment"], "opening_balance": data["opening_balance"],
            "prior_drawdowns": data["prior_drawdowns"],
            "unused_commitment": fixed(terms["commitment"] - used, terms["places"]),
            "periods": periods, "accrual_segments": segments, "totals": totals,
            "checks": {"principal_roll_forward": "PASS", "maturity_balance_zero": "PASS"}}


def csv_text(rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def render_report(result):
    lines = [f"# Debt schedule: {result['facility_id']}", "",
             f"Amounts: {result['currency']} currency units. Fixed annual rate: {result['annual_rate']}. "
             f"Day count: {result['day_count']}.", "",
             "Interest accrues on actual calendar days, start inclusive and end exclusive. "
             "Dated cash events take effect after accrual to that date; same-day drawdowns precede repayments. "
             "Events on a payment date appear in that period's principal movements and affect the next accrual interval.", "",
             "Interest is paid at each listed payment date and rounded half up once per period. "
             "Debt service is principal repaid plus rounded interest; draws are excluded. "
             "Accrual fractions are exact in report.json and accruals.csv.", "",
             "| End date | Opening | Draws | Repayments | Closing | Interest paid | Debt service |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for row in result["periods"]:
        lines.append("| " + " | ".join(str(row[k]) for k in
                     ("end_date", "opening_balance", "drawdowns", "repayments", "closing_balance", "interest_paid", "debt_service")) + " |")
    lines += ["", "Totals: " + "; ".join(f"{k.replace('_', ' ')} {v}" for k, v in result["totals"].items()) + ".",
              f"Unused non-revolving commitment: {result['unused_commitment']}.", "",
              "Checks: principal roll-forward PASS; zero principal at maturity PASS.", "",
              "Scope: one fixed-rate, single-currency facility. No fee, tax, default, holiday, "
              "rate-reset, compounding, capitalization, refinancing, FX or covenant calculation. "
              "This is a calculation of the supplied terms; no term-sheet review or spreadsheet recalculation is performed.", ""]
    if "input_sha256" in result:
        lines += [f"Input SHA-256: `{result['input_sha256']}`", ""]
    return "\n".join(lines)


def run(input_path, output_path):
    data, digest = read_input(input_path)
    result = calculate(data)
    result["input_sha256"] = digest
    files = {"report.json": json.dumps(result, indent=2) + "\n",
             "schedule.csv": csv_text(result["periods"]),
             "accruals.csv": csv_text(result["accrual_segments"]),
             "report.md": render_report(result)}
    if hashlib.sha256(Path(input_path).read_bytes()).hexdigest() != digest:
        raise InputError("input changed during calculation; no output written")
    output = Path(output_path)
    output.mkdir()  # Exclusive creation; existing paths, including symlinks, are refused.
    for name, content in files.items():
        with (output / name).open("x", encoding="utf-8", newline="") as handle:
            handle.write(content)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="UTF-8 JSON terms and dated cash events")
    parser.add_argument("--out", required=True, help="new output directory; parent must exist")
    args = parser.parse_args(argv)
    try:
        run(args.input, args.out)
    except (InputError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Schedule written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
