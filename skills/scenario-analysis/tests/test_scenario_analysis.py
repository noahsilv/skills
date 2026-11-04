import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scenario_analysis.py"
spec = importlib.util.spec_from_file_location("scenario_analysis", SCRIPT)
scenario = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenario)


def analysis():
    return {"schema_version": 1, "analysis_id": "Synthetic_Cases", "currency": "USD", "money_decimals": 2,
            "periods": [{"id": "Y1", "start_date": "2027-01-01", "end_date": "2028-01-01"},
                        {"id": "Y2", "start_date": "2028-01-01", "end_date": "2029-01-01"}],
            "base_assumptions": {"volume": ["100", "120"], "unit_price": ["10", "10"],
                                 "unit_variable_cost": ["4", "4"], "fixed_cost": ["100", "120"],
                                 "cash_taxes": ["50", "60"], "maintenance_capex": ["20", "20"],
                                 "working_capital_increase": ["30", "0"], "debt_service": ["200", "250"]},
            "cases": [{"id": "base", "overrides": {}},
                      {"id": "volume_down", "overrides": {"volume": {"operation": "multiply", "values": ["0.8", "0.8"]}}},
                      {"id": "cost_up", "overrides": {"fixed_cost": {"operation": "add", "values": ["25", "25"]}}},
                      {"id": "combined", "overrides": {
                          "volume": {"operation": "multiply", "values": ["0.8", "0.8"]},
                          "fixed_cost": {"operation": "add", "values": ["25", "25"]}}}],
            "sensitivities": [{"id": "volume_axis", "assumption": "volume", "operation": "multiply", "values": ["0.8", "1", "1.2"]}]}


