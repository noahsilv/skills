#!/usr/bin/env python3
"""Retrieve one annual World Bank Indicators API series with explicit gaps."""
import argparse
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

BASE = 'https://api.worldbank.org/v2'
MAX_BYTES = 2_000_000
PER_PAGE = 100
MAX_PAGES = 20


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def string(value, label, limit=1000, empty=False):
    require(isinstance(value, str) and len(value) <= limit, f'invalid {label}')
    require((empty or bool(value.strip())) and not any(ord(c) < 32 for c in value), f'invalid {label}')
    return value


def integer(value, label, low=0, high=10000):
    if isinstance(value, str) and re.fullmatch(r'[0-9]{1,6}', value):
        value = int(value)
    require(type(value) is int and low <= value <= high, f'invalid {label}')
    return value


def reject_duplicate(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, 'duplicate JSON key')
        out[key] = value
    return out


def decode(blob):
    require(isinstance(blob, bytes) and len(blob) <= MAX_BYTES, 'response/input byte limit exceeded')
    try:
        value = json.loads(blob.decode('utf-8'), parse_float=Decimal,
                          parse_constant=lambda _: (_ for _ in ()).throw(ContractError('non-finite JSON number')),
                          object_pairs_hook=reject_duplicate)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError('invalid JSON') from exc
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        require(depth <= 30, 'JSON nesting limit exceeded')
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return value


def request_contract(raw):
    require(isinstance(raw, dict) and set(raw) == {'country', 'indicator', 'source_id', 'start_year', 'end_year', 'unit'}, 'request fields differ from contract')
    require(isinstance(raw['country'], str) and re.fullmatch('[A-Z]{3}', raw['country']), 'country must be one uppercase ISO3 code')
    require(isinstance(raw['indicator'], str) and re.fullmatch(r'[A-Z][A-Z0-9_.]{0,79}', raw['indicator']), 'invalid indicator ID')
    source = integer(raw['source_id'], 'source ID', 1, 9999)
    start = integer(raw['start_year'], 'start year', 1900, 2200)
    end = integer(raw['end_year'], 'end year', 1900, 2200)
    require(start <= end and end - start < 100, 'request must cover 1 to 100 annual periods')
    unit = string(raw['unit'], 'caller unit', 100)
    return {**raw, 'source_id': source, 'start_year': start, 'end_year': end, 'unit': unit}


def urls(spec, page=1):
    integer(page, 'page', 1, MAX_PAGES)
    meta = f"{BASE}/indicator/{spec['indicator']}?" + urlencode({'format': 'json', 'source': spec['source_id'], 'per_page': PER_PAGE})
    data = f"{BASE}/country/{spec['country']}/indicator/{spec['indicator']}?" + urlencode({
        'format': 'json', 'source': spec['source_id'], 'date': f"{spec['start_year']}:{spec['end_year']}", 'per_page': PER_PAGE, 'page': page})
    return meta, data


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ContractError('upstream redirect refused')


class LiveTransport:
    mode = 'live'

    def __init__(self):
        self.opener = build_opener(NoRedirect())

    def read(self, key, url):
        require(url.startswith(BASE + '/'), 'unsupported endpoint')
        try:
            with self.opener.open(Request(url, headers={'Accept': 'application/json', 'User-Agent': 'FinancialDataPortfolio/1.0'}), timeout=20) as response:
                require(response.status == 200, 'unexpected HTTP status')
                blob = response.read(MAX_BYTES + 1)
        except (HTTPError, URLError, HTTPException, TimeoutError, OSError) as exc:
            raise ContractError('upstream request failed; no complete result written') from exc
        require(len(blob) <= MAX_BYTES, 'response byte limit exceeded')
        return blob


class FixtureTransport:
    mode = 'synthetic-fixture'

    def __init__(self, directory):
        self.directory = Path(directory)

    def read(self, key, url):
        return (self.directory / (key + '.json')).read_bytes()


def envelope(payload):
    require(isinstance(payload, list) and len(payload) == 2, 'expected API metadata and rows')
    head, rows = payload
    if isinstance(head, dict) and head.get('total') in (0, '0') and rows is None:
        rows = []
    require(isinstance(head, dict) and isinstance(rows, list), 'invalid API envelope or provider error')
    return head, rows


