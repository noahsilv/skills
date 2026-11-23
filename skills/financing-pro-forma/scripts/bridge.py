"""Prepare a closing-date financing bridge from a sourced opening balance sheet."""
import argparse
from datetime import date
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import re


BASIS = ("entity", "scope", "as_of", "currency", "scale")
BALANCES = ("total_assets", "total_liabilities", "total_equity", "current_assets", "current_liabilities",
            "cash_and_equivalents", "debt_current", "debt_noncurrent", "leases_current", "leases_noncurrent")
FLOWS = ("draw_current", "draw_noncurrent", "repay_current", "repay_noncurrent",
         "equity_contribution", "capital_spending", "cash_expense")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read(path):
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs), hashlib.sha256(raw).hexdigest()


def fields(value, names, label):
    require(isinstance(value, dict) and set(value) == set(names), f"{label} requires exactly {', '.join(names)}")


def text(value, label):
    require(isinstance(value, str) and value.strip() == value and 0 < len(value) <= 500
            and all(ord(c) >= 32 for c in value), f"Invalid {label}")
    return value


def amount(value, label):
    require(isinstance(value, str) and re.fullmatch(r"-?(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,6})?", value),
            f"{label} must be a decimal string with up to 18 whole digits and six decimal places")
    return Decimal(value)


def number(value):
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def basis(data):
    result = {key: text(data[key], key) for key in BASIS}
    require(re.fullmatch(r"[A-Z]{3}", result["currency"]), "Currency must be a three-letter code")
    require(result["scale"] in {"1", "1000", "1000000"}, "Unsupported reporting scale")
    require(date.fromisoformat(result["as_of"]).isoformat() == result["as_of"], "Expected an ISO date")
    return result


def balances(values):
    fields(values, BALANCES, "opening balances")
    b = {key: amount(values[key], key) for key in BALANCES}
    require(all(b[key] >= 0 for key in BALANCES if key != "total_equity"), "Negative asset or liability balance")
    require(b["total_assets"] == b["total_liabilities"] + b["total_equity"], "Opening balance sheet does not balance")
    require(b["cash_and_equivalents"] <= b["current_assets"] <= b["total_assets"], "Cash or current assets exceed their total")
    require(b["debt_current"] + b["leases_current"] <= b["current_liabilities"],
            "Current borrowings and leases exceed current liabilities")
    require(b["debt_noncurrent"] + b["leases_noncurrent"] <= b["total_liabilities"] - b["current_liabilities"],
            "Noncurrent borrowings and leases exceed noncurrent liabilities")
    return b


