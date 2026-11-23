"""Trace selected debt and cash figures to exact disclosure lines and transaction inputs."""
from decimal import Decimal, localcontext
import hashlib
import json
import re


FILES = {"disclosure": "synthetic-disclosure.txt", "normalized": "normalized.json",
         "statements": "statements/report.json", "opening": "opening.json",
         "transactions": "transactions.json", "closing": "closing.json"}
LABELS = {
    "cash_and_equivalents": "Cash and equivalents",
    "debt_current": "Current borrowings excluding leases",
    "debt_noncurrent": "Noncurrent borrowings excluding leases",
    "leases_current": "Current lease liabilities",
    "leases_noncurrent": "Noncurrent lease liabilities",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return format(value.normalize(), "f") if value else "0"


class FinancialTrace:
    def __init__(self):
        self.nodes = {}

    def add(self, key, value, unit, file, locator, factors=()):
        require(key not in self.nodes, f"Duplicate trace ID: {key}")
        value = Decimal(value)
        inputs = []
        derived = Decimal(0)
        for parent, coefficient in factors:
            require(parent in self.nodes, f"Missing upstream value {parent}")
            if coefficient in {1, -1}:
                require(self.nodes[parent]["unit"] == unit, f"Unit mismatch at {key}")
            derived += Decimal(self.nodes[parent]["value"]) * Decimal(coefficient)
            inputs.append({"id": parent, "coefficient": str(coefficient)})
        if inputs:
            require(value == derived, f"{key}: recomputed {derived}, recorded {value}")
        self.nodes[key] = {"value": canonical(value), "unit": unit, "file": file, "locator": locator, "inputs": inputs}


def build(folder):
    raw = {name: (folder / filename).read_bytes() for name, filename in FILES.items()}
    digests = {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()}
    statements, opening, transactions, closing = (json.loads(raw[k]) for k in ("statements", "opening", "transactions", "closing"))
    require(statements["input"]["sha256"] == digests["normalized"], "Statement input version differs")
    require(opening["source"]["sha256"] == digests["statements"], "Opening statement version differs")
    require(closing["input_sha256"] == {k: digests[k] for k in ("opening", "transactions")}, "Closing input version differs")
    require(statements["status"] == "COMPLETE" and statements["scale"] == opening["scale"] == "1000000"
            and statements["currency"] == opening["currency"] == "USD", "Unexpected statement status or units")
    source, = statements["sources"]
    require(source["document"] == FILES["disclosure"], "The source register names a different disclosure")
    require(source["sha256"] == digests["disclosure"], "Disclosure version differs from the statement register")
    period, = statements["periods"]
    require(statements["entity"]["name"] == opening["entity"] and statements["entity"]["scope"] == opening["scope"]
            and period["end"] == opening["as_of"], "Opening position and statement scope differ")
    for key in ("entity", "scope", "as_of", "currency", "scale"):
        require(opening[key] == closing[key] == transactions[key], f"Transaction {key} differs")
    pages = raw["disclosure"].decode("utf-8").split("\f")
    context = (f"{opening['entity']}; {opening['scope']}; currency USD; scale 1000; "
               f"period {period['start']} to {period['end']}.")
    require(context in pages[0].splitlines(), "Disclosure does not support the source basis")
    trace = FinancialTrace()
    unit = "USD millions"
    with localcontext() as ctx:
        ctx.prec = 64
        for field, label in LABELS.items():
            row = period["normalized_values"][field]
            ref, = row["sources"]
            require(ref["source_id"] == source["id"], f"Different disclosure for {field}")
            found = re.fullmatch(r"physical text page ([1-9][0-9]*): (.+)", ref["locator"])
            require(found is not None, f"Unrecognized locator for {field}")
            page, excerpt = int(found[1]), found[2]
            require(page <= len(pages) and pages[page - 1].splitlines().count(excerpt) == 1,
                    f"Disclosure excerpt missing or ambiguous for {field}")
            quoted = re.fullmatch(re.escape(label) + r" (0|[1-9][0-9]{0,2}(?:,[0-9]{3})*)", excerpt)
            require(quoted is not None, f"Expected a labeled nonnegative source amount for {field}")
            reported = f"reported.{field}"
            normalized = f"statement.{field}"
            trace.add(reported, quoted[1].replace(",", ""), "USD thousands", "disclosure", ref["locator"])
            trace.add(normalized, row["value"], unit, "statements", f"/periods/0/normalized_values/{field}/value",
                      [(reported, "0.001")])
            require(opening["source"]["locators"][field] == f"{source['id']}, {ref['locator']}", f"Opening locator differs for {field}")
            trace.add(f"opening.{field}", opening["balances"][field], unit, "opening", f"/balances/{field}", [(normalized, 1)])

        debt_fields = ("debt_current", "debt_noncurrent", "leases_current", "leases_noncurrent")
        gross_key = "gross_debt_including_leases"
        net_key = "net_debt_including_leases"
        trace.add("opening.gross_debt", closing["opening_metrics"][gross_key], unit, "closing", f"/opening_metrics/{gross_key}",
                  [(f"opening.{field}", 1) for field in debt_fields])
        trace.add("opening.net_debt", closing["opening_metrics"][net_key], unit, "closing", f"/opening_metrics/{net_key}",
                  [("opening.gross_debt", 1), ("opening.cash_and_equivalents", -1)])
        case_ids = [c["id"] for c in transactions["cases"]]
        require(len(set(case_ids)) == len(case_ids) and case_ids == [c["id"] for c in closing["cases"]],
                "Closing cases and transaction inputs differ")
        for index, (case, result) in enumerate(zip(transactions["cases"], closing["cases"])):
            require(result["status"] == "BALANCED", "Trace requires a funded closing case")
            ident, location = case["id"], f"/cases/{index}"
            f = f"{ident}.flow."
            c = f"{ident}.closing."
            for name, value in case["flows"].items():
                trace.add(f + name, value, unit, "transactions", f"{location}/flows/{name}")
            def balance(name, dependencies):
                trace.add(c + name, result["closing_balances"][name], unit, "closing",
                          f"{location}/closing_balances/{name}", dependencies)
            def metric(short, name, dependencies):
                trace.add(c + short, result["closing_metrics"][name], unit, "closing",
                          f"{location}/closing_metrics/{name}", dependencies)
            balance("cash_and_equivalents", [("opening.cash_and_equivalents", 1), (f + "draw_current", 1),
                    (f + "draw_noncurrent", 1), (f + "equity_contribution", 1), (f + "repay_current", -1),
                    (f + "repay_noncurrent", -1), (f + "capital_spending", -1), (f + "cash_expense", -1)])
            for term in ("current", "noncurrent"):
                balance("debt_" + term, [("opening.debt_" + term, 1), (f + "draw_" + term, 1), (f + "repay_" + term, -1)])
                balance("leases_" + term, [("opening.leases_" + term, 1)])
            metric("gross_debt", gross_key, [(c + field, 1) for field in debt_fields])
            metric("net_debt", net_key, [(c + "gross_debt", 1), (c + "cash_and_equivalents", -1)])
            trace.add(f"{ident}.change_in_net_debt", result["change_in_net_debt"], unit, "closing",
                      location + "/change_in_net_debt", [(c + "net_debt", 1), ("opening.net_debt", -1)])
    return {"schema_version": 1, "entity": opening["entity"], "as_of": opening["as_of"], "scope": opening["scope"],
            "files": {k: {"path": FILES[k], "sha256": digest} for k, digest in digests.items()}, "nodes": trace.nodes}


def verified(folder):
    expected = json.loads((folder / "graph.json").read_bytes())
    actual = build(folder)
    require(actual == expected, "Recorded trace differs from the current inputs and reports")
    return actual


def related(graph, key, direction):
    nodes = graph["nodes"]
    require(key in nodes, f"Unknown trace ID: {key}")
    links = {name: [edge["id"] for edge in node["inputs"]] for name, node in nodes.items()}
    if direction == "downstream":
        children = {name: [] for name in nodes}
        for child, parents in links.items():
            for parent in parents:
                children[parent].append(child)
        links = children
    elif direction != "upstream":
        raise ValueError("Choose upstream or downstream")
    found = {key}
    pending = [key]
    while pending:
        for neighbor in links[pending.pop()]:
            if neighbor not in found:
                found.add(neighbor)
                pending.append(neighbor)
    return [name for name in nodes if name in found]


def impact(original, revised, key):
    require((original["entity"], original["as_of"], original["scope"]) ==
            (revised["entity"], revised["as_of"], revised["scope"]), "Cannot compare different reporting bases")
    before, after = original["nodes"], revised["nodes"]
    require(before.keys() == after.keys(), "Cannot compare different trace coverage")
    for name in before:
        require(before[name]["inputs"] == after[name]["inputs"] and before[name]["unit"] == after[name]["unit"],
                f"Definition or unit changed for {name}")
    related_ids = related(original, key, "downstream")
    changed_leaves = {name for name in before if not before[name]["inputs"] and before[name]["value"] != after[name]["value"]}
    return [{"id": name, "original": before[name]["value"], "revised": after[name]["value"],
             "unit": after[name]["unit"], "value_changed": before[name]["value"] != after[name]["value"],
             "changed_upstream_inputs": sorted(changed_leaves.intersection(related(original, name, "upstream")))}
            for name in related_ids]