class ScenarioArithmeticTests(unittest.TestCase):
    def test_hand_calculated_base_cash_bridge(self):
        result = scenario.calculate(analysis())
        base = result["cases"][0]
        # Y1: 100*10 - 100*4 - 100 = 500; CFADS 500 - 50 - 20 - 30 = 400.
        self.assertEqual(base["periods"][0]["ebitda"], "500.00")
        self.assertEqual(base["periods"][0]["cfads"], "400.00")
        self.assertEqual(base["periods"][0]["dscr"], "2.000000")
        # Y2 CFADS: 120*6 - 120 - 60 - 20 = 520.
        self.assertEqual(base["summary"]["cfads"], "920.00")
        self.assertEqual(base["summary"]["cash_after_debt_service"], "470.00")
        self.assertEqual(base["summary"]["minimum_defined_dscr"], "2.000000")
        self.assertEqual(base["exact_summary"]["cfads"], "920/1")

    def test_volume_changes_variable_cost_as_well_as_revenue(self):
        case = scenario.calculate(analysis())["cases"][1]
        self.assertEqual(case["periods"][0]["revenue"], "800.00")
        self.assertEqual(case["periods"][0]["variable_cost"], "320.00")
        self.assertEqual(case["periods"][0]["cfads"], "280.00")
        self.assertEqual(case["summary"]["cash_after_debt_service"], "206.00")
        self.assertEqual(case["delta_from_base"]["delta_cash_after_debt_service"], "-264.00")

    def test_every_case_starts_from_base_and_source_is_immutable(self):
        source = analysis()
        snapshot = copy.deepcopy(source)
        result = scenario.calculate(source)
        self.assertEqual(source, snapshot)
        self.assertEqual(result["cases"][2]["summary"]["cash_after_debt_service"], "420.00")
        reordered = copy.deepcopy(source)
        reordered["cases"][1:] = reversed(reordered["cases"][1:])
        compare = scenario.calculate(reordered)
        self.assertEqual({c["id"]: c for c in result["cases"]}, {c["id"]: c for c in compare["cases"]})
        self.assertEqual(result["base_assumptions_sha256"], compare["base_assumptions_sha256"])

    def test_combined_case_lever_isolation(self):
        cases = scenario.calculate(analysis())["cases"]
        volume = Fraction(cases[1]["exact_summary"]["cash_after_debt_service"])
        combined = Fraction(cases[3]["exact_summary"]["cash_after_debt_service"])
        # The pair differs only in fixed_cost: +25 in each of two periods.
        self.assertEqual(combined - volume, -50)
        self.assertEqual(cases[3]["periods"][0]["revenue"], cases[1]["periods"][0]["revenue"])

    def test_sensitivity_identity_and_single_lever_results(self):
        result = scenario.calculate(analysis())
        rows = result["sensitivities"]
        self.assertEqual(rows[1]["delta_cash_after_debt_service"], "0.00")
        self.assertEqual(rows[0]["exact_summary"], result["cases"][1]["exact_summary"])
        self.assertEqual(rows[2]["delta_cash_after_debt_service"], "264.00")
        self.assertEqual([r["cash_after_debt_service"] for r in rows], ["206.00", "470.00", "734.00"])

    def test_replace_add_and_multiply_semantics_are_distinct(self):
        source = analysis()
        source["cases"] = [source["cases"][0],
                           {"id": "replace_cost", "overrides": {"fixed_cost": {"operation": "replace", "values": ["25", "25"]}}},
                           {"id": "add_cost", "overrides": {"fixed_cost": {"operation": "add", "values": ["25", "25"]}}},
                           {"id": "multiply_cost", "overrides": {"fixed_cost": {"operation": "multiply", "values": ["0.25", "0.25"]}}}]
        cases = scenario.calculate(source)["cases"]
        self.assertEqual([c["applied_assumptions"]["fixed_cost"] for c in cases[1:]],
                         [["25/1", "25/1"], ["125/1", "145/1"], ["25/1", "30/1"]])

    def test_zero_service_is_explicitly_undefined(self):
        source = analysis()
        source["base_assumptions"]["debt_service"] = ["0", "250"]
        base = scenario.calculate(source)["cases"][0]
        self.assertIsNone(base["periods"][0]["dscr"])
        self.assertEqual(base["periods"][0]["dscr_status"], "ZERO_DEBT_SERVICE")
        self.assertEqual(base["summary"]["periods_with_dscr"], 1)
        self.assertEqual(base["summary"]["minimum_defined_dscr"], "2.080000")
        source["base_assumptions"]["debt_service"] = ["0", "0"]
        self.assertIsNone(scenario.calculate(source)["cases"][0]["summary"]["minimum_defined_dscr"])

    def test_working_capital_release_and_negative_cash_are_retained(self):
        source = analysis()
        source["base_assumptions"]["working_capital_increase"] = ["-30", "1000"]
        base = scenario.calculate(source)["cases"][0]
        self.assertEqual(base["periods"][0]["cfads"], "460.00")
        self.assertEqual(base["periods"][1]["cfads"], "-480.00")
        self.assertEqual(base["periods"][1]["dscr"], "-1.920000")

    def test_noop_and_unaffected_output_flags(self):
        source = analysis()
        source["cases"].append({"id": "identity", "overrides": {"volume": {"operation": "multiply", "values": ["1", "1"]}}})
        self.assertEqual(scenario.calculate(source)["cases"][-1]["status"], "NO_ASSUMPTION_CHANGE")
        source["base_assumptions"]["volume"] = ["0", "0"]
        source["cases"].append({"id": "price_without_sales", "overrides": {"unit_price": {"operation": "add", "values": ["1", "1"]}}})
        self.assertEqual(scenario.calculate(source)["cases"][-1]["status"], "ASSUMPTIONS_CHANGED_OUTPUT_UNCHANGED")

    def test_exact_math_and_aggregate_before_rounding(self):
        source = analysis()
        source["base_assumptions"]["volume"] = ["0.1", "0.1"]
        source["base_assumptions"]["unit_price"] = ["0.05", "0.05"]
        base = scenario.calculate(source)["cases"][0]
        self.assertEqual(base["periods"][0]["revenue"], "0.01")
        self.assertEqual(base["summary"]["revenue"], "0.01")
        self.assertEqual(base["exact_summary"]["revenue"], "1/100")

    def test_assumption_changes_record_correct_period_and_exact_delta(self):
        result = scenario.calculate(analysis())
        volume = [r for r in result["assumption_change_rows"] if r["case_id"] == "volume_down"]
        self.assertEqual([r["period_id"] for r in volume], ["Y1", "Y2"])
        self.assertEqual([r["change"] for r in volume], ["-20/1", "-24/1"])
        self.assertEqual([r["operation"] for r in volume], ["multiply", "multiply"])


