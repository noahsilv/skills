#!/usr/bin/env python3
"""Write synthetic snapshots; no workbook or external data is read."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def clean():
    periods = [{'id': 'Y1', 'start': '2030-01-01', 'end': '2031-01-01'},
               {'id': 'Y2', 'start': '2031-01-01', 'end': '2032-01-01'},
               {'id': 'Y3', 'start': '2032-01-01', 'end': '2033-01-01'}]
    inputs = {'drawdown': ['0', '0', '0'], 'repayment': ['30', '30', '40'],
              'interest': ['10', '7', '4'], 'cfads': ['50', '44.4', '44']}
    observed = {'opening_debt': ['100', '70', '40'], 'closing_debt': ['70', '40', '0'],
                'debt_service': ['40', '37', '44'], 'dscr': ['1.25', '1.2', '1'],
                'covenant': ['PASS', 'PASS', 'FAIL']}
    def block(series, sheet):
        return {'period_ids': ['Y1', 'Y2', 'Y3'], 'currency': 'USD', 'amount_unit': 'millions',
                'series': series,
                'references': {m: [f"{sheet}!{col}{row}" for col in 'BCD']
                               for row, m in enumerate(series, 2)}}
    return {'schema_version': 1, 'model_id': 'synthetic-debt-review',
            'model_sha256': hashlib.sha256(b'fictional-model-identity-only-no-workbook').hexdigest(),
            'currency': 'USD', 'amount_unit': 'millions', 'periods': periods,
            'initial_debt': '100', 'required_final_debt': '0',
            'money_tolerance': '0.000001', 'ratio_tolerance': '0.000001',
            'covenant': {'operator': 'gte', 'threshold': '1.2'},
            'inputs': block(inputs, 'Inputs'), 'observed': block(observed, 'Model')}


def cases():
    good = clean()
    bad = deepcopy(good)
    # Consistent-looking wrong service and ratio are tested against separate raw inputs.
    bad['observed']['series']['debt_service'][0] = '50'
    bad['observed']['series']['dscr'][0] = '1'
    bad['observed']['series']['closing_debt'][0] = '75'
    bad['observed']['series']['opening_debt'][1] = '75'
    bad['observed']['series']['covenant'][2] = 'PASS'
    missing = deepcopy(good)
    missing['inputs']['series']['cfads'][1] = None
    missing['observed']['series']['dscr'][1] = None
    missing['observed']['series']['covenant'][1] = None
    return {'clean': good, 'planted-errors': bad, 'missing-data': missing}


if __name__ == '__main__':
    for name, data in cases().items():
        (Path(__file__).parent / (name + '.json')).write_text(json.dumps(data, indent=2) + '\n')
