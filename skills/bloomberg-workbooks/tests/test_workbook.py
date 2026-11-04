import copy
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_workbook import build, load, InputError
from openpyxl import load_workbook


class WorkbookTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'examples/config.json').read_text())

    def rejected(self, config):
        with self.assertRaises(InputError):
            build(config)

    def test_matrix_references_exact(self):
        wb, report = build(self.config)
        self.assertEqual(wb['Live']['B2'].value, '=_xll.BDP(Securities!$B2,Fields!$B$2)')
        self.assertEqual(wb['Live']['C3'].value, '=_xll.BDP(Securities!$B3,Fields!$B$3)')
        self.assertEqual(report['provider_formula_count'], 4)

    def test_plain_function_preserved(self):
        self.config['function'] = 'BDP'
        wb, _ = build(self.config)
        self.assertTrue(wb['Live']['B2'].value.startswith('=BDP('))

    def test_no_cached_values(self):
        wb, _ = build(self.config)
        stream = BytesIO(); wb.save(stream)
        saved = load_workbook(BytesIO(stream.getvalue()), data_only=True)
        self.assertIsNone(saved['Live']['B2'].value)
        self.assertIsNone(saved['Live']['C3'].value)
        with zipfile.ZipFile(stream) as archive:
            doc = ET.fromstring(archive.read('xl/worksheets/sheet4.xml'))
            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            self.assertEqual(len(doc.findall('.//s:f', ns)), 6)
            self.assertFalse(any(e.text for e in doc.findall('.//s:v', ns)))

    def test_status_not_promoted(self):
        wb, report = build(self.config)
        self.assertEqual(report['live_refresh'], 'NOT_RUN')
        self.assertFalse(report['snapshot_created'])
        self.assertIsNone(wb['Controls']['B6'].value)
        self.assertIn('SYNTHETIC', wb['Controls']['B3'].value)

    def test_nonfixture_is_still_unverified(self):
        self.config['fixture'] = False
        wb, report = build(self.config)
        self.assertEqual(report['live_refresh'], 'NOT_RUN')
        self.assertIn('require evidence review', wb['Controls']['B3'].value)

    def test_securities_retained_as_literals(self):
        wb, _ = build(self.config)
        self.assertEqual(wb['Securities']['B2'].value, 'SYNTHETIC_A Corp')
        self.assertEqual(wb['Securities']['B2'].data_type, 's')

    def test_reject_formula_security(self):
        self.config['securities'][0]['identifier'] = '=WEBSERVICE("https://example.invalid")'
        self.rejected(self.config)

    def test_reject_formula_title(self):
        self.config['title'] = '+SUM(A1)'; self.rejected(self.config)

    def test_reject_control_characters(self):
        self.config['fields'][0]['evidence'] = 'line\x00'; self.rejected(self.config)

    def test_reject_surrogate(self):
        self.config['title'] = 'bad\ud800'; self.rejected(self.config)

    def test_reject_invalid_function(self):
        self.config['function'] = 'BDH'; self.rejected(self.config)

    def test_reject_missing_keys(self):
        del self.config['fixture']; self.rejected(self.config)

    def test_reject_unknown_keys(self):
        self.config['live_refresh'] = 'PASS'; self.rejected(self.config)

    def test_reject_empty_lists(self):
        for name in ('securities', 'fields'):
            cfg = copy.deepcopy(self.config); cfg[name] = []; self.rejected(cfg)

    def test_reject_duplicate_identifiers(self):
        self.config['securities'].append(copy.deepcopy(self.config['securities'][0])); self.rejected(self.config)

    def test_reject_duplicate_fields(self):
        self.config['fields'].append(copy.deepcopy(self.config['fields'][0])); self.rejected(self.config)

    def test_reject_date_impossible(self):
        self.config['reference_date'] = '2030-02-30'; self.rejected(self.config)

    def test_reject_date_not_iso(self):
        self.config['reference_date'] = '20300630'; self.rejected(self.config)

    def test_reject_false_fixture_string(self):
        self.config['fixture'] = 'false'; self.rejected(self.config)

    def test_reject_mnemonic_escape(self):
        self.config['fields'][0]['mnemonic'] = 'PX_MID")'; self.rejected(self.config)

    def test_no_implicit_percent_conversion(self):
        wb, _ = build(self.config)
        self.assertEqual(wb['Live']['B2'].number_format, 'General')

    def test_all_security_field_combinations(self):
        self.config['fields'].append({'label':'Extra','mnemonic':'SYNTHETIC','unit':'Undefined','evidence':'Synthetic fixture'})
        wb, report = build(self.config)
        self.assertEqual(report['provider_formula_count'], 6)
        self.assertEqual(wb['Live']['D3'].value, '=_xll.BDP(Securities!$B3,Fields!$B$4)')

    def test_bad_json_duplicate_and_nan(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'input.json'
            for blob in ['{"a":1,"a":2}', '{"a":NaN}', '['*1500 + ']'*1500]:
                p.write_text(blob)
                with self.assertRaises(InputError): load(p)

    def test_cli_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'result'
            command = [sys.executable, str(ROOT/'scripts/build_workbook.py'), str(ROOT/'examples/config.json'), str(out)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            before = (out/'workbook.xlsx').read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual((out/'workbook.xlsx').read_bytes(), before)

    def test_cli_invalid_input_no_output(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'bad.json'; p.write_text('{}'); out = Path(temp)/'result'
            run = subprocess.run([sys.executable,str(ROOT/'scripts/build_workbook.py'),str(p),str(out)],capture_output=True,text=True)
            self.assertEqual(run.returncode, 2); self.assertFalse(out.exists()); self.assertNotIn('Traceback',run.stderr)


if __name__ == '__main__': unittest.main()
