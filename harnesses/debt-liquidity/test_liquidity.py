import itertools
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from liquidity import analyze, markdown, minor_units, reserve_requirement, waterfall
from run import OPERATIONS, TERMS, run


class RetentionTests(unittest.TestCase):
    def test_minimum_cap_against_exhaustive_integer_cash_policies(self):
        # Independent simulation: spend retained cash first. Any negative balance
        # means the cap is insufficient. Search all caps on short cash paths.
        for flows in itertools.product((-3, -1, 0, 2, 4), repeat=4):
            feasible = []
            for cap in range(sum(max(v, 0) for v in flows) + 1):
                cash = 0
                for flow in flows:
                    cash = min(cap, cash + flow)
                    if cash < 0:
                        break
                else:
                    feasible.append(cap)
            opening, minimum_cap = reserve_requirement(flows)
            self.assertEqual(minimum_cap, min(feasible, default=None), flows)
            for initial in {opening, max(0, opening - 1)}:
                running = itertools.accumulate(flows, initial=initial)
                self.assertEqual(min(running) >= 0, initial >= opening, flows)

    def test_sub_minor_unit_is_rejected(self):
        self.assertEqual(minor_units("-0.01", 2), -1)
        with self.assertRaises(ValueError):
            minor_units("0.001", 2)

    def test_opening_deficit_and_later_recovery(self):
        periods = [("first", -2, 3), ("second", 8, 1)]
        self.assertEqual(reserve_requirement([-5, 7]), (5, None))
        retained = waterfall(periods, None, 0)
        self.assertEqual((retained["funding_needed"], retained["closing"]), ("5", "7"))
        swept = waterfall(periods, 0, 0)
        self.assertEqual((swept["funding_needed"], swept["distributions"]), ("5", "7"))

    def test_empty_path_is_excluded(self):
        with self.assertRaises(ValueError):
            reserve_requirement([])

    def test_clean_end_to_end_run_matches_recorded_report(self):
        with TemporaryDirectory() as folder:
            out = Path(folder)
            result = run(out, TERMS, OPERATIONS)
            self.assertEqual(result, Path(__file__).with_name("expected.md").read_text(encoding="utf-8"))
            scenarios = json.loads((out / "calculation/scenario/report.json").read_bytes())
            report = json.loads((out / "liquidity.json").read_bytes())
            self.assertEqual(markdown(analyze(scenarios)), result)
            combined = next(case for case in report["cases"] if case["case"] == "combined")
            self.assertEqual(combined["shortfall_periods"], ["H2_2027", "H1_2028", "H2_2028"])
            limited = combined["policies"]["minimum_cap"]
            self.assertEqual(limited["periods"][0]["closing"], "62708.23")
            self.assertEqual(limited["periods"][-1]["closing"], "0.00")
            self.assertEqual(limited["funding_needed"], "0.00")


if __name__ == "__main__":
    unittest.main()
