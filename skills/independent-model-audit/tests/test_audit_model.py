import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_model import InputError, audit, load, run
spec = importlib.util.spec_from_file_location('make_examples', ROOT / 'examples/make_examples.py')
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.data = fixtures.clean()

    def finding(self, report, check, period='Y1'):
        return next(x for x in report['checks'] if x['check'] == check and x['period'] == period)

    def test_clean_arithmetic_and_economic_breach(self):
        report = audit(self.data)
        self.assertEqual(report['status'], 'CHECKS_PASSED')
        self.assertEqual(report['counts'], {'PASS': 21})
        self.assertEqual(report['covenant_breach_periods'], ['Y3'])
        self.assertEqual(self.finding(report, 'dscr')['expected'], '5/4')
        self.assertEqual(self.finding(report, 'covenant', 'Y3')['expected'], 'FAIL')
        self.assertFalse(report['model_file_verified'])

    def test_correlated_wrong_outputs_not_adopted(self):
        self.data['observed']['series']['debt_service'][0] = '50'
        self.data['observed']['series']['dscr'][0] = '1'
        report = audit(self.data)
        self.assertEqual(self.finding(report, 'debt_service')['expected'], '40')
        self.assertEqual(self.finding(report, 'dscr')['expected'], '5/4')
        self.assertEqual(self.finding(report, 'dscr')['status'], 'FAIL')

    def test_wrong_opening_cannot_reset_recomputed_carry(self):
        self.data['observed']['series']['closing_debt'][0] = '75'
        self.data['observed']['series']['opening_debt'][1] = '75'
        report = audit(self.data)
        self.assertEqual(self.finding(report, 'reported_continuity', 'Y2')['status'], 'PASS')
        self.assertEqual(self.finding(report, 'opening_debt', 'Y2')['status'], 'FAIL')
        self.assertEqual(self.finding(report, 'closing_debt', 'Y2')['expected'], '40')

    def test_planted_errors_have_exact_findings(self):
        report = audit(fixtures.cases()['planted-errors'])
        failures = {(x['period'], x['check']) for x in report['checks'] if x['status'] == 'FAIL'}
        self.assertEqual(failures, {('Y1', 'closing_debt'), ('Y1', 'debt_service'), ('Y1', 'dscr'),
                                    ('Y2', 'opening_debt'), ('Y3', 'covenant')})

    def test_missing_cfads_not_zero(self):
        report = audit(fixtures.cases()['missing-data'])
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertEqual(report['counts']['UNVERIFIED'], 2)
        self.assertIsNone(self.finding(report, 'dscr', 'Y2')['expected'])

    def test_missing_draw_propagates_carry_not_service(self):
        self.data['inputs']['series']['drawdown'][0] = None
        report = audit(self.data)
        self.assertEqual(self.finding(report, 'opening_debt', 'Y2')['status'], 'UNVERIFIED')
        self.assertEqual(self.finding(report, 'debt_service', 'Y2')['status'], 'PASS')
        self.assertEqual(self.finding(report, 'final_principal', 'Y3')['status'], 'UNVERIFIED')

    def test_missing_observed_number_stays_unverified(self):
        self.data['observed']['series']['debt_service'][0] = None
        report = audit(self.data)
        self.assertEqual(self.finding(report, 'debt_service')['status'], 'UNVERIFIED')
        self.assertEqual(self.finding(report, 'dscr')['status'], 'PASS')

    def test_zero_service_is_not_ratio_zero(self):
        for m in ('repayment', 'interest'):
            self.data['inputs']['series'][m][0] = '0'
        self.data['observed']['series']['dscr'][0] = None
        self.data['observed']['series']['covenant'][0] = 'UNDEFINED'
        report = audit(self.data)
        self.assertEqual(self.finding(report, 'dscr')['status'], 'NOT_APPLICABLE')
        self.assertEqual(self.finding(report, 'covenant')['status'], 'NOT_APPLICABLE')
        self.data['observed']['series']['dscr'][0] = '0'
        self.assertEqual(self.finding(audit(self.data), 'dscr')['status'], 'FAIL')

    def test_zero_service_and_missing_cfads_unverified(self):
        for m in ('repayment', 'interest'):
            self.data['inputs']['series'][m][0] = '0'
        self.data['inputs']['series']['cfads'][0] = None
        self.assertEqual(self.finding(audit(self.data), 'dscr')['status'], 'UNVERIFIED')

    def test_missing_threshold_is_unverified(self):
        self.data['covenant']['threshold'] = None
        report = audit(self.data)
        self.assertEqual(report['counts']['UNVERIFIED'], 3)
        self.assertEqual(report['covenant_breach_periods'], [])

    def test_reversed_covenant_operator(self):
        self.data['covenant']['operator'] = 'lte'
        self.data['observed']['series']['covenant'] = ['FAIL', 'PASS', 'PASS']
        self.assertEqual(audit(self.data)['status'], 'CHECKS_PASSED')

    def test_covenant_uses_exact_ratio_not_rounded_cached_value(self):
        self.data['inputs']['series']['cfads'][1] = '44.3999999'
        self.data['ratio_tolerance'] = '0.001'
        report = audit(self.data)
        self.assertEqual(self.finding(report, 'dscr', 'Y2')['status'], 'PASS')
        self.assertEqual(self.finding(report, 'covenant', 'Y2')['status'], 'FAIL')

    def test_negative_cfads_permitted_and_breach_detected(self):
        self.data['inputs']['series']['cfads'][0] = '-10'
        report = audit(self.data)
        self.assertEqual(self.finding(report, 'dscr')['expected'], '-1/4')
        self.assertEqual(self.finding(report, 'covenant')['expected'], 'FAIL')

    def test_excess_repayment_is_finding(self):
        self.data['inputs']['series']['repayment'][0] = '101'
        report = audit(self.data)
        self.assertEqual(self.finding(report, 'principal_nonnegative')['status'], 'FAIL')

    def test_no_final_target_is_disclosed(self):
        self.data['required_final_debt'] = None
        report = audit(self.data)
        self.assertFalse(report['final_principal_checked'])
        self.assertFalse(any(x['check'] == 'final_principal' for x in report['checks']))

    def test_tolerance_is_absolute_and_inclusive(self):
        self.data['observed']['series']['debt_service'][0] = '40.000001'
        self.assertEqual(self.finding(audit(self.data), 'debt_service')['status'], 'PASS')
        self.data['observed']['series']['debt_service'][0] = '40.000001000001'
        self.assertEqual(self.finding(audit(self.data), 'debt_service')['status'], 'FAIL')

    def test_decimal_precision_without_float_conversion(self):
        self.data['initial_debt'] = '999999999999999999999999'
        report = audit(self.data)
        self.assertEqual(self.finding(report, 'closing_debt')['expected'], '999999999999999999999969')

    def test_period_alignment_rejected_before_calculation(self):
        self.data['observed']['period_ids'] = ['Y2', 'Y1', 'Y3']
        with self.assertRaises(InputError): audit(self.data)

    def test_unit_and_currency_alignment(self):
        for field, value in [('amount_unit', 'units'), ('currency', 'EUR')]:
            with self.subTest(field=field):
                data = copy.deepcopy(self.data);data['observed'][field] = value
                with self.assertRaises(InputError): audit(data)

    def test_period_gap_overlap_and_duplicate_rejected(self):
        for field, value in [('start', '2031-01-02'), ('start', '2030-12-31'), ('id', 'Y1')]:
            data = copy.deepcopy(self.data);data['periods'][1][field] = value
            with self.assertRaises(InputError): audit(data)

    def test_strict_numeric_contract(self):
        for value in [1, 1.2, True, 'NaN', 'Infinity', '1e2', '01', '1' * 25, '0.0000000000001', [], {}]:
            with self.subTest(value=value):
                data = copy.deepcopy(self.data);data['inputs']['series']['interest'][0] = value
                with self.assertRaises(InputError): audit(data)

    def test_negative_cash_interest_rejected(self):
        self.data['inputs']['series']['interest'][0] = '-1'
        with self.assertRaises(InputError): audit(self.data)

    def test_unknown_keys_lengths_and_unmapped_values_rejected(self):
        variants = []
        d = copy.deepcopy(self.data);d['extra'] = 1;variants.append(d)
        d = copy.deepcopy(self.data);d['inputs']['series']['drawdown'].pop();variants.append(d)
        d = copy.deepcopy(self.data);d['inputs']['references']['cfads'][0] = '';variants.append(d)
        d = copy.deepcopy(self.data);d['observed']['series']['covenant'][0] = 'OK';variants.append(d)
        for data in variants:
            with self.assertRaises(InputError): audit(data)

    def test_duplicate_nonfinite_and_overlarge_json_rejected(self):
        for raw in [b'{"x":1,"x":2}', b'{"x":NaN}', b' ' * 2_000_001, b'\xff', b'[' * 1500 + b']' * 1500]:
            with self.assertRaises(InputError): load(raw)

    def test_input_not_mutated_and_artifacts_bound(self):
        before = copy.deepcopy(self.data);audit(self.data);self.assertEqual(before, self.data)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.json';raw = json.dumps(self.data).encode();path.write_bytes(raw)
            out = Path(folder)/'out';report = run(path, out)
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(json.loads((out/'report.json').read_text())['snapshot_sha256'], report['snapshot_sha256'])
            self.assertIn('Y3', (out/'report.md').read_text())
            with self.assertRaises(FileExistsError): run(path, out)

    def test_cli_exit_codes_and_no_report_on_bad_input(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for name, data, code in [('clean', fixtures.clean(), 0), ('bad', fixtures.cases()['planted-errors'], 1),
                                     ('missing', fixtures.cases()['missing-data'], 1), ('invalid', {}, 2)]:
                source = folder/(name+'.json');source.write_text(json.dumps(data))
                output = folder/name
                result = subprocess.run([sys.executable, str(ROOT/'scripts/audit_model.py'), str(source), '--out', str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(output.exists(), code != 2)


if __name__ == '__main__':
    unittest.main()