def validate_opening(opening):
    fields(opening, ("schema_version", *BASIS, "source", "balances"), "opening position")
    require(type(opening["schema_version"]) is int and opening["schema_version"] == 1, "Unsupported opening schema")
    basis(opening)
    source = opening["source"]
    fields(source, ("label", "sha256", "locators"), "opening source")
    text(source["label"], "source label")
    require(isinstance(source["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", source["sha256"]), "Invalid source hash")
    fields(source["locators"], BALANCES, "source locators")
    for key in BALANCES:
        text(source["locators"][key], f"locator for {key}")
    return balances(opening["balances"])


def from_statement_report(report, digest, period_id):
    require(report.get("status") == "COMPLETE", "Expected a complete statement report")
    selected = [p for p in report["periods"] if p["id"] == period_id]
    require(len(selected) == 1, "Statement period must match exactly once")
    period, = selected
    checks = [c for c in period["checks"] if c["id"] == "balance_sheet"]
    require(len(checks) == 1 and checks[0]["status"] == "PASS", "Statement balance sheet did not pass")
    values = period["normalized_values"]
    opening = {"schema_version": 1, "entity": report["entity"]["name"], "scope": report["entity"]["scope"],
               "as_of": period["end"], "currency": report["currency"], "scale": report["scale"],
               "source": {"label": f"Historical statement report, {period_id}", "sha256": digest, "locators": {}},
               "balances": {}}
    for key in BALANCES:
        row = values[key]
        require(isinstance(row["sources"], list) and row["sources"], f"Missing statement reference for {key}")
        locators = [text(ref["source_id"], "source ID") + ", " + text(ref["locator"], "locator") for ref in row["sources"]]
        opening["source"]["locators"][key] = " | ".join(locators)
        opening["balances"][key] = row["value"]
    validate_opening(opening)
    return opening


def metrics(b):
    borrowings = b["debt_current"] + b["debt_noncurrent"]
    leases = b["leases_current"] + b["leases_noncurrent"]
    gross = borrowings + leases
    return {"borrowings_excluding_leases": number(borrowings), "lease_liabilities": number(leases),
            "gross_debt_including_leases": number(gross),
            "net_debt_including_leases": number(gross - b["cash_and_equivalents"]),
            "gross_debt_to_equity": format(gross / b["total_equity"], ".6f") if b["total_equity"] > 0 else None,
            "current_ratio": format(b["current_assets"] / b["current_liabilities"], ".6f") if b["current_liabilities"] > 0 else None}


def calculate_case(start, case):
    fields(case, ("id", "flows"), "case")
    require(isinstance(case["id"], str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", case["id"]), "Invalid case ID")
    fields(case["flows"], FLOWS, "transaction flows")
    flow = {k: amount(case["flows"][k], k) for k in FLOWS}
    require(all(v >= 0 for v in flow.values()), "Use nonnegative magnitudes for transaction flows")
    for term in ("current", "noncurrent"):
        require(flow["repay_" + term] <= start["debt_" + term], f"Repayment exceeds existing {term} borrowings")
    raised = flow["draw_current"] + flow["draw_noncurrent"]
    repaid = flow["repay_current"] + flow["repay_noncurrent"]
    sources = raised + flow["equity_contribution"]
    uses = repaid + flow["capital_spending"] + flow["cash_expense"]
    change = sources - uses
    closing_cash = start["cash_and_equivalents"] + change
    gap = max(-closing_cash, Decimal(0))
    result = {"id": case["id"], "status": "FUNDING_GAP" if gap else "BALANCED",
              "flows": {k: number(v) for k, v in flow.items()},
              "new_funding": number(sources), "transaction_uses": number(uses), "change_in_cash": number(change),
              "cash_before_additional_funding": number(closing_cash), "funding_gap": number(gap),
              "closing_balances": None, "closing_metrics": None, "change_in_net_debt": None}
    if gap:
        return result
    closing = dict(start)
    closing["cash_and_equivalents"] = closing_cash
    closing["current_assets"] += change
    closing["total_assets"] += change + flow["capital_spending"]
    closing["current_liabilities"] += flow["draw_current"] - flow["repay_current"]
    closing["total_liabilities"] += raised - repaid
    closing["total_equity"] += flow["equity_contribution"] - flow["cash_expense"]
    for term in ("current", "noncurrent"):
        closing["debt_" + term] += flow["draw_" + term] - flow["repay_" + term]
    require(closing["total_assets"] == closing["total_liabilities"] + closing["total_equity"],
            "Closing balance sheet failed reconciliation")
    closing_metrics = metrics(closing)
    delta_net = Decimal(closing_metrics["net_debt_including_leases"]) - Decimal(metrics(start)["net_debt_including_leases"])
    require(delta_net == flow["capital_spending"] + flow["cash_expense"] - flow["equity_contribution"],
            "Net debt change does not reconcile to uses and equity")
    result.update(closing_balances={k: number(v) for k, v in closing.items()}, closing_metrics=closing_metrics,
                  change_in_net_debt=number(delta_net))
    return result


def calculate(opening, proposals):
    with localcontext() as ctx:
        ctx.prec = 64
        start = validate_opening(opening)
        fields(proposals, ("schema_version", *BASIS, "cases"), "transactions")
        require(type(proposals["schema_version"]) is int and proposals["schema_version"] == 1, "Unsupported transaction schema")
        require(basis(opening) == basis(proposals), "The opening position and transaction reporting bases differ")
        require(isinstance(proposals["cases"], list) and 0 < len(proposals["cases"]) <= 100, "Supply one to 100 cases")
        results = [calculate_case(start, case) for case in proposals["cases"]]
        require(len({r["id"] for r in results}) == len(results), "Duplicate transaction case ID")
        return {"schema_version": 1, **basis(opening), "source": opening["source"],
                "opening_balances": opening["balances"], "opening_metrics": metrics(start), "cases": results}


def write_new(path, data):
    payload = json.dumps(data, indent=2) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as file:
        file.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prepare = commands.add_parser("prepare", help="extract an opening position from a statement-analysis report")
    prepare.add_argument("statement_report", type=Path)
    prepare.add_argument("--period", required=True)
    bridge = commands.add_parser("bridge", help="calculate and compare financing cases")
    bridge.add_argument("opening", type=Path)
    bridge.add_argument("transactions", type=Path)
    for cmd in (prepare, bridge):
        cmd.add_argument("--out", type=Path, required=True, help="new JSON output file")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            report, digest = read(args.statement_report)
            output = from_statement_report(report, digest, args.period)
            require(hashlib.sha256(args.statement_report.read_bytes()).hexdigest() == digest, "Statement report changed during preparation")
            write_new(args.out, output)
            print(f"Prepared opening position for {output['as_of']}.")
            return 0
        opening, opening_hash = read(args.opening)
        proposals, transaction_hash = read(args.transactions)
        output = calculate(opening, proposals)
        output["input_sha256"] = {"opening": opening_hash, "transactions": transaction_hash}
        require(hashlib.sha256(args.opening.read_bytes()).hexdigest() == opening_hash
                and hashlib.sha256(args.transactions.read_bytes()).hexdigest() == transaction_hash,
                "Financing inputs changed during calculation")
        write_new(args.out, output)
        for case in output["cases"]:
            delta = case["change_in_net_debt"] if case["change_in_net_debt"] is not None else "unavailable"
            print(f"{case['id']}: {case['status']}, change in net debt {delta}, "
                  f"funding gap {case['funding_gap']} ({output['currency']}, scale {output['scale']})")
        return int(any(c["status"] == "FUNDING_GAP" for c in output["cases"]))
    except (ValueError, KeyError, TypeError, OSError, AttributeError) as exc:
        parser.exit(2, f"Financing bridge: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