def timestamp(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value), 'retrieval timestamp must be UTC seconds')
    try:
        datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as exc:
        raise ContractError('invalid retrieval timestamp') from exc
    return value


def numeric(value):
    require(type(value) in (int, Decimal), 'value must be a JSON number or null')
    try:
        d = Decimal(value)
        require(d.is_finite() and len(d.as_tuple().digits) <= 100 and -100 <= d.as_tuple().exponent <= 100, 'numeric value outside supported range')
        return format(d, 'f')
    except (InvalidOperation, ValueError) as exc:
        raise ContractError('invalid numeric value') from exc


def retrieve(spec, transport, retrieved_at=None):
    spec = request_contract(spec)
    at = timestamp(retrieved_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    require(transport.mode in {'synthetic-fixture', 'live'}, 'unsupported transport mode')
    evidence = []

    def fetch(key, url):
        raw = transport.read(key, url)
        evidence.append({'request': key, 'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
        return decode(raw)

    meta_url, _ = urls(spec)
    mh, metadata = envelope(fetch('metadata', meta_url))
    require(integer(mh.get('page'), 'metadata page', 1) == 1 and integer(mh.get('pages'), 'metadata pages', 1) == 1 and integer(mh.get('total'), 'metadata count', 1) == 1 and len(metadata) == 1, 'metadata must resolve to exactly one indicator and source')
    info = metadata[0]
    require(isinstance(info, dict) and info.get('id') == spec['indicator'], 'metadata indicator differs')
    source = info.get('source')
    require(isinstance(source, dict) and integer(source.get('id'), 'metadata source', 1) == spec['source_id'], 'metadata source differs')
    source_name = string(source.get('value'), 'source name')
    indicator_name = string(info.get('name'), 'indicator name')
    provider_unit = string(info.get('unit'), 'metadata unit', 100, empty=True)
    require(not provider_unit or provider_unit == spec['unit'], 'metadata unit conflicts with caller unit')
    unit_basis = 'provider-metadata' if provider_unit else 'caller-supplied; provider metadata unit is blank'
    observed, page = {}, 1
    expected = None
    rows_read = 0
    while True:
        _, url = urls(spec, page)
        head, rows = envelope(fetch(f'page-{page}', url))
        actual_page = integer(head.get('page'), 'response page', 1, MAX_PAGES)
        pages = integer(head.get('pages'), 'response pages', 0, MAX_PAGES)
        total = integer(head.get('total'), 'response total', 0, MAX_PAGES * PER_PAGE)
        per_page = integer(head.get('per_page'), 'response per_page', 1, PER_PAGE)
        source_id = integer(head.get('sourceid'), 'response source', 1, 9999)
        updated = string(head.get('lastupdated'), 'source lastupdated', 10)
        try:
            require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', updated) is not None, 'invalid source update date')
            date.fromisoformat(updated)
        except ValueError as exc:
            raise ContractError('invalid source update date') from exc
        require(actual_page == page and source_id == spec['source_id'], 'response page/source differs from request')
        require(pages == (total + per_page - 1) // per_page, 'inconsistent page count')
        current = (pages, total, per_page, updated, source_id)
        require(expected is None or current == expected, 'pagination metadata changed during retrieval')
        expected = current
        expected_rows = min(per_page, max(total - (page - 1) * per_page, 0))
        require(len(rows) == expected_rows, 'page row count differs from advertised coverage')
        rows_read += len(rows)
        for row in rows:
            require(isinstance(row, dict), 'invalid observation')
            require(row.get('countryiso3code') == spec['country'], 'observation country differs')
            require(isinstance(row.get('indicator'), dict) and row['indicator'].get('id') == spec['indicator'], 'observation indicator differs')
            year = row.get('date')
            require(isinstance(year, str) and re.fullmatch('[0-9]{4}', year), 'observation period is not annual')
            require(spec['start_year'] <= int(year) <= spec['end_year'], 'observation outside requested periods')
            require(year not in observed, 'duplicate country/indicator/year observation')
            row_unit = string(row.get('unit'), 'observation unit', 100, empty=True)
            require(not row_unit or row_unit == spec['unit'], 'observation unit conflicts with caller unit')
            require('value' in row, 'observation lacks value field')
            value = None if row['value'] is None else numeric(row['value'])
            status = string(row.get('obs_status', ''), 'observation status', 100, empty=True)
            observed[year] = {'value': value, 'gap': 'provider returned null' if value is None else None, 'observation_status': status, 'response_url': url}
        if page >= pages:
            break
        page += 1
    require(rows_read == expected[1], 'incomplete advertised observations')
    output = []
    for year in range(spec['start_year'], spec['end_year'] + 1):
        o = observed.get(str(year), {'value': None, 'gap': 'provider omitted requested year', 'observation_status': '', 'response_url': None})
        output.append({'country': spec['country'], 'indicator': spec['indicator'], 'period': str(year), **o,
                       'unit': spec['unit'], 'unit_basis': unit_basis, 'source': source_name,
                       'source_id': spec['source_id'], 'retrieved_at': at, 'source_last_updated': expected[3], 'mode': transport.mode})
    gaps = sum(row['gap'] is not None for row in output)
    return {'schema_version': 1, 'mode': transport.mode, 'status': 'COMPLETE_WITH_GAPS' if gaps else 'COMPLETE',
            'request': spec, 'indicator_name': indicator_name, 'metadata_url': meta_url,
            'request_count': len(evidence), 'provider_rows': rows_read, 'gap_count': gaps,
            'rows': output, 'responses': evidence}


def md(value):
    return str(value).replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;')


def report(result):
    lines = ['# Annual indicator retrieval', '', f"Mode: **{result['mode']}**. Status: **{result['status']}**.", '',
             'Synthetic-fixture mode contains invented observations and does not contact the provider.' if result['mode'] == 'synthetic-fixture' else 'Live mode records a successful API retrieval; it does not certify economic accuracy.', '',
             f"Indicator: {md(result['request']['indicator'])}. {md(result['indicator_name'])}.",
             f"Requests: {result['request_count']}. Provider rows: {result['provider_rows']}. Gaps: {result['gap_count']}.", '',
             '| Country | Period | Value | Unit | Gap |', '| --- | --- | --- | --- | --- |']
    for row in result['rows']:
        lines.append('| ' + ' | '.join(md(row[k]) if row[k] is not None else '' for k in ['country', 'period', 'value', 'unit', 'gap']) + ' |')
    first = result['rows'][0]
    lines += ['', f"Unit basis: {md(first['unit_basis'])}.", f"Retrieved at: {first['retrieved_at']}. Source last updated: {first['source_last_updated']}.",
              '', 'The JSON records request URLs and response hashes. Retrieval time is separate from the source update date.',
              'Missing observations are not zero. No interpolation, currency conversion or revision history is inferred.', '']
    return '\n'.join(lines)


def write(result, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'report.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (out / 'report.md').write_text(report(result), encoding='utf-8')
    with (out / 'observations.csv').open('w', newline='', encoding='utf-8') as handle:
        w = csv.DictWriter(handle, fieldnames=list(result['rows'][0]))
        w.writeheader()
        for row in result['rows']:
            # Apostrophe protects formula-looking text in spreadsheet imports; JSON is canonical.
            w.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) and k != 'value' else v for k, v in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fixtures')
    mode.add_argument('--live', action='store_true')
    parser.add_argument('--retrieved-at', help='fixed UTC timestamp for fixture replay only')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        require(not args.live or args.retrieved_at is None, 'live retrieval timestamps cannot be overridden')
        raw = Path(args.request).read_bytes()
        spec = request_contract(decode(raw))
        require(not Path(args.out).exists(), 'output path already exists')
        transport = FixtureTransport(args.fixtures) if args.fixtures else LiveTransport()
        result = retrieve(spec, transport, args.retrieved_at)
        result['request_sha256'] = hashlib.sha256(raw).hexdigest()
        require(Path(args.request).read_bytes() == raw, 'request file changed during retrieval')
        write(result, args.out)
        print(f"{result['mode']}: {result['status']}; {result['gap_count']} gaps; output written")
        return 0
    except (ContractError, OSError, ValueError, RecursionError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
