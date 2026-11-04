#!/usr/bin/env python3
"""Optional, explicit debt-schedule-to-scenario handoff; not a core dependency."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCENARIO_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scenario_analysis.py"
SPEC = importlib.util.spec_from_file_location("connected_scenario_engine", SCENARIO_SCRIPT)
scenario = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scenario)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def map_debt(template, report, debt_input_hash):
    """Return a new scenario input only after explicit period/unit checks."""
    scenario.validate(template)
    if type(report) is not dict or report.get("model") != "fixed-rate-non-revolving-v1":
        raise scenario.InputError("handoff expects debt-schedule model fixed-rate-non-revolving-v1")
    if report.get("input_sha256") != debt_input_hash:
        raise scenario.InputError("debt report input hash does not match the supplied terms")
    if report.get("currency") != template["currency"] or report.get("unit") != "currency units":
        raise scenario.InputError("handoff currency or amount unit mismatch")
    if type(report.get("money_decimals")) is not int or report["money_decimals"] != template["money_decimals"]:
        raise scenario.InputError("handoff amount precision mismatch")
    if report.get("checks") != {"principal_roll_forward": "PASS", "maturity_balance_zero": "PASS"}:
        raise scenario.InputError("debt report lacks the expected successful reconciliation checks")
    rows = report.get("periods")
    if type(rows) is not list or len(rows) != len(template["periods"]):
        raise scenario.InputError("handoff requires exactly one debt period per scenario period")
    if any(scenario.decimal(value, "placeholder") != 0 for value in template["base_assumptions"]["debt_service"]):
        raise scenario.InputError("template debt_service must contain zero placeholders to avoid replacing existing estimates")
    if any("debt_service" in case["overrides"] for case in template["cases"]):
        raise scenario.InputError("connected demonstration accepts operating stresses only, without debt_service overrides")
    derived = copy.deepcopy(template)
    mapping = []
    for i, (period, row) in enumerate(zip(template["periods"], rows)):
        if type(row) is not dict or any(row.get(key) != period[key] for key in ("start_date", "end_date")):
            raise scenario.InputError(f"handoff period {i + 1}: date boundary mismatch")
        try:
            service = scenario.decimal(row["debt_service"], "debt_service")
            repaid = scenario.decimal(row["repayments"], "repayments")
            interest = scenario.decimal(row["interest_paid"], "interest_paid")
        except KeyError as exc:
            raise scenario.InputError("debt report lacks cash payment fields") from exc
        if min(service, repaid, interest) < 0 or service != repaid + interest:
            raise scenario.InputError("debt service does not reconcile to principal plus cash interest")
        value = scenario.fixed(service, template["money_decimals"])
        if scenario.decimal(value, "mapped value") != service:
            raise scenario.InputError("handoff would lose payment precision")
        derived["base_assumptions"]["debt_service"][i] = value
        mapping.append({"scenario_period": period["id"], "start_date": period["start_date"],
                        "end_date": period["end_date"], "source": f"debt/report.json#/periods/{i}/debt_service",
                        "debt_service": value})
    scenario.validate(derived)
    return derived, mapping


def run(debt_script, debt_terms, template_path, output_path):
    template, template_hash = scenario.read_input(template_path)
    scenario.validate(template)
    debt_script = Path(debt_script).resolve(strict=True)
    debt_terms = Path(debt_terms).resolve(strict=True)
    debt_input_hash = sha256(debt_terms)
    debt_script_hash = sha256(debt_script)
    output = Path(output_path)
    output.mkdir()
    subprocess.run([sys.executable, str(debt_script), str(debt_terms), "--out", str(output / "debt")], check=True)
    report, report_hash = scenario.read_input(output / "debt" / "report.json")
    if sha256(debt_terms) != debt_input_hash or sha256(debt_script) != debt_script_hash:
        raise scenario.InputError("debt script or terms changed during the demonstration")
    derived, mapping = map_debt(template, report, debt_input_hash)
    case_path = output / "scenario-input.json"
    with case_path.open("x", encoding="utf-8") as handle:
        json.dump(derived, handle, indent=2)
        handle.write("\n")
    scenario_result = scenario.run(case_path, output / "scenario")
    handoff = {"schema_version": 1, "mapping_method": "one debt payment period to one identical scenario period",
               "currency": template["currency"], "unit": "currency units", "mapping": mapping,
               "debt_input_sha256": debt_input_hash, "debt_script_sha256": debt_script_hash,
               "debt_report_sha256": report_hash, "scenario_template_sha256": template_hash,
               "derived_scenario_input_sha256": sha256(case_path),
               "scenario_script_sha256": sha256(SCENARIO_SCRIPT),
               "scenario_report_sha256": sha256(output / "scenario" / "report.json")}
    with (output / "handoff.json").open("x", encoding="utf-8") as handle:
        json.dump(handoff, handle, indent=2)
        handle.write("\n")
    lines = ["# Connected synthetic debt and scenario example", "",
             "This optional wrapper executed the supplied debt script, matched every period's date bounds, "
             "currency and units, then replaced explicit zero debt-service placeholders in a synthetic operating case. "
             "It ran the scenario engine on that derived file. Both core tools also run independently.", "",
             "| Period | Start | End | Mapped debt service |", "|---|---|---|---:|"]
    lines.extend(f"| {row['scenario_period']} | {row['start_date']} | {row['end_date']} | {row['debt_service']} |" for row in mapping)
    lines += ["", "| Case | CFADS total | Debt service total | Cash after service | Minimum period DSCR |",
              "|---|---:|---:|---:|---:|"]
    for case in scenario_result["cases"]:
        values = case["summary"]
        lines.append(f"| {case['id']} | {values['cfads']} | {values['debt_service']} | "
                     f"{values['cash_after_debt_service']} | {values['minimum_defined_dscr']} |")
    lines += ["", "Operating stresses leave contractual debt payments unchanged. A rate or amortization change "
              "would require another debt run and a new mapped debt-service array. No covenant threshold is applied.", "",
              "## Evidence hashes", ""]
    lines.extend(f"- {key}: `{value}`" for key, value in handoff.items() if key.endswith("sha256"))
    lines += ["", "See debt/report.md, scenario/report.md and handoff.json for the calculations and exact mapping.", ""]
    with (output / "handoff.md").open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return handoff


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debt-script", required=True, help="explicit path to optional debt-schedule/scripts/debt_schedule.py")
    parser.add_argument("--debt-terms", required=True, help="terms for that debt engine")
    parser.add_argument("--case-template", required=True, help="scenario input with zero debt-service placeholders and matching periods")
    parser.add_argument("--out", required=True, help="new output directory; parent must exist")
    args = parser.parse_args(argv)
    try:
        run(args.debt_script, args.debt_terms, args.case_template, args.out)
    except (scenario.InputError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Connected demonstration written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
