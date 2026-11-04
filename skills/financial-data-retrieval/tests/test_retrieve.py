import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock
from http.client import IncompleteRead, BadStatusLine
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('data_retrieve_under_test', ROOT / 'scripts/retrieve.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
REQUEST = json.loads((ROOT / 'examples/request.json').read_text())
FIXTURES = {p.stem: json.loads(p.read_text()) for p in (ROOT / 'examples/fixtures').glob('*.json')}
AT = '2026-11-04T00:00:00Z'


class Memory:
    mode = 'synthetic-fixture'
    def __init__(self, data=None):
        self.data = copy.deepcopy(FIXTURES if data is None else data)
        self.calls = []
    def read(self, key, url):
        self.calls.append((key, url))
        return json.dumps(self.data[key]).encode()


class RetrievalTests(unittest.TestCase):
    def run_data(self, change=None, request=None):
        t = Memory()
        if change:
            change(t.data)
        return r.retrieve(request or REQUEST, t, AT)

    def test_happy_path_is_synthetic_with_two_distinct_gaps(self):
        out = self.run_data()
        self.assertEqual(out['mode'], 'synthetic-fixture')
        self.assertEqual(out['status'], 'COMPLETE_WITH_GAPS')
        self.assertEqual(out['request_count'], 3)
        self.assertEqual([x['value'] for x in out['rows']], ['0', None, None, '3.25'])
        self.assertEqual([x['gap'] for x in out['rows']], [None, 'provider omitted requested year', 'provider returned null', None])
        self.assertIn('caller-supplied', out['rows'][0]['unit_basis'])

    def test_provenance_and_raw_hashes_are_retained(self):
        out = self.run_data()
        self.assertTrue(all(len(x['sha256']) == 64 for x in out['responses']))
        self.assertEqual(out['rows'][0]['retrieved_at'], AT)
        self.assertEqual(out['rows'][0]['source_last_updated'], '2026-01-15')
        self.assertEqual(out['rows'][0]['source_id'], 2)
        self.assertIn('page=2', out['rows'][0]['response_url'])

    def test_decimal_input_is_not_rounded(self):
        self.assertEqual(r.numeric(r.decode(b'1.234567890123456789')), '1.234567890123456789')

    def test_empty_result_creates_every_requested_gap(self):
        def change(d):
            d['page-1'] = [{'page':1,'pages':0,'per_page':100,'total':0,'sourceid':'2','lastupdated':'2026-01-15'}, None]
        out = self.run_data(change)
        self.assertEqual(out['gap_count'], 4)
        self.assertEqual(out['request_count'], 2)

    def test_complete_coverage_has_complete_status(self):
        q = {**REQUEST, 'start_year':2024}
        def change(d):
            d['page-1'][0].update(pages=1,total=1)
            d['page-1'][1] = d['page-1'][1][:1]
        self.assertEqual(self.run_data(change, q)['status'], 'COMPLETE')

    def test_provider_unit_is_checked(self):
        out = self.run_data(lambda d: d['metadata'][1][0].update(unit='percent'))
        self.assertEqual(out['rows'][0]['unit_basis'], 'provider-metadata')
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['metadata'][1][0].update(unit='USD'))

    def test_observation_unit_mismatch_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][1][0].update(unit='USD'))

    def test_changed_metadata_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-2'][0].update(lastupdated='2026-01-16'))

    def test_page_counter_repeated_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-2'][0].update(page=1))

    def test_short_page_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][1].pop())

    def test_extra_page_count_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][0].update(pages=3))

    def test_page_limit_rejected_before_more_requests(self):
        t = Memory()
        t.data['page-1'][0].update(pages=21)
        with self.assertRaises(r.ContractError): r.retrieve(REQUEST, t, AT)
        self.assertEqual(len(t.calls), 2)

    def test_duplicate_year_across_pages_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-2'][1][0].update(date='2024'))

    def test_out_of_scope_country_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][1][0].update(countryiso3code='USA'))

    def test_out_of_scope_indicator_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][1][0]['indicator'].update(id='OTHER'))

    def test_out_of_scope_period_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][1][0].update(date='2020'))

    def test_nonannual_period_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][1][0].update(date='2024Q1'))

    def test_source_mismatch_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][0].update(sourceid='3'))
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['metadata'][1][0]['source'].update(id='3'))

    def test_unresolved_metadata_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['metadata'][1].append(d['metadata'][1][0]))

    def test_missing_value_field_not_treated_as_null(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][1][0].pop('value'))

    def test_boolean_string_and_nonfinite_values_rejected(self):
        for value in [True, '3.2', float('inf'), float('nan')]:
            with self.subTest(value=value), self.assertRaises(r.ContractError):
                self.run_data(lambda d: d['page-1'][1][0].update(value=value))

    def test_huge_decimal_and_exponent_rejected(self):
        for value in [Decimal('1e10000'), Decimal('1e-10000'), 10**101]:
            with self.assertRaises(r.ContractError): r.numeric(value)

    def test_provider_error_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d.update({'page-1':[{'message':[{'key':'Invalid value'}]}]}))

    def test_request_path_injection_rejected(self):
        for k,v in [('country','USA;all'),('indicator','../other'),('indicator','X?source=4')]:
            with self.assertRaises(r.ContractError): r.request_contract({**REQUEST,k:v})

    def test_extra_fields_and_bad_years_rejected(self):
        for q in [{**REQUEST,'url':'http://localhost'}, {**REQUEST,'start_year':True}, {**REQUEST,'start_year':2025}, {**REQUEST,'start_year':1900}]:
            with self.assertRaises(r.ContractError): r.request_contract(q)

    def test_urls_pin_origin_source_and_time_scope(self):
        meta, data = r.urls(REQUEST,2)
        self.assertTrue(meta.startswith('https://api.worldbank.org/v2/indicator/DEMO.ANNUAL.RATE?'))
        self.assertIn('/country/ZZZ/',data)
        self.assertIn('date=2021%3A2024',data)
        self.assertIn('source=2',data)
        self.assertIn('page=2',data)

    def test_redirect_rejected(self):
        with self.assertRaises(r.ContractError):
            r.NoRedirect().redirect_request(None,None,302,'',{},'http://localhost')

    def test_incomplete_http_and_bad_status_are_sanitized(self):
        for error in [IncompleteRead(b'secret-body'), BadStatusLine('secret-status')]:
            transport = r.LiveTransport()
            transport.opener = MagicMock()
            transport.opener.open.side_effect = error
            with self.assertRaises(r.ContractError) as caught:
                transport.read('page-1', r.urls(REQUEST)[1])
            self.assertEqual(str(caught.exception), 'upstream request failed; no complete result written')

    def test_incomplete_response_body_is_sanitized(self):
        transport = r.LiveTransport()
        transport.opener = MagicMock()
        response = transport.opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.side_effect = IncompleteRead(b'secret-body')
        with self.assertRaises(r.ContractError) as caught:
            transport.read('page-1', r.urls(REQUEST)[1])
        self.assertNotIn('secret-body', str(caught.exception))

    def test_json_duplicate_keys_depth_and_size_rejected(self):
        for blob in [b'{"x":1,"x":2}', b'['*2000+b']'*2000, b' '* (r.MAX_BYTES+1), b'\xff']:
            with self.assertRaises(r.ContractError): r.decode(blob)

    def test_bad_source_date_rejected(self):
        with self.assertRaises(r.ContractError):
            self.run_data(lambda d: d['page-1'][0].update(lastupdated='2026-02-31'))

    def test_timestamp_requires_utc_calendar_time(self):
        for at in ['2026-11-04','2026-02-31T00:00:00Z','2026-11-04T00:00:00+01:00']:
            with self.assertRaises(r.ContractError): r.timestamp(at)

    def test_outputs_keep_zero_missing_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'out'
            r.write(self.run_data(),out)
            doc=json.loads((out/'report.json').read_text())
            self.assertEqual(doc['rows'][0]['value'],'0')
            self.assertIsNone(doc['rows'][1]['value'])
            self.assertIn('invented observations', (out/'report.md').read_text())
            with self.assertRaises(FileExistsError): r.write(doc,out)

    def test_formula_looking_metadata_escaped_only_in_csv(self):
        data = self.run_data(lambda d: d['metadata'][1][0]['source'].update(value='=BAD()'))
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'out';r.write(data,out)
            self.assertIn("'=BAD()",(out/'observations.csv').read_text())
            self.assertIn('=BAD()',json.loads((out/'report.json').read_text())['rows'][0]['source'])

    def test_cli_fixture_and_bad_input_exit_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'out'
            cmd=[sys.executable,str(ROOT/'scripts/retrieve.py'),str(ROOT/'examples/request.json'),'--fixtures',str(ROOT/'examples/fixtures'),'--retrieved-at',AT,'--out',str(out)]
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2)
            bad=Path(temp)/'bad.json';bad.write_text('['*2000+']'*2000)
            cmd[2]=str(bad);cmd[-1]=str(Path(temp)/'badout')
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertNotIn('Traceback',result.stderr)
            self.assertFalse(Path(cmd[-1]).exists())

    def test_live_timestamp_override_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as temp:
            result=subprocess.run([sys.executable,str(ROOT/'scripts/retrieve.py'),str(ROOT/'examples/request.json'),'--live','--retrieved-at',AT,'--out',str(Path(temp)/'out')],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('cannot be overridden',result.stderr)

if __name__ == '__main__': unittest.main()
