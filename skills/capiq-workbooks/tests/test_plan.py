import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_plan import build, cell, area, load, InputError


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT/'examples/config.json').read_text())

    def rejected(self):
        with self.assertRaises(InputError): build(self.cfg)

    def test_exact_formula_preservation(self):
        result = build(self.cfg)
        self.assertEqual(result['cells'][0]['value'], self.cfg['queries'][0]['formula'])
        self.assertIn(',,', result['cells'][0]['value'])

    def test_supported_families_preserved(self):
        for name in ['SPG','SPGRANGEV','SPGTable','SPGScreen','CIQ','CIQRANGE','CIQRANGEV']:
            for prefix in ['', '_xll.', '_xll.SNL.Clients.Office.Excel.Functions.']:
                self.cfg['queries'][0]['formula'] = f'=@{prefix}{name}(A2,"SYNTHETIC")'
                self.assertEqual(build(self.cfg)['cells'][0]['value'], self.cfg['queries'][0]['formula'])

    def test_live_status_never_promoted(self):
        self.cfg['fixture'] = False; self.cfg['queries'][0]['syntax_status'] = 'observed_control'
        result = build(self.cfg)
        self.assertEqual(result['live_refresh'],'NOT_RUN')
        self.assertEqual(result['status'],'FORMULA_PLAN_ONLY')

    def test_link_not_hardcoded(self):
        result = build(self.cfg)
        self.assertEqual(result['cells'][-1]['value'], "='Raw Data'!B2")
        self.assertEqual(result['cells'][-1]['role'], 'presentation_link')

    def test_quoted_sheet_escaped(self):
        self.cfg['queries'][0]['sheet'] = "Issuer's Data"
        self.assertEqual(build(self.cfg)['cells'][-1]['value'], "='Issuer''s Data'!B2")

    def test_single_quoted_sheet_parentheses(self):
        self.cfg['queries'][0]['formula'] = "=SPG('Input ) sheet'!A1,\"FIELD\")"
        self.assertEqual(build(self.cfg)['cells'][0]['value'], self.cfg['queries'][0]['formula'])

    def test_single_quoted_sheet_apostrophe(self):
        self.cfg['queries'][0]['formula'] = "=SPG('Issuer''s (data'!A1,\"FIELD\")"
        self.assertEqual(build(self.cfg)['cells'][0]['value'], self.cfg['queries'][0]['formula'])

    def test_interior_anchor_rejected(self):
        self.cfg['queries'][0]['output_range'] = 'B1:B3'
        self.rejected()

    def test_separate_anchor_allowed(self):
        self.cfg['queries'][0]['anchor'] = 'D2'
        self.assertEqual(build(self.cfg)['queries'][0]['anchor'], 'D2')

    def test_parameter_collision_rejected(self):
        self.cfg['queries'][0]['parameters'][0]['cell'] = 'B2'; self.rejected()

    def test_own_anchor_in_result_allowed(self):
        self.assertEqual(build(self.cfg)['queries'][0]['output_range'], 'B2')

    def test_overlapping_result_regions_rejected(self):
        q = copy.deepcopy(self.cfg['queries'][0]); q['id']='other'; q['anchor']='F2';q['parameters']=[]
        self.cfg['queries'].append(q); self.rejected()

    def test_cross_query_anchor_collision_rejected(self):
        q = copy.deepcopy(self.cfg['queries'][0]); q['id']='other';q['anchor']='B2';q['output_range']='F2';q['parameters']=[]
        self.cfg['queries'].append(q); self.rejected()

    def test_later_region_rejects_earlier_parameter(self):
        q = copy.deepcopy(self.cfg['queries'][0]);q['id']='other';q['anchor']='F2';q['output_range']='A2';q['parameters']=[]
        self.cfg['queries'].append(q);self.rejected()

    def test_duplicate_parameters(self):
        self.cfg['queries'][0]['parameters'].append({'cell':'A2','value':'Other'});self.rejected()

    def test_duplicate_output(self):
        self.cfg['outputs'].append(copy.deepcopy(self.cfg['outputs'][0]));self.rejected()

    def test_output_not_from_query_range(self):
        self.cfg['outputs'][0]['source_cell']='Z99';self.rejected()

    def test_query_not_found(self):
        self.cfg['outputs'][0]['query_id']='unknown';self.rejected()

    def test_reserved_sheet_case_insensitive(self):
        self.cfg['queries'][0]['sheet']='oUtPuTs';self.rejected()

    def test_sheet_case_conflict(self):
        q=copy.deepcopy(self.cfg['queries'][0]);q['id']='other';q['sheet']='raw data';q['anchor']='F2';q['output_range']='F2';q['parameters']=[]
        self.cfg['queries'].append(q);self.rejected()

    def test_sheet_invalid_characters(self):
        for name in ['A/B',"'Data", 'Data'*9]:
            self.cfg['queries'][0]['sheet']=name;self.rejected()

    def test_bounds(self):
        self.assertEqual(cell('XFD1048576'),(16384,1048576))
        for invalid in ['XFE1','A1048577','A0','$A$1','a1','A01','A1:B2',True,None]:
            with self.assertRaises(InputError):cell(invalid)

    def test_reversed_range(self):
        for invalid in ['B2:A3','A3:B2','A1:B2:C3']:
            with self.assertRaises(InputError):area(invalid)

    def test_literal_parameter_injection(self):
        self.cfg['queries'][0]['parameters'][0]['value']='=WEBSERVICE("x")';self.rejected()

    def test_formula_must_be_provider_call(self):
        for value in ['=SUM(A1)', '=SPG(A1)+1', '=SPG("unterminated)', '=SPG(A1))', '=SPG(A1)\n']:
            self.cfg['queries'][0]['formula']=value;self.rejected()

    def test_quoted_parentheses_are_not_syntax(self):
        self.cfg['queries'][0]['formula']='=SPG(A2,"A () and ""quoted"" text")'
        self.assertEqual(build(self.cfg)['cells'][0]['value'], self.cfg['queries'][0]['formula'])

    def test_fixture_status_cannot_claim_live(self):
        self.cfg['queries'][0]['syntax_status']='observed_control';self.rejected()

    def test_missing_unit(self):
        del self.cfg['outputs'][0]['unit'];self.rejected()

    def test_unknown_key(self):
        self.cfg['live_refresh']='PASS';self.rejected()

    def test_bad_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json'
            for text in ['{"a":1,"a":2}', '{"a":Infinity}', '['*1500+']'*1500]:
                p.write_text(text)
                with self.assertRaises(InputError):load(p)

    def test_bad_unicode_rejected(self):
        self.cfg['title']='x\ud800';self.rejected()

    def test_cli_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'result.json';cmd=[sys.executable,str(ROOT/'scripts/build_plan.py'),str(ROOT/'examples/config.json'),str(p)]
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            before=p.read_bytes();self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2);self.assertEqual(before,p.read_bytes())

    def test_cli_invalid_input_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text('{}');out=Path(tmp)/'result.json'
            run=subprocess.run([sys.executable,str(ROOT/'scripts/build_plan.py'),str(p),str(out)],capture_output=True,text=True)
            self.assertEqual(run.returncode,2);self.assertFalse(out.exists());self.assertNotIn('Traceback',run.stderr)


if __name__=='__main__':unittest.main()
