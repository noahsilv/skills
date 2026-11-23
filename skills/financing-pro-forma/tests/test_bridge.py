import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.opening = json.loads((ROOT / "examples/opening.json").read_bytes())
        self.proposals = json.loads((ROOT / "examples/transactions.json").read_bytes())

    def test_financing_uses_reconcile_to_separate_closing_statements(self):
        report = bridge.calculate(self.opening, self.proposals)
        refinance, assets = report["cases"]
        for case, total_assets, liabilities in ((refinance, "1318", "670"), (assets, "1418", "770")):
            self.assertEqual(case["closing_balances"]["total_assets"], total_assets)
            self.assertEqual(case["closing_balances"]["total_liabilities"], liabilities)
            self.assertEqual(case["closing_balances"]["total_equity"], "648")
            self.assertEqual(case["closing_balances"]["cash_and_equivalents"], "168")
        self.assertEqual([r["change_in_net_debt"] for r in (refinance, assets)], ["2", "102"])
        self.assertEqual(refinance["closing_metrics"]["lease_liabilities"], "60")
        self.assertEqual(refinance["closing_metrics"]["current_ratio"], "2.877778")

    def test_cases_are_independent_and_order_invariant(self):
        before = copy.deepcopy(self.opening)
        first = bridge.calculate(self.opening, self.proposals)
        self.proposals["cases"].reverse()
        second = bridge.calculate(self.opening, self.proposals)
        self.assertEqual(first["cases"], list(reversed(second["cases"])))
        self.assertEqual(before, self.opening)

    def test_opening_cash_can_fund_a_purchase_without_adding_debt(self):
        flow = self.proposals["cases"][1]["flows"]
        flow.update(draw_noncurrent="0", capital_spending="100", cash_expense="0")
        result = bridge.calculate(self.opening, self.proposals)["cases"][1]
        self.assertEqual(result["closing_metrics"]["gross_debt_including_leases"], "450")
        self.assertEqual(result["closing_balances"]["cash_and_equivalents"], "50")
        self.assertEqual(result["change_in_net_debt"], "100")

    def test_exactly_funded_boundary_and_next_minor_unit(self):
        case = self.proposals["cases"][1]
        case["flows"].update(capital_spending="268", cash_expense="2")
        result = bridge.calculate(self.opening, self.proposals)["cases"][1]
        self.assertEqual(result["status"], "BALANCED")
        self.assertEqual(result["closing_balances"]["cash_and_equivalents"], "0")
        case["flows"]["capital_spending"] = "268.000001"
        result = bridge.calculate(self.opening, self.proposals)["cases"][1]
        self.assertEqual(result["funding_gap"], "0.000001")
        self.assertIsNone(result["closing_balances"])
        self.assertIsNone(result["closing_metrics"])

    def test_equity_contribution_reduces_net_debt(self):
        self.proposals["cases"][1]["flows"]["equity_contribution"] = "110"
        result = bridge.calculate(self.opening, self.proposals)["cases"][1]
        self.assertEqual(result["change_in_net_debt"], "-8")
        self.assertEqual(result["closing_balances"]["total_equity"], "758")

    def test_ratios_handle_nonpositive_denominators(self):
        start = {k: Decimal(v) for k, v in self.opening["balances"].items()}
        start.update(total_equity=Decimal("-5"), current_liabilities=Decimal("0"))
        ratios = bridge.metrics(start)
        self.assertIsNone(ratios["gross_debt_to_equity"])
        self.assertIsNone(ratios["current_ratio"])

    def test_case_basis_must_match_the_opening_position(self):
        for key, value in (("currency", "EUR"), ("scale", "1000"), ("scope", "standalone"),
                           ("as_of", "2026-01-01"), ("entity", "Another synthetic issuer")):
            with self.subTest(key=key):
                inputs = dict(self.proposals, **{key: value})
                with self.assertRaisesRegex(ValueError, "bases differ"):
                    bridge.calculate(self.opening, inputs)

    def test_repayment_cannot_exceed_existing_debt_in_the_class(self):
        self.proposals["cases"][0]["flows"].update(draw_current="50", repay_current="100")
        with self.assertRaisesRegex(ValueError, "exceeds existing current"):
            bridge.calculate(self.opening, self.proposals)

    def test_opening_components_and_balance_reconciliation(self):
        for key, value in (("total_assets", "1299"), ("cash_and_equivalents", "501"),
                           ("debt_current", "226"), ("leases_noncurrent", "111")):
            with self.subTest(key=key):
                inputs = copy.deepcopy(self.opening)
                inputs["balances"][key] = value
                with self.assertRaises(ValueError):
                    bridge.calculate(inputs, self.proposals)

    def test_numeric_contract(self):
        for value in ("NaN", "-1", "", None, 1, True, "1e6", "0.0000001", "9" * 19):
            with self.subTest(value=value):
                self.proposals["cases"][0]["flows"]["draw_current"] = value
                with self.assertRaises(ValueError):
                    bridge.calculate(self.opening, self.proposals)

    def test_schema_and_reference_validation(self):
        for mutate in (
            lambda o, t: t["cases"][0]["flows"].pop("cash_expense"),
            lambda o, t: t["cases"][0]["flows"].update(undisclosed="2"),
            lambda o, t: t["cases"].append(t["cases"][0]),
            lambda o, t: o["source"]["locators"].update(total_equity=""),
            lambda o, t: o["source"].update(sha256="x"),
            lambda o, t: t.update(schema_version=True),
        ):
            opening, proposals = copy.deepcopy(self.opening), copy.deepcopy(self.proposals)
            mutate(opening, proposals)
            with self.assertRaises(ValueError):
                bridge.calculate(opening, proposals)

    def test_statement_adapter_keeps_period_refs_and_rejects_incomplete_reports(self):
        source = self.opening
        period = {"id": "year", "end": source["as_of"], "checks": [{"id": "balance_sheet", "status": "PASS"}],
                  "normalized_values": {k: {"value": value, "sources": [{"source_id": "note", "locator": k}]}
                                        for k, value in source["balances"].items()}}
        report = {"status": "COMPLETE", "entity": {"name": source["entity"], "scope": source["scope"]},
                  "currency": source["currency"], "scale": source["scale"], "periods": [period]}
        converted = bridge.from_statement_report(report, "0" * 64, "year")
        self.assertEqual(converted["balances"], source["balances"])
        self.assertEqual(converted["source"]["locators"]["debt_current"], "note, debt_current")
        for change in ("bad_period", "failed_check", "missing_locator", "duplicate_period", "incomplete"):
            test_report = copy.deepcopy(report)
            test_period = test_report["periods"][0]
            if change == "failed_check":
                test_period["checks"][0]["status"] = "FAIL"
            elif change == "missing_locator":
                test_period["normalized_values"]["debt_current"]["sources"] = []
            elif change == "duplicate_period":
                test_report["periods"].append(test_period)
            elif change == "incomplete":
                test_report["status"] = "INCOMPLETE"
            with self.subTest(change=change), self.assertRaises(ValueError):
                bridge.from_statement_report(test_report, "0" * 64, "missing" if change == "bad_period" else "year")

    def test_cli_matches_recorded_result_and_preserves_existing_destination(self):
        with TemporaryDirectory() as directory:
            out = Path(directory) / "report.json"
            command = [sys.executable, str(ROOT / "scripts/bridge.py"), "bridge", str(ROOT / "examples/opening.json")]
            def run(filename):
                return subprocess.run([*command, str(ROOT / "examples" / filename), "--out", str(out)], capture_output=True)
            self.assertEqual(run("transactions.json").returncode, 0)
            expected = (ROOT / "examples/comparison.json").read_bytes()
            self.assertEqual(out.read_bytes(), expected)
            self.assertEqual(run("unfunded.json").returncode, 2)
            self.assertEqual(out.read_bytes(), expected)
            out = Path(directory) / "gap.json"
            self.assertEqual(run("unfunded.json").returncode, 1)
            gap = json.loads(out.read_bytes())
            self.assertEqual(gap["cases"][0]["funding_gap"], "32")
            self.assertEqual(gap["input_sha256"]["transactions"], hashlib.sha256((ROOT / "examples/unfunded.json").read_bytes()).hexdigest())

    def test_duplicate_json_keys_fail_before_output(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_bytes(b'{"as_of":"first","as_of":"second"}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                bridge.read(path)


if __name__ == "__main__":
    unittest.main()
