#!/usr/bin/env python3
"""Recompute a declared debt/coverage snapshot without using model formulas."""
import argparse
from collections import Counter
from datetime import date
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

INPUTS = ('drawdown', 'repayment', 'interest', 'cfads')
OUTPUTS = ('opening_debt', 'closing_debt', 'debt_service', 'dscr', 'covenant')
MAX_BYTES = 2_000_000


class InputError(ValueError):
    pass


def keys(obj, expected, where):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise InputError(f'{where}: expected exactly {", ".join(expected)}')


def number(value, where, nullable=True, nonnegative=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,23})(?:\.[0-9]{1,12})?', value):
        raise InputError(f'{where}: use a bounded decimal string' + (' or null' if nullable else ''))
    result = Fraction(value)
    if nonnegative and result < 0:
        raise InputError(f'{where}: must be nonnegative')
    return result


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def load(raw):
    if len(raw) > MAX_BYTES:
        raise InputError('input exceeds 2,000,000 bytes')
    try:
        result = json.loads(raw, object_pairs_hook=unique_object,
                            parse_constant=lambda x: (_ for _ in ()).throw(InputError('nonfinite JSON value')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InputError('invalid JSON: ' + type(exc).__name__) from exc
    pending = [(result, 0)]
    while pending:
        node, depth = pending.pop()
        if depth > 20:
            raise InputError("JSON nesting exceeds 20 levels")
        if isinstance(node, dict):
            pending.extend((v, depth + 1) for v in node.values())
        elif isinstance(node, list):
            pending.extend((v, depth + 1) for v in node)
    return result


def validate(data):
    keys(data, ('schema_version', 'model_id', 'model_sha256', 'currency', 'amount_unit',
                'periods', 'initial_debt', 'required_final_debt', 'money_tolerance',
                'ratio_tolerance', 'covenant', 'inputs', 'observed'), 'root')
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise InputError('schema_version must be 1')
    if not isinstance(data['model_id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', data['model_id']):
        raise InputError('model_id must be a short identifier')
    if not isinstance(data['model_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', data['model_sha256']):
        raise InputError('model_sha256 must be lowercase SHA-256; it is caller-supplied')
    if not isinstance(data['currency'], str) or not re.fullmatch('[A-Z]{3}', data['currency']):
        raise InputError('currency must be three uppercase letters')
    if data['amount_unit'] not in ('units', 'thousands', 'millions'):
        raise InputError('amount_unit must be units, thousands or millions')
    periods = data['periods']
    if not isinstance(periods, list) or not 1 <= len(periods) <= 500:
        raise InputError('periods must contain 1..500 entries')
    ids, previous_end = [], None
    for period in periods:
        keys(period, ('id', 'start', 'end'), 'period')
        if not isinstance(period['id'], str) or not re.fullmatch('[A-Za-z0-9_-]{1,32}', period['id']):
            raise InputError('invalid period ID')
        if period['id'] in ids:
            raise InputError('duplicate period ID')
        try:
            start, end = date.fromisoformat(period['start']), date.fromisoformat(period['end'])
        except (ValueError, TypeError) as exc:
            raise InputError('period dates must be ISO dates') from exc
        if start.isoformat() != period['start'] or end.isoformat() != period['end'] or start >= end:
            raise InputError('period must have canonical dates and start before end')
        if previous_end is not None and start != previous_end:
            raise InputError('periods must be consecutive half-open intervals')
        ids.append(period['id']); previous_end = end
    for name in ('initial_debt', 'required_final_debt', 'money_tolerance', 'ratio_tolerance'):
        number(data[name], name, nullable=name == 'required_final_debt', nonnegative=True)
    keys(data['covenant'], ('operator', 'threshold'), 'covenant')
    if data['covenant']['operator'] not in ('gte', 'lte'):
        raise InputError('covenant operator must be gte or lte')
    number(data['covenant']['threshold'], 'threshold', nonnegative=True)
    for block_name, metrics in (('inputs', INPUTS), ('observed', OUTPUTS)):
        block = data[block_name]
        keys(block, ('period_ids', 'currency', 'amount_unit', 'series', 'references'), block_name)
        if block['period_ids'] != ids or block['currency'] != data['currency'] or block['amount_unit'] != data['amount_unit']:
            raise InputError(block_name + ': period order, currency and amount unit must match root')
        keys(block['series'], metrics, block_name + '.series')
        keys(block['references'], metrics, block_name + '.references')
        for metric in metrics:
            values, refs = block['series'][metric], block['references'][metric]
            if not isinstance(values, list) or len(values) != len(ids) or not isinstance(refs, list) or len(refs) != len(ids):
                raise InputError(block_name + '.' + metric + ': length must match periods')
            for i, (value, ref) in enumerate(zip(values, refs)):
                if not isinstance(ref, str) or not re.fullmatch(r"[A-Za-z0-9 _'!$:.()-]{1,120}", ref):
                    raise InputError('invalid source-cell reference')
                if metric == 'covenant':
                    if value not in ('PASS', 'FAIL', 'UNDEFINED', None):
                        raise InputError('observed covenant must be PASS, FAIL, UNDEFINED or null')
                else:
                    number(value, f'{block_name}.{metric}[{i}]', nonnegative=block_name == 'inputs' and metric != 'cfads')
    return data


def exact(value):
    if value is None:
        return None
    if not isinstance(value, Fraction):
        return value
    return str(value.numerator) if value.denominator == 1 else f'{value.numerator}/{value.denominator}'


def audit(data):
    validate(data)
    results = []
    source = data['inputs']['series']; observed = data['observed']['series']
    refs = data['inputs']['references']; outrefs = data['observed']['references']
    money_tol, ratio_tol = Fraction(data['money_tolerance']), Fraction(data['ratio_tolerance'])
    carry = Fraction(data['initial_debt'])
    threshold = number(data['covenant']['threshold'], 'threshold')

    def record(period, check, expected, actual, status, method, source_refs, target):
        results.append(dict(period=period, check=check, status=status, expected=exact(expected),
                            observed=exact(actual), method=method, input_references=source_refs,
                            output_reference=target))

    def compare(period, check, expected, actual, tolerance, method, source_refs, target):
        status = 'UNVERIFIED' if expected is None or actual is None else ('PASS' if abs(expected - actual) <= tolerance else 'FAIL')
        record(period, check, expected, actual, status, method, source_refs, target)

    for i, period in enumerate(data['periods']):
        pid = period['id']
        draw, repay, interest, cfads = [number(source[m][i], m) for m in INPUTS]
        actual = {m: (observed[m][i] if m == 'covenant' else number(observed[m][i], m)) for m in OUTPUTS}
        closing = carry + draw - repay if None not in (carry, draw, repay) else None
        service = repay + interest if None not in (repay, interest) else None
        debtrefs = [refs[m][i] for m in ('drawdown', 'repayment')]
        # Carry is recomputed from all preceding inputs; never adopt a model closing balance.
        prior_refs = ['root.initial_debt'] + [refs[m][j] for j in range(i) for m in ('drawdown', 'repayment')]
        compare(pid, 'opening_debt', carry, actual['opening_debt'], money_tol,
                'initial debt plus all earlier drawdowns minus repayments', prior_refs, outrefs['opening_debt'][i])
        compare(pid, 'closing_debt', closing, actual['closing_debt'], money_tol,
                'recomputed opening plus drawdown minus repayment', prior_refs + debtrefs, outrefs['closing_debt'][i])
        record(pid, 'principal_nonnegative', '>= 0', closing,
               'UNVERIFIED' if closing is None else ('PASS' if closing >= 0 else 'FAIL'),
               'repayment cannot exceed available principal', prior_refs + debtrefs, outrefs['closing_debt'][i])
        compare(pid, 'debt_service', service, actual['debt_service'], money_tol,
                'repayment plus supplied cash interest', [refs[m][i] for m in ('repayment', 'interest')], outrefs['debt_service'][i])
        ratio = cfads / service if cfads is not None and service not in (None, 0) else None
        ratio_refs = [refs[m][i] for m in ('cfads', 'repayment', 'interest')]
        if service == 0 and cfads is not None:
            record(pid, 'dscr', None, actual['dscr'], 'NOT_APPLICABLE' if actual['dscr'] is None else 'FAIL',
                   'zero debt service makes DSCR undefined', ratio_refs, outrefs['dscr'][i])
        else:
            compare(pid, 'dscr', ratio, actual['dscr'], ratio_tol,
                    'CFADS divided by recomputed debt service', ratio_refs, outrefs['dscr'][i])
        if service == 0 and cfads is not None:
            expected = 'UNDEFINED'
            state = 'UNVERIFIED' if actual['covenant'] is None else ('NOT_APPLICABLE' if actual['covenant'] == expected else 'FAIL')
        elif ratio is None or threshold is None:
            expected, state = None, 'UNVERIFIED'
        else:
            passes = ratio >= threshold if data['covenant']['operator'] == 'gte' else ratio <= threshold
            expected = 'PASS' if passes else 'FAIL'
            state = 'UNVERIFIED' if actual['covenant'] is None else ('PASS' if actual['covenant'] == expected else 'FAIL')
        record(pid, 'covenant', expected, actual['covenant'], state,
               'exact unrounded DSCR ' + data['covenant']['operator'] + ' supplied threshold; no comparison tolerance',
               ratio_refs + ['root.covenant.threshold'], outrefs['covenant'][i])
        if i:
            previous_close = number(observed['closing_debt'][i-1], 'previous closing')
            compare(pid, 'reported_continuity', previous_close, actual['opening_debt'], money_tol,
                    'reported opening equals previous reported closing', [outrefs['closing_debt'][i-1]], outrefs['opening_debt'][i])
        carry = closing
    final_target = number(data['required_final_debt'], 'final debt')
    if final_target is not None:
        compare(data['periods'][-1]['id'], 'final_principal', final_target, carry, money_tol,
                'recomputed final principal equals explicit target', ['root.required_final_debt'], 'recomputed final principal')
    counts = dict(Counter(r['status'] for r in results))
    status = 'FINDINGS' if counts.get('FAIL') else ('INCOMPLETE' if counts.get('UNVERIFIED') else 'CHECKS_PASSED')
    return dict(schema_version=1, model_id=data['model_id'], claimed_model_sha256=data['model_sha256'],
                model_file_verified=False, status=status, currency=data['currency'], amount_unit=data['amount_unit'],
                money_tolerance=data['money_tolerance'], ratio_tolerance=data['ratio_tolerance'], covenant=data['covenant'],
                period_count=len(data['periods']), check_count=len(results), counts=counts, checks=results,
                required_final_debt=data['required_final_debt'], final_principal_checked=final_target is not None,
                covenant_breach_periods=[r['period'] for r in results if r['check'] == 'covenant' and r['expected'] == 'FAIL'],
                limits=['Normalized snapshot only; mapping and model-file identity are caller-supplied.',
                        'No spreadsheet calculation, formula inspection, interest accrual verification or source-document review.',
                        'Arithmetic is recomputed separately from reported outputs; this is not an independent professional audit.',
                        'CHECKS_PASSED means checked outputs agree, not that covenants are met or a loan is affordable.'])


def markdown(report):
    lines = ['# Model audit demonstration', '', f"Result: **{report['status']}**", '',
             f"Model: {report['model_id']}. Amounts: {report['currency']} {report['amount_unit']}.",
             f"Periods: {report['period_count']}. Checks: {report['check_count']}.",
             'Recomputed covenant breach periods: ' + (', '.join(report['covenant_breach_periods']) or 'none established') + '.',
             'Final-principal target checked: ' + str(report['final_principal_checked']) + '.',
             f"Absolute tolerances: money {report['money_tolerance']}; ratio {report['ratio_tolerance']}.", '',
             '| Period | Check | Expected | Observed | Result |', '| --- | --- | --- | --- | --- |']
    for r in report['checks']:
        lines.append('| ' + ' | '.join(str(r[k]) if r[k] is not None else 'unknown / undefined' for k in ('period', 'check', 'expected', 'observed', 'status')) + ' |')
    lines += ['', '## Scope', ''] + ['- ' + x for x in report['limits']]
    lines += ['', 'Snapshot SHA-256: `' + report['snapshot_sha256'] + '`.', '']
    return '\n'.join(lines)


def run(input_path, output_path):
    raw = input_path.read_bytes()
    report = audit(load(raw)); report['snapshot_sha256'] = hashlib.sha256(raw).hexdigest()
    if input_path.read_bytes() != raw:
        raise InputError('input changed during audit')
    output_path.mkdir(parents=False, exist_ok=False)
    (output_path / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (output_path / 'report.md').write_text(markdown(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(args.input, args.out)
        print(f"{report['status']}: {report['check_count']} checks; {args.out}")
        return 1 if report['status'] != 'CHECKS_PASSED' else 0
    except (InputError, OSError, TypeError, OverflowError, RecursionError) as exc:
        print('ERROR: ' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
