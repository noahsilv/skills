import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "debt_schedule.py"
spec = importlib.util.spec_from_file_location("debt_schedule", SCRIPT)
debt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(debt)


def facility():
    return {"schema_version": 1, "facility_id": "Synthetic_A", "currency": "USD",
            "money_decimals": 2, "start_date": "2027-01-01", "maturity_date": "2028-01-01",
            "commitment": "1000.00", "opening_balance": "0.00", "prior_drawdowns": "0.00", "annual_rate": "0.10",
            "day_count": "ACT/365F", "payment_dates": ["2028-01-01"],
            "events": [{"date": "2027-01-01", "type": "drawdown", "amount": "1000.00"},
                       {"date": "2028-01-01", "type": "repayment", "amount": "1000.00"}]}


class DebtArithmeticTests(unittest.TestCase):
    def test_full_year_bullet_and_immutable_input(self):
        source = facility()
        snapshot = copy.deepcopy(source)
        result = debt.calculate(source)
        self.assertEqual(source, snapshot)
        row = result["periods"][0]
        self.assertEqual(row["interest_paid"], "100.00")
        self.assertEqual(row["debt_service"], "1100.00")
        self.assertEqual(row["closing_balance"], "0.00")
        self.assertEqual(result["unused_commitment"], "0.00")

    def test_partial_period_repayment_uses_actual_daily_principal(self):
        source = facility()
        source["events"] = [source["events"][0],
                            {"date": "2027-04-01", "type": "repayment", "amount": "400.00"},
                            {"date": "2028-01-01", "type": "repayment", "amount": "600.00"}]
        result = debt.calculate(source)
        # Independent hand calculation: 90 days at 1000; 275 days at 600.
        expected = Fraction(1000 * 90 + 600 * 275, 3650)
        self.assertEqual(Fraction(result["periods"][0]["interest_exact"]), expected)
        self.assertEqual(result["periods"][0]["interest_paid"], "69.86")
        self.assertEqual([r["days"] for r in result["accrual_segments"]], [90, 275])

    def test_payment_boundary_event_belongs_to_ending_period(self):
        source = facility()
        source["payment_dates"] = ["2027-07-01", "2028-01-01"]
        source["events"] = [source["events"][0],
                            {"date": "2027-07-01", "type": "repayment", "amount": "250.00"},
                            {"date": "2028-01-01", "type": "repayment", "amount": "750.00"}]
        first, second = debt.calculate(source)["periods"]
        self.assertEqual(first["repayments"], "250.00")
        self.assertEqual(first["closing_balance"], second["opening_balance"])
        self.assertEqual(Fraction(first["interest_exact"]), Fraction(18100, 365))
        self.assertEqual(Fraction(second["interest_exact"]), Fraction(13800, 365))

    def test_leap_year_fixed_denominator(self):
        source = facility()
        source.update(start_date="2028-01-01", maturity_date="2029-01-01",
                      payment_dates=["2029-01-01"], opening_balance="1000.00", prior_drawdowns="1000.00")
        source["events"] = [{"date": "2029-01-01", "type": "repayment", "amount": "1000.00"}]
        result = debt.calculate(source)
        self.assertEqual(result["periods"][0]["days"], 366)
        self.assertEqual(result["totals"]["interest_paid"], "100.27")
        source["day_count"] = "ACT/360"
        self.assertEqual(debt.calculate(source)["totals"]["interest_paid"], "101.67")

    def test_round_once_per_period_not_per_segment(self):
        source = facility()
        source.update(start_date="2027-01-01", maturity_date="2027-01-04",
                      payment_dates=["2027-01-04"], annual_rate="0.00365", commitment="1000.00")
        source["events"] = [{"date": "2027-01-01", "type": "drawdown", "amount": "100.00"},
                            {"date": "2027-01-02", "type": "drawdown", "amount": "100.00"},
                            {"date": "2027-01-03", "type": "drawdown", "amount": "100.00"},
                            {"date": "2027-01-04", "type": "repayment", "amount": "300.00"}]
        result = debt.calculate(source)
        self.assertEqual(result["periods"][0]["interest_exact"], "3/500")
        self.assertEqual(result["totals"]["interest_paid"], "0.01")

    def test_same_day_draw_precedes_repayment_independent_of_input_order(self):
        source = facility()
        source["events"] = [{"date": "2027-01-01", "type": "repayment", "amount": "400.00"},
                            {"date": "2027-01-01", "type": "drawdown", "amount": "1000.00"},
                            {"date": "2028-01-01", "type": "repayment", "amount": "600.00"}]
        self.assertEqual(debt.calculate(source)["totals"]["interest_paid"], "60.00")

    def test_zero_interest_and_unused_commitment(self):
        source = facility()
        source.update(annual_rate="0", commitment="1500.00")
        result = debt.calculate(source)
        self.assertEqual(result["unused_commitment"], "500.00")
        self.assertEqual(result["totals"]["interest_paid"], "0.00")
        self.assertEqual(result["totals"]["debt_service"], "1000.00")

    def test_half_up_exact_rounding(self):
        self.assertEqual(debt.fixed(Fraction(1005, 1000), 2), "1.01")
        self.assertEqual(debt.fixed(Fraction(-1005, 1000), 2), "-1.01")
        self.assertEqual(debt.fixed(Fraction(999999999999999999999999, 1), 2), "999999999999999999999999.00")


