import copy
import importlib.util
import json
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("connected_demo", PACKAGE / "examples" / "run_connected_demo.py")
connected = importlib.util.module_from_spec(spec)
spec.loader.exec_module(connected)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads((PACKAGE / "examples" / "connected-operating-case.json").read_text())
        self.report = {"model": "fixed-rate-non-revolving-v1", "input_sha256": "test-hash",
                       "currency": "USD", "unit": "currency units", "money_decimals": 2,
                       "checks": {"principal_roll_forward": "PASS", "maturity_balance_zero": "PASS"},
                       "periods": [{"start_date": p["start_date"], "end_date": p["end_date"],
                                    "debt_service": "105.25", "repayments": "100.00", "interest_paid": "5.25"}
                                   for p in self.template["periods"]]}

    def test_explicit_mapping_preserves_template_and_other_assumptions(self):
        before = copy.deepcopy(self.template)
        derived, mapping = connected.map_debt(self.template, self.report, "test-hash")
        self.assertEqual(self.template, before)
        self.assertEqual(derived["base_assumptions"]["debt_service"], ["105.25"] * 4)
        derived["base_assumptions"]["debt_service"] = before["base_assumptions"]["debt_service"]
        self.assertEqual(derived, before)
        self.assertEqual(mapping[2]["source"], "debt/report.json#/periods/2/debt_service")

    def test_currency_period_precision_and_hash_mismatches_fail(self):
        reports = []
        for key, value in [("currency", "EUR"), ("unit", "millions"), ("money_decimals", 0),
                           ("input_sha256", "wrong"), ("model", "other"), ("periods", [])]:
            report = copy.deepcopy(self.report)
            report[key] = value
            reports.append(report)
        report = copy.deepcopy(self.report)
        report["periods"][0]["end_date"] = "2027-07-02"
        reports.append(report)
        for report in reports:
            with self.subTest(report=report), self.assertRaises(connected.scenario.InputError):
                connected.map_debt(self.template, report, "test-hash")

    def test_payment_reconciliation_and_precision_loss_fail(self):
        for service, interest in [("105.26", "5.25"), ("105.255", "5.255"), ("-1", "-101")]:
            report = copy.deepcopy(self.report)
            report["periods"][0]["debt_service"] = service
            report["periods"][0]["interest_paid"] = interest
            with self.subTest(service=service), self.assertRaises(connected.scenario.InputError):
                connected.map_debt(self.template, report, "test-hash")

    def test_existing_debt_estimate_or_override_is_not_silently_replaced(self):
        self.template["base_assumptions"]["debt_service"][0] = "1"
        with self.assertRaises(connected.scenario.InputError):
            connected.map_debt(self.template, self.report, "test-hash")
        self.template["base_assumptions"]["debt_service"][0] = "0"
        self.template["cases"][1]["overrides"]["debt_service"] = {"operation": "multiply", "values": ["1"] * 4}
        with self.assertRaises(connected.scenario.InputError):
            connected.map_debt(self.template, self.report, "test-hash")


if __name__ == "__main__":
    unittest.main()
