import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_regression", ROOT / "scripts" / "regression.py")
regression = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regression)


def snapshot():
    return {"schema_version": 1, "label": "Synthetic baseline", "value_basis": "literal", "items": [
        {"id": "profit", "value": 250, "unit": "USD thousands", "period": "FY2025"},
        {"id": "balance-check", "value": True, "unit": "boolean", "period": "FY2025"},
    ]}


def declaration():
    return {"schema_version": 1, "changes": [{"id": "profit", "reason": "A documented input correction affects profit."}]}


class RegressionTests(unittest.TestCase):
    def test_unchanged_is_pass(self):
        base = snapshot()
        pristine = copy.deepcopy(base)
        report = regression.compare(base, copy.deepcopy(base))
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["counts"]["STABLE"], 2)
        self.assertEqual(base, pristine)

    def test_undeclared_drift_is_failure(self):
        current = snapshot()
        current["items"][0]["value"] = 251
        report = regression.compare(snapshot(), current)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["counts"]["REGRESSION"], 1)

    def test_declared_change_and_silent_change_require_review(self):
        current = snapshot()
        current["items"][0]["value"] = 251
        changed = regression.compare(snapshot(), current, declaration())
        unchanged = regression.compare(snapshot(), snapshot(), declaration())
        self.assertEqual(changed["status"], "REVIEW")
        self.assertEqual(changed["counts"]["EXPECTED_CHANGED"], 1)
        self.assertEqual(unchanged["status"], "REVIEW")
        self.assertEqual(unchanged["counts"]["EXPECTED_UNCHANGED"], 1)

    def test_unlisted_item_does_not_inherit_expected_change(self):
        current = snapshot()
        current["items"][1]["value"] = False
        self.assertEqual(regression.compare(snapshot(), current, declaration())["status"], "FAIL")

    def test_missing_and_added_items_fail(self):
        current = snapshot()
        current["items"].pop()
        report = regression.compare(snapshot(), current)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["counts"]["REMOVED"], 1)
        extra = snapshot()
        extra["items"].append({"id": "new", "value": 1, "unit": "count", "period": "FY2025"})
        self.assertEqual(regression.compare(snapshot(), extra)["status"], "FAIL")

    def test_unit_period_and_type_changes_fail_even_when_declared(self):
        for key, value in [("unit", "EUR thousands"), ("period", "FY2024"), ("value", "250")]:
            current = snapshot()
            current["items"][0][key] = value
            with self.subTest(key=key):
                self.assertEqual(regression.compare(snapshot(), current, declaration())["status"], "FAIL")
        current = snapshot()
        current["items"][1]["value"] = 1
        self.assertEqual(regression.compare(snapshot(), current)["status"], "FAIL")

    def test_null_is_missing_including_two_nulls(self):
        base = snapshot()
        base["items"][0]["value"] = None
        self.assertEqual(regression.compare(base, copy.deepcopy(base))["status"], "INCOMPLETE")
        self.assertEqual(regression.compare(snapshot(), base)["status"], "INCOMPLETE")

    def test_cached_snapshots_never_pass(self):
        current = snapshot()
        current["value_basis"] = "saved_formula_cache"
        self.assertEqual(regression.compare(snapshot(), current)["status"], "REVIEW")

    def test_numeric_tolerance_boundary_and_zero(self):
        tolerances = {"schema_version": 1, "items": [
            {"id": "profit", "absolute": 0, "relative": 0.004, "reason": "Synthetic rounding example"}]}
        current = snapshot()
        current["items"][0]["value"] = 251
        self.assertEqual(regression.compare(snapshot(), current, tolerances=tolerances)["status"], "PASS")
        current["items"][0]["value"] = 251.01
        self.assertEqual(regression.compare(snapshot(), current, tolerances=tolerances)["status"], "FAIL")
        base = snapshot()
        base["items"][0]["value"] = 0
        current["items"][0]["value"] = 0.000001
        self.assertEqual(regression.compare(base, current, tolerances=tolerances)["status"], "FAIL")

    def test_invalid_tolerances_rejected(self):
        for value in [True, -1, float("nan"), float("inf"), "0"]:
            tolerances = {"schema_version": 1, "items": [
                {"id": "profit", "absolute": value, "relative": 0, "reason": "Synthetic test"}]}
            with self.subTest(value=value), self.assertRaises(regression.ContractError):
                regression.compare(snapshot(), snapshot(), tolerances=tolerances)

    def test_empty_duplicate_and_bad_schema_rejected(self):
        variants = []
        empty = snapshot()
        empty["items"] = []
        variants.append(empty)
        duplicate = snapshot()
        duplicate["items"].append(copy.deepcopy(duplicate["items"][0]))
        variants.append(duplicate)
        extra = snapshot()
        extra["secretly-ignore-missing"] = True
        variants.append(extra)
        for value in [float("nan"), float("inf"), [], {}]:
            bad = snapshot()
            bad["items"][0]["value"] = value
            variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(regression.ContractError):
                regression.compare(bad, snapshot())

    def test_invalid_or_unknown_declarations_rejected(self):
        for bad in [{}, {"schema_version": 1, "changes": [{"id": "unknown", "reason": "test"}]},
                    {"schema_version": 1, "changes": [{"id": "profit", "reason": ""}]}]:
            with self.subTest(bad=bad), self.assertRaises(regression.ContractError):
                regression.compare(snapshot(), snapshot(), bad)

    def test_json_duplicate_keys_and_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            for raw in ['{"x": 1, "x": 2}', '{"x": NaN}']:
                path.write_text(raw)
                with self.assertRaises(regression.ContractError):
                    regression.parse_json(path)

    def test_cli_reports_exit_and_preserves_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, current, out = [Path(tmp) / name for name in ("baseline.json", "current.json", "report.json")]
            original = json.dumps(snapshot())
            base.write_text(original)
            changed = snapshot()
            changed["items"][0]["value"] = 300
            current.write_text(json.dumps(changed))
            run = subprocess.run([sys.executable, str(ROOT / "scripts" / "regression.py"), str(base), str(current), "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1, run.stderr)
            self.assertEqual(json.loads(out.read_text())["status"], "FAIL")
            self.assertEqual(base.read_text(), original)
            refused = subprocess.run([sys.executable, str(ROOT / "scripts" / "regression.py"), str(base), str(current), "--out", str(base)], capture_output=True, text=True)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(base.read_text(), original)

    def test_cli_preserves_decimal_literals_and_large_small_differences(self):
        # Use raw JSON numbers: Python float construction would round first.
        for before, after in [("0.1", "0.10000000000000001"),
                              ("1e30", "1000000000000000000000000000000.0000000000000000000000000001"),
                              ("0", "1e-400")]:
            with self.subTest(before=before, after=after), tempfile.TemporaryDirectory() as tmp:
                base, current = Path(tmp) / "baseline.json", Path(tmp) / "current.json"
                data = snapshot()
                data["items"][0]["value"] = "DECIMAL_LITERAL"
                template = json.dumps(data)
                base.write_text(template.replace('"DECIMAL_LITERAL"', before))
                current.write_text(template.replace('"DECIMAL_LITERAL"', after))
                run = subprocess.run([sys.executable, str(ROOT / "scripts" / "regression.py"), str(base), str(current)], capture_output=True, text=True)
                self.assertEqual(run.returncode, 1, run.stderr)
                report = json.loads(run.stdout)
                changed = next(item for item in report["results"] if item["id"] == "profit")
                self.assertEqual(changed["current_value_type"], "number")
                self.assertNotEqual(changed["delta"], "0")

    def test_numeric_resource_bound_is_explicit(self):
        from decimal import Decimal
        baseline = snapshot()
        baseline["items"][0]["value"] = Decimal("1e1001")
        with self.assertRaisesRegex(regression.ContractError, "numeric bound"):
            regression.compare(baseline, snapshot())


if __name__ == "__main__":
    unittest.main()
