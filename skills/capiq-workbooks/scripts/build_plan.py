#!/usr/bin/env python3
"""Preserve supplied Capital IQ formulas in a checked layout plan; no data retrieval."""
import argparse
import json
from pathlib import Path
import re


class InputError(ValueError):
    pass


def text(value, name, maximum=300):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise InputError(f'{name}: nonempty text up to {maximum} characters required')
    if value != value.strip() or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in value):
        raise InputError(f'{name}: untrimmed or control characters')
    return value


def keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise InputError(f'{name}: expected keys {sorted(expected)}')


def cell(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]{0,6}', value):
        raise InputError('cell must be an uppercase A1 address without dollar signs')
    match = re.fullmatch(r'([A-Z]+)([0-9]+)', value)
    col = 0
    for letter in match[1]:
        col = col * 26 + ord(letter) - 64
    row = int(match[2])
    if col > 16384 or row > 1048576:
        raise InputError('cell exceeds Excel bounds')
    return col, row


def area(value):
    if not isinstance(value, str) or value.count(':') > 1:
        raise InputError('range must contain one cell or two A1 endpoints')
    parts = value.split(':')
    start, end = cell(parts[0]), cell(parts[-1])
    if start[0] > end[0] or start[1] > end[1]:
        raise InputError('range endpoints must run top-left to bottom-right')
    return start[0], start[1], end[0], end[1]


def contains(box, position):
    return box[0] <= position[0] <= box[2] and box[1] <= position[1] <= box[3]


