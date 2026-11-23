"""Compare cash retention and distributions at contractual payment dates."""
from fractions import Fraction


def minor_units(value, places):
    """Convert a settled amount into an integer count of currency minor units."""
    scaled = Fraction(value) * 10 ** places
    if scaled.denominator != 1:
        raise ValueError("Settlement amount exceeds the report's currency precision")
    return scaled.numerator


def money(amount, places):
    sign = "-" if amount < 0 else ""
    whole, tail = divmod(abs(amount), 10 ** places)
    return f"{sign}{whole}.{tail:0{places}d}" if places else f"{sign}{whole}"


def reserve_requirement(net_cash):
    """Return minimum opening cash and, if starting at zero works, minimum retention cap."""
    if not net_cash:
        raise ValueError("At least one payment period is required")
    balance = low = peak = drawdown = 0
    for net in net_cash:
        balance += net
        low = min(low, balance)
        peak = max(peak, balance)
        drawdown = max(drawdown, peak - balance)
    return -low, drawdown if low == 0 else None


def waterfall(periods, limit, places):
    """Apply each settlement, identify any unfunded amount, then distribute excess cash."""
    balance = distributed = funding_needed = 0
    rows = []
    for name, cfads, service in periods:
        opening = balance
        available = opening + cfads - service
        gap = max(-available, 0)
        available += gap
        distribution = 0 if limit is None else max(available - limit, 0)
        balance = available - distribution
        if opening + cfads + gap != service + distribution + balance:
            raise ArithmeticError("Cash movements do not reconcile")
        distributed += distribution
        funding_needed += gap
        rows.append({"period": name, "opening": money(opening, places),
                     "cash_available_for_debt_service": money(cfads, places),
                     "debt_service": money(service, places), "funding_needed": money(gap, places),
                     "distribution": money(distribution, places), "closing": money(balance, places)})
    return {"closing": money(balance, places), "distributions": money(distributed, places),
            "funding_needed": money(funding_needed, places), "periods": rows}


def analyze(scenarios):
    if (scenarios["model"] != "operating-cash-bridge-v1" or scenarios["unit"] != "currency units"
            or scenarios["checks"] != {"base_preserved": "PASS"}):
        raise ValueError("Expected a reconciled operating cash bridge in currency units")
    places = scenarios["money_decimals"]
    results = []
    for case in scenarios["cases"]:
        periods = [(row["period"]["id"], minor_units(row["cfads"], places),
                    minor_units(row["debt_service"], places)) for row in case["periods"]]
        net = [cfads - service for _, cfads, service in periods]
        opening, cap = reserve_requirement(net)
        policies = {"retain_all": waterfall(periods, None, places),
                    "distribute_all": waterfall(periods, 0, places)}
        if cap is not None:
            policies["minimum_cap"] = waterfall(periods, cap, places)
            if minor_units(policies["minimum_cap"]["funding_needed"], places) != 0:
                raise ArithmeticError("Minimum cap does not cover every payment")
        results.append({"case": case["id"], "net_cash": money(sum(net), places),
                        "shortfall_periods": [p[0] for p, value in zip(periods, net) if value < 0],
                        "minimum_opening_cash_with_full_retention": money(opening, places),
                        "minimum_retention_cap_from_zero": None if cap is None else money(cap, places),
                        "policies": policies})
    return {"currency": scenarios["currency"], "money_decimals": places,
            "basis": "Period-end settlement of displayed CFADS and debt service; zero opening cash in policy runs.",
            "cases": results}


def markdown(report):
    rows = ["# Cash at the payment date", "",
            f"All amounts are in {report['currency']}. Each policy starts with zero cash.", "",
            "| Operating case | Net cash after debt service | Shortfall periods | Funding needed if cash is retained | Funding needed if surpluses are distributed | Minimum retention cap from zero |",
            "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for case in report["cases"]:
        policies = case["policies"]
        cap = case["minimum_retention_cap_from_zero"]
        rows.append(f"| {case['case']} | {case['net_cash']} | {len(case['shortfall_periods'])} | "
                    f"{policies['retain_all']['funding_needed']} | {policies['distribute_all']['funding_needed']} | "
                    f"{cap if cap is not None else 'Requires opening cash'} |")
    rows.extend(["", "A shortfall period has less operating cash available than debt service due. "
                 "Earlier cash can cover a later shortfall only if the distribution policy retains it.",
                 "", "The minimum retention cap is the smallest end-of-period cash limit that covers every modeled payment from a zero opening balance. "
                 "It uses the entire scenario path. Funding needed measures the gap at a payment date.", ""])
    return "\n".join(rows)