class DebtValidationTests(unittest.TestCase):
    def test_numeric_types_null_nonfinite_and_precision_are_rejected(self):
        for invalid in [True, False, None, 0.1, 1, "NaN", "Infinity", "1e3", "-1", "01", "1.001"]:
            with self.subTest(invalid=invalid):
                source = facility()
                source["commitment"] = invalid
                with self.assertRaises(debt.InputError):
                    debt.calculate(source)

    def test_unknown_missing_fields_and_bool_integer(self):
        for update in [{"schema_version": True}, {"money_decimals": False}, {"unexpected": 1},
                       {"currency": "usd"}, {"facility_id": "=CMD"}, {"day_count": "30/360"}]:
            source = facility()
            source.update(update)
            with self.subTest(update=update), self.assertRaises(debt.InputError):
                debt.calculate(source)
        source = facility()
        del source["opening_balance"]
        with self.assertRaises(debt.InputError):
            debt.calculate(source)

    def test_invalid_dates_and_periods(self):
        for values in [["2028-02-30"], [], ["2028-01-01", "2028-01-01"],
                       ["2027-07-01"], ["2027-01-01", "2028-01-01"],
                       ["2028-01-01", "2027-07-01"]]:
            source = facility()
            source["payment_dates"] = values
            with self.subTest(values=values), self.assertRaises(debt.InputError):
                debt.calculate(source)

    def test_overrepayment_and_residual_maturity(self):
        for amount in ["1000.01", "999.99"]:
            source = facility()
            source["events"][-1]["amount"] = amount
            with self.subTest(amount=amount), self.assertRaises(debt.InputError):
                debt.calculate(source)

    def test_repaid_commitment_does_not_revolve(self):
        source = facility()
        source["events"] = [source["events"][0],
                            {"date": "2027-03-01", "type": "repayment", "amount": "500.00"},
                            {"date": "2027-04-01", "type": "drawdown", "amount": "500.00"},
                            source["events"][-1]]
        with self.assertRaisesRegex(debt.InputError, "non-revolving"):
            debt.calculate(source)

    def test_prior_repayments_do_not_restore_commitment(self):
        source = facility()
        source.update(opening_balance="500.00", prior_drawdowns="1000.00")
        source["events"] = [{"date": "2028-01-01", "type": "repayment", "amount": "500.00"}]
        result = debt.calculate(source)
        self.assertEqual(result["unused_commitment"], "0.00")
        self.assertEqual(result["totals"]["interest_paid"], "50.00")
        source["events"].insert(0, {"date": "2027-01-01", "type": "drawdown", "amount": "1.00"})
        with self.assertRaisesRegex(debt.InputError, "non-revolving"):
            debt.calculate(source)

    def test_historical_draws_must_cover_opening_principal_and_fit_commitment(self):
        for opening, prior in [("500", "400"), ("500", "1001")]:
            source = facility()
            source.update(opening_balance=opening, prior_drawdowns=prior)
            with self.subTest(opening=opening, prior=prior), self.assertRaises(debt.InputError):
                debt.calculate(source)

    def test_invalid_event_fields_dates_and_duplicates(self):
        invalid_events = [{"date": "2026-12-31", "type": "drawdown", "amount": "1"},
                          {"date": "2028-01-01", "type": "drawdown", "amount": "1"},
                          {"date": "2027-02-01", "type": "fee", "amount": "1"},
                          {"date": "2027-01-01", "type": "drawdown", "amount": "1"},
                          {"date": "2027-02-01", "type": "drawdown", "amount": "0"}]
        for event in invalid_events:
            source = facility()
            source["events"].append(event)
            with self.subTest(event=event), self.assertRaises(debt.InputError):
                debt.calculate(source)

    def test_strict_json_duplicate_keys_and_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for contents in ['{"schema_version":1,"schema_version":1}', '{"a":NaN}',
                             '{"a":Infinity}', '{"event":{"amount":"1","amount":"2"}}', 'null',
                             '{"a":1e9999}', '{"a":' + '9' * 5000 + '}']:
                path.write_text(contents)
                with self.subTest(contents=contents), self.assertRaises(debt.InputError):
                    source, _ = debt.read_input(path)
                    debt.calculate(source)


class DebtCLITests(unittest.TestCase):
    def test_cli_outputs_trace_input_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "terms.json"
            source.write_text(json.dumps(facility()))
            original = source.read_bytes()
            output = Path(tmp) / "result"
            command = [sys.executable, str(SCRIPT), str(source), "--out", str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(source.read_bytes(), original)
            expected_files = {"report.md", "report.json", "schedule.csv", "accruals.csv"}
            self.assertEqual({p.name for p in output.iterdir()}, expected_files)
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["input_sha256"], debt.hashlib.sha256(original).hexdigest())

    def test_invalid_input_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "terms.json"
            source.write_text('{"schema_version":true}')
            output = Path(tmp) / "result"
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), "--out", str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
