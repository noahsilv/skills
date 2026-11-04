#!/usr/bin/env python3
"""Build a new BDP formula matrix. No provider calls or cached returns are made."""
import argparse
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import re

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


class InputError(ValueError):
    pass


def text(value, name, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise InputError(f'{name}: nonempty text up to {limit} characters required')
    if value != value.strip() or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in value) or value[0] in '=+-@':
        raise InputError(f'{name}: unsafe or untrimmed literal text')
    return value


def keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise InputError(f'{name}: expected keys {sorted(expected)}')


def validate(config):
    keys(config, {'title', 'reference_date', 'fixture', 'function', 'securities', 'fields'}, 'config')
    text(config['title'], 'title')
    if type(config['fixture']) is not bool:
        raise InputError('fixture must be a boolean')
    if config['function'] not in ('BDP', '_xll.BDP'):
        raise InputError('function must be BDP or _xll.BDP')
    if not isinstance(config['reference_date'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', config['reference_date']):
        raise InputError('reference_date must be YYYY-MM-DD')
    try:
        date.fromisoformat(config['reference_date'])
    except ValueError as exc:
        raise InputError('reference_date is not a calendar date') from exc
    for group, maximum in [('securities', 500), ('fields', 100)]:
        values = config[group]
        if not isinstance(values, list) or not 1 <= len(values) <= maximum:
            raise InputError(f'{group}: expected 1 to {maximum} records')
    identifiers = set()
    for item in config['securities']:
        keys(item, {'label', 'identifier', 'evidence'}, 'security')
        for key, value in item.items():
            text(value, 'security.' + key, 500 if key == 'evidence' else 200)
        if item['identifier'] in identifiers:
            raise InputError('duplicate security identifier')
        identifiers.add(item['identifier'])
    fields = set()
    for item in config['fields']:
        keys(item, {'label', 'mnemonic', 'unit', 'evidence'}, 'field')
        for key, value in item.items():
            text(value, 'field.' + key, 500 if key == 'evidence' else 200)
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', item['mnemonic']):
            raise InputError('field mnemonic must use uppercase letters, digits and underscores')
        if item['mnemonic'] in fields:
            raise InputError('duplicate field mnemonic')
        fields.add(item['mnemonic'])
    return config


def build(config):
    validate(config)
    wb = Workbook()
    wb.remove(wb.active)
    control = wb.create_sheet('Controls')
    label = 'SYNTHETIC FIXTURE - identifiers are not provider-verified' if config['fixture'] else 'FORMULA TEMPLATE - identifiers and fields require evidence review'
    for row in [ ['Item', 'Value'], ['Title', config['title']], ['Purpose', label],
                 ['Reference date', config['reference_date']], ['Live refresh', 'NOT_RUN'],
                 ['Confirmed refresh timestamp', None], ['Function', config['function']],
                 ['Cache policy', 'No returned values or snapshot created'] ]:
        control.append(row)
    securities = wb.create_sheet('Securities')
    securities.append(['Label', 'Identifier', 'Caller-supplied evidence'])
    for item in config['securities']:
        securities.append([item['label'], item['identifier'], item['evidence']])
    fields = wb.create_sheet('Fields')
    fields.append(['Label', 'Mnemonic', 'Expected unit', 'Caller-supplied evidence'])
    for item in config['fields']:
        fields.append([item['label'], item['mnemonic'], item['unit'], item['evidence']])
    live = wb.create_sheet('Live')
    live.append(['Security'] + [f"{f['label']} [{f['unit']}]" for f in config['fields']])
    for i, item in enumerate(config['securities'], 2):
        live.cell(i, 1, f'=Securities!B{i}')
        for j, field in enumerate(config['fields'], 2):
            live.cell(i, j, f"={config['function']}(Securities!$B{i},Fields!$B${j})")
    for sheet in wb:
        sheet.freeze_panes = 'B2'
        sheet.sheet_view.showGridLines = False
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='243B53')
        for column in range(1, sheet.max_column + 1):
            sheet.column_dimensions[get_column_letter(column)].width = 34
    wb.properties.creator = 'Portfolio demonstration'
    wb.calculation.fullCalcOnLoad = True
    report = {'schema_version': 1, 'fixture': config['fixture'], 'status': 'FORMULAS_CONSTRUCTED',
              'live_refresh': 'NOT_RUN', 'reference_date': config['reference_date'],
              'provider_formula_count': len(config['securities']) * len(config['fields']),
              'function': config['function'], 'snapshot_created': False,
              'evidence_status': 'Caller statements recorded; not independently verified',
              'limits': ['BDP only; no BDH/BDS layout generation', 'No provider connection, entitlement or field coverage check',
                         'No native Excel rendering or recalculation performed', 'Reference date does not establish quote time']}
    return wb, report


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
    parser.add_argument('output_dir', help='new directory; never overwrite an existing path')
    args = parser.parse_args()
    try:
        wb, report = build(load(args.config))
        buf = BytesIO()
        wb.save(buf)
        out = Path(args.output_dir)
        out.mkdir(parents=False, exist_ok=False)
        (out / 'workbook.xlsx').write_bytes(buf.getvalue())
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Created workbook.xlsx and report.json; live refresh NOT_RUN')
        return 0
    except (InputError, OSError) as exc:
        print(f'ERROR: {exc}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