def overlaps(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def sheet_name(value):
    text(value, 'sheet', 31)
    if any(c in value for c in '[]:*?/\\') or value.startswith("'") or value.endswith("'"):
        raise InputError('invalid worksheet name')
    return value


def formula(value):
    text(value, 'formula', 8192)
    match = re.match(r'^=@?(?:_xll\.)?(?:SNL\.Clients\.Office\.Excel\.Functions\.)?(SPGTable|SPGScreen|SPGRANGEV|SPG|CIQRANGEV|CIQRANGE|CIQ)\(', value)
    if not match:
        raise InputError('expected a complete supported Pro or legacy provider formula')
    # This checks enclosing syntax only. It deliberately does not interpret arguments.
    depth = 0
    quote = None
    i = 1
    while i < len(value):
        c = value[i]
        if quote:
            if c == quote:
                if i + 1 < len(value) and value[i + 1] == quote:
                    i += 2
                    continue
                quote = None
        elif c in ('"', "'"):
            quote = c
        else:
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth < 0 or (depth == 0 and i != len(value) - 1):
                    raise InputError('formula must be one enclosing provider call')
        i += 1
    if quote or depth != 0 or not value.endswith(')'):
        raise InputError('unclosed provider call or string')
    return match[1]


def build(config):
    keys(config, {'title', 'fixture', 'queries', 'outputs'}, 'config')
    text(config['title'], 'title')
    if type(config['fixture']) is not bool:
        raise InputError('fixture must be a boolean')
    for name in ('queries', 'outputs'):
        if not isinstance(config[name], list) or not 1 <= len(config[name]) <= 100:
            raise InputError(f'{name}: expected 1 to 100 records')
    queries = {}
    normalized_sheets = {}
    assignments = []
    for q in config['queries']:
        keys(q, {'id', 'sheet', 'anchor', 'output_range', 'formula', 'syntax_source', 'syntax_status', 'parameters'}, 'query')
        text(q['id'], 'id', 50)
        if q['id'] in queries:
            raise InputError('duplicate query id')
        sheet = sheet_name(q['sheet'])
        if sheet.casefold() == 'outputs':
            raise InputError('Outputs is reserved for presentation links')
        prior = normalized_sheets.setdefault(sheet.casefold(), sheet)
        if prior != sheet:
            raise InputError('worksheet names differ only by case')
        anchor, box = cell(q['anchor']), area(q['output_range'])
        if contains(box, anchor) and anchor != (box[0], box[1]):
            raise InputError('an in-range query anchor must be the result range top-left cell')
        function = formula(q['formula'])
        text(q['syntax_source'], 'syntax_source', 1000)
        permitted = ('synthetic_fixture',) if config['fixture'] else ('addin_generated', 'observed_control')
        if q['syntax_status'] not in permitted:
            raise InputError('syntax_status incompatible with fixture flag')
        if not isinstance(q['parameters'], list) or len(q['parameters']) > 100:
            raise InputError('parameters must be a list of at most 100 literal cells')
        queries[q['id']] = (q, box, anchor, function)
        assignments.append((q['id'], sheet, q['anchor'], q['formula'], 'provider_formula'))
        for p in q['parameters']:
            keys(p, {'cell', 'value'}, 'parameter')
            cell(p['cell'])
            text(p['value'], 'parameter value', 1000)
            if p['value'][0] in '=+-@':
                raise InputError('parameters must be literal text; formulas are not accepted')
            assignments.append((q['id'], sheet, p['cell'], p['value'], 'literal_parameter'))
    ordered = list(queries.values())
    for i, (q, box, anchor, _) in enumerate(ordered):
        for other, other_box, _, _ in ordered[i+1:]:
            if q['sheet'] == other['sheet'] and overlaps(box, other_box):
                raise InputError('query output ranges overlap')
    occupied = set()
    for owner, sheet, address, value, role in assignments:
        key = (sheet, address)
        if key in occupied:
            raise InputError('multiple assignments to one cell')
        occupied.add(key)
        for q, box, _, _ in ordered:
            if q['sheet'] == sheet and contains(box, cell(address)):
                if not (owner == q['id'] and role == 'provider_formula' and address == q['anchor']):
                    raise InputError('assigned cell collides with reserved returned-data range')
    cells = [{'sheet': sheet, 'cell': address, 'value': value, 'role': role}
             for _, sheet, address, value, role in assignments]
    output_metadata = []
    for o in config['outputs']:
        keys(o, {'cell', 'query_id', 'source_cell', 'label', 'unit', 'period', 'currency', 'quote_side'}, 'output')
        destination = cell(o['cell'])
        if ('Outputs', o['cell']) in occupied:
            raise InputError('duplicate output destination')
        occupied.add(('Outputs', o['cell']))
        if not isinstance(o['query_id'], str) or o['query_id'] not in queries:
            raise InputError('unknown output query id')
        q, box, _, _ = queries[o['query_id']]
        if not contains(box, cell(o['source_cell'])):
            raise InputError('output source is outside its query result range')
        for name in ('label', 'unit', 'period', 'currency', 'quote_side'):
            text(o[name], name)
        safe_sheet = q['sheet'].replace("'", "''")
        cells.append({'sheet': 'Outputs', 'cell': o['cell'],
                      'value': f"='{safe_sheet}'!{o['source_cell']}", 'role': 'presentation_link'})
        output_metadata.append(dict(o))
    return {'schema_version': 1, 'title': config['title'], 'fixture': config['fixture'],
            'status': 'FORMULA_PLAN_ONLY', 'live_refresh': 'NOT_RUN', 'cells': cells,
            'queries': [{'id': q['id'], 'sheet': q['sheet'], 'anchor': q['anchor'], 'output_range': q['output_range'],
                         'function': function, 'syntax_status': q['syntax_status'], 'syntax_source': q['syntax_source']}
                        for q, _, _, function in ordered], 'output_metadata': output_metadata,
            'limits': ['Caller-supplied formula and evidence; no verification of provider arguments or entitlement',
                       'Layout checks cover only declared ranges and assigned cells',
                       'No XLSX authoring, provider execution, cached values or snapshot']}


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InputError('duplicate JSON key')
            result[key] = value
        return result
    try:
        if Path(path).stat().st_size > 1_000_000:
            raise InputError('config exceeds 1 MB')
        return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(InputError('nonfinite JSON number')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InputError(str(exc)) from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    parser.add_argument('output', help='new JSON file; no overwrite')
    args = parser.parse_args()
    try:
        result = build(load(args.config))
        content = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
        with open(args.output, 'x', encoding='utf-8') as stream:
            stream.write(content)
        print('Created formula plan; live refresh NOT_RUN')
        return 0
    except (InputError, OSError) as exc:
        print(f'ERROR: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