class ScenarioValidationTests(unittest.TestCase):
    def assert_invalid(self, source):
        with self.assertRaises(scenario.InputError):
            scenario.calculate(source)

    def test_unknown_assumptions_and_override_fields(self):
        source = analysis()
        source["cases"][1]["overrides"]["rate"] = {"operation": "add", "values": ["0.02", "0.02"]}
        self.assert_invalid(source)
        source = analysis()
        source["cases"][1]["overrides"]["volume"]["typo"] = 1
        self.assert_invalid(source)

    def test_bool_null_number_nonfinite_and_exponents_rejected(self):
        for value in [True, False, None, 1, 0.1, "NaN", "Infinity", "1e2", "01", " 1", "+1"]:
            source = analysis()
            source["base_assumptions"]["volume"][0] = value
            with self.subTest(value=value):
                self.assert_invalid(source)

    def test_base_must_be_first_and_unmodified(self):
        source = analysis()
        source["cases"][0]["overrides"] = {"volume": {"operation": "add", "values": ["1", "1"]}}
        self.assert_invalid(source)
        source = analysis()
        source["cases"].reverse()
        self.assert_invalid(source)

    def test_unique_case_period_and_axis_ids(self):
        for target in ["cases", "periods", "sensitivities"]:
            source = analysis()
            source[target].append(copy.deepcopy(source[target][0]))
            with self.subTest(target=target):
                self.assert_invalid(source)

    def test_lengths_and_invalid_effective_values(self):
        source = analysis()
        source["base_assumptions"]["volume"] = ["100"]
        self.assert_invalid(source)
        source = analysis()
        source["cases"][1]["overrides"]["volume"]["values"] = ["1"]
        self.assert_invalid(source)
        source = analysis()
        source["cases"][2]["overrides"]["fixed_cost"]["values"] = ["-1000", "-1000"]
        self.assert_invalid(source)
        source = analysis()
        source["sensitivities"][0]["values"] = ["-1"]
        self.assert_invalid(source)

    def test_noncontiguous_and_invalid_dates(self):
        for start in ["2028-01-02", "2027-12-31", "2028-02-30", "2028-1-1", None]:
            source = analysis()
            source["periods"][1]["start_date"] = start
            with self.subTest(start=start):
                self.assert_invalid(source)

    def test_unknown_fields_type_confusion_and_unsafe_ids(self):
        for field, value in [("schema_version", True), ("money_decimals", False), ("unexpected", "x"),
                             ("analysis_id", "=SUM(A1)"), ("cases", {}), ("sensitivities", None)]:
            source = analysis()
            source[field] = value
            with self.subTest(field=field):
                self.assert_invalid(source)

    def test_sensitivity_duplicate_numeric_levels_and_unknown_operation(self):
        source = analysis()
        source["sensitivities"][0]["values"] = ["1", "1.00"]
        self.assert_invalid(source)
        source = analysis()
        source["sensitivities"][0]["operation"] = "percent"
        self.assert_invalid(source)

    def test_strict_json_duplicate_keys_and_constants(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for contents in ['{"cases":[],"cases":[]}', '{"x":NaN}', '{"x":Infinity}',
                             '{"x":{"values":[],"values":[]}}', 'null', '{"x":1e9999}',
                             '{"x":' + '9' * 5000 + '}']:
                path.write_text(contents)
                with self.subTest(contents=contents), self.assertRaises(scenario.InputError):
                    source, _ = scenario.read_input(path)
                    scenario.calculate(source)


class ScenarioCLITests(unittest.TestCase):
    def test_outputs_input_preservation_and_refused_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.json"
            source.write_text(json.dumps(analysis()))
            original = source.read_bytes()
            output = Path(tmp) / "result"
            cmd = [sys.executable, str(SCRIPT), str(source), "--out", str(output)]
            first = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual({p.name for p in output.iterdir()},
                             {"report.md", "report.json", "cases.csv", "period_results.csv", "assumption_changes.csv", "sensitivities.csv"})
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})
            result = json.loads((output / "report.json").read_text())
            self.assertEqual(result["input_sha256"], scenario.hashlib.sha256(original).hexdigest())

    def test_invalid_case_prevents_any_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.json"
            invalid = analysis()
            invalid["cases"][-1]["overrides"]["volume"]["values"] = ["-1", "-1"]
            source.write_text(json.dumps(invalid))
            output = Path(tmp) / "result"
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), "--out", str(output)], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_empty_sensitivities_and_base_only_produce_header_csvs(self):
        source = analysis()
        source["cases"] = source["cases"][:1]
        source["sensitivities"] = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            path.write_text(json.dumps(source))
            output = Path(tmp) / "result"
            scenario.run(path, output)
            self.assertEqual(len((output / "assumption_changes.csv").read_text().splitlines()), 1)
            self.assertEqual(len((output / "sensitivities.csv").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
