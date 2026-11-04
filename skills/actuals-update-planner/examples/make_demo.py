#!/usr/bin/env python3
"""Create entirely synthetic annual or cumulative-quarter planning inputs."""
import argparse
import hashlib
import json
from pathlib import Path

from openpyxl import Workbook


def make_demo(output, case="annual"):
    if case not in ("annual", "cumulative"):
        raise ValueError("case must be annual or cumulative")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    cumulative = case == "cumulative"
    entity = "Cedar Circuit Components (synthetic)"
    start, end = ("2025-04-01", "2025-06-30") if cumulative else ("2025-01-01", "2025-12-31")
    source_start = "2025-01-01"
    status = "interim" if cumulative else "audited"
    prior_header, live_header = ("Q1 2025A", "Q2 2025E") if cumulative else ("FY2024A", "FY2025E")
    actual_header = "Q2 2025A" if cumulative else "FY2025A"
    future_headers = ("Q3 2025E", "Q4 2025E") if cumulative else ("FY2026E", "FY2027E")
    records = [
        ("sales", 5, "Revenue", 300 if cumulative else 1100, 330 if cumulative else 1200,
         "675000" if cumulative else "1280000", "675,000" if cumulative else "1,280,000"),
        ("costs", 6, "Cost of sales", -185 if cumulative else -640, -200 if cumulative else -700,
         "-410000" if cumulative else "-720000", "(410,000)" if cumulative else "(720,000)"),
        ("operating_cash", 9, "Operating cash flow", 50 if cumulative else 150, 60 if cumulative else 170,
         "120000" if cumulative else "185000", "120,000" if cumulative else "185,000"),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Forecast"
    ws["B1"], ws["B2"], ws["B3"] = entity, "consolidated", "USD millions"
    for col, value in zip(("B", "C", "D", "E"), (prior_header, live_header, *future_headers)):
        ws[f"{col}4"] = value
    for _, row, label, prior, estimate, _, _ in records:
        ws[f"A{row}"], ws[f"B{row}"], ws[f"C{row}"] = label, prior, estimate
        ws[f"D{row}"] = f"=C{row}*(1+D8)"
        ws[f"E{row}"] = f"=D{row}*(1+E8)"
    ws["A7"] = "Gross profit"
    ws["A8"] = "Growth assumption"
    for col in ("B", "C", "D", "E"):
        ws[f"{col}7"] = f"=SUM({col}5:{col}6)"
        ws[f"{col}8"] = 0.05
    wb.save(output / "model.xlsx")
    wb.close()
    context = f"{entity}; consolidated; currency USD; scale 1000; period {source_start} to {end}."
    audit = f"Synthetic {status} status declaration for this example. No real auditor or assurance."
    lines = [f"{label} {printed}" for _, _, label, _, _, _, printed in records]
    if not cumulative:
        # Additional fictional statement facts connect this case to the
        # financial-statement-analysis example without a runtime dependency.
        lines += ["Total assets 1,300,000", "Total liabilities 650,000", "Total equity 650,000",
                  "Current assets 500,000", "Current liabilities 240,000", "Cash and equivalents 150,000",
                  "Current borrowings excluding leases 90,000", "Noncurrent borrowings excluding leases 300,000",
                  "Current lease liabilities 15,000", "Noncurrent lease liabilities 45,000",
                  "Gross profit 560,000", "Operating expenses (310,000)", "Operating profit 250,000",
                  "Net income 180,000", "Opening cash 100,000", "Closing cash 150,000",
                  "Investing cash flow (110,000)", "Financing cash flow (25,000)", "FX cash movement 0",
                  "Opening equity 500,000", "Other comprehensive income 0", "Owner contributions 20,000",
                  "Dividends 50,000"]
    source_text = "Fictional financial disclosure for software demonstration only.\n" + context + "\n" + audit + "\f" + "\n".join(lines) + "\n"
    source_path = sources / "synthetic-disclosure.txt"
    source_path.write_text(source_text, encoding="utf-8")
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    mapping = {
        "schema_version": 1, "entity": entity, "scope": "consolidated", "model_sha256": sha(output / "model.xlsx"),
        "sheet": "Forecast", "model_context": {"entity_cell": "B1", "scope_cell": "B2", "unit_cell": "B3", "unit_label": "USD millions"},
        "label_column": "A", "header_row": 4,
        "target": {"column": "C", "expected_header": live_header, "actual_header": actual_header,
                   "period": {"start": start, "end": end}, "currency": "USD", "scale": "1000000"},
        "source_sheet": "Q2 2025 Sources" if cumulative else "FY2025 Sources",
        "forecast_columns": [{"column": col, "expected_header": value} for col, value in zip(("D", "E"), future_headers)],
        "sources": [{"id": "disclosure", "file": source_path.name, "sha256": sha(source_path), "entity": entity, "scope": "consolidated",
                     "currency": "USD", "scale": "1000", "period": {"start": source_start, "end": end}, "audit_status": status,
                     "context_evidence": {"page": 1, "excerpt": context}, "audit_evidence": {"page": 1, "excerpt": audit}}],
        "mappings": [], "excluded_rows": [{"row": 8, "label": "Growth assumption", "reason": "Forward driver assumption; not a reported financial result."}],
    }
    for ident, row, label, prior, estimate, value, printed in records:
        mapping["mappings"].append({"id": ident, "row": row, "label": label, "expected_estimate": str(estimate),
                                    "source_id": "disclosure", "source_label": label, "source_value": value, "reported_as": printed,
                                    "citation": {"page": 2, "excerpt": f"{label} {printed}"}, "kind": "flow",
                                    "basis": "cumulative" if cumulative else "standalone", "sign_multiplier": 1,
                                    "prior_periods": [{"column": "B", "expected_header": prior_header,
                                                       "period": {"start": source_start, "end": "2025-03-31"}, "expected_value": str(prior)}] if cumulative else []})
    (output / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    return mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--case", choices=("annual", "cumulative"), default="annual")
    args = parser.parse_args()
    try:
        make_demo(args.out, args.case)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(f"Synthetic {args.case} inputs: {args.out}")


if __name__ == "__main__":
    main()
