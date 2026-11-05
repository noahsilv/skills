#!/usr/bin/env python3
"""Synthetic source/ledger/brief/gate composition; no model or live service calls."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'skills/evidence-brief/examples/financing'

def dump(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)

def fixture_checks(root,brief):
    mapping=json.loads((root/'claim-map.json').read_text())
    results=[]
    for row in mapping:
        source=(root/row['source']).read_text()
        results.append({'claim':row['id'],'passed':row['sentence'] in brief and row['quote'] in source,
                        'scope':'Exact authored fixture sentence and source quote containment only'})
    return {'passed':all(x['passed'] for x in results),'checks':results,
            'semantic_verification':'NOT_PERFORMED_BY_THIS_CHECKER'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('out',type=Path);p.add_argument('--check-only',action='store_true');a=p.parse_args()
    if a.check_only:
        result=fixture_checks(a.out,(a.out/'brief.md').read_text());print(json.dumps(result));return 0 if result['passed'] else 1
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('committee-record.md','concept-deck.md','auto-summary.md'):shutil.copyfile(SOURCES/name,a.out/name)
    subprocess.run([sys.executable,str(ROOT/'examples/financing_evidence_demo.py'),str(a.out/'ledger')],check=True,capture_output=True,text=True,timeout=30)
    rows=[
      ('decision','Only further diligence within the existing advisory budget was authorized; no facility amount or tenor was approved. [DISCUSSION 02:10]','committee-record.md','The only decision today is to authorize further diligence within the existing advisory budget. We do not approve any facility amount or tenor.'),
      ('request','The sponsor requested EUR42 million over seven years. [DECK Slide 3]','concept-deck.md','Requested refinancing is 42 million euros with a seven-year tenor.'),
      ('lender','The lender could consider up to EUR36 million over six years, subject to the reconciled debt schedule; this is not a commitment. [DISCUSSION 00:55]','committee-record.md','We could consider up to 36 million euros over six years if the reconciled debt schedule supports it. This is not a credit approval or commitment to lend.'),
      ('savings-call','The later call estimated EUR1.1 million annual cash-interest savings at current floating rates, excluding arrangement fees. [DISCUSSION 01:35]','committee-record.md','We estimate the refinancing could reduce annual cash interest by about 1.1 million euros. That estimate uses current floating rates and excludes arrangement fees.'),
      ('savings-deck','The earlier deck illustrated EUR1.4 million using May-model rates, excluding fees; these bases have not been reconciled. [DECK Slide 4]','concept-deck.md','Illustrative annual cash-interest saving is 1.4 million euros using the rates in the sponsor\'s May model. Fees are excluded.'),
      ('owner','Petra owns the debt schedule; delivery depends on two servicer balances and no date is promised. [DISCUSSION 02:55]','committee-record.md','I will send the reconciled debt schedule. I cannot promise a date until the servicer confirms two balances.'),
      ('deadline','No lender term-sheet deadline was agreed. [DISCUSSION 03:30]','committee-record.md','We have no term-sheet deadline today.')]
    dump(a.out/'claim-map.json',[{'id':ident,'sentence':sentence,'source':source,'quote':quote} for ident,sentence,source,quote in rows])
    (a.out/'brief.md').write_text('# Authored synthetic fixture brief\n\n'+'\n\n'.join(row[1] for row in rows)+'\n')
    shutil.copyfile(__file__,a.out/'checker.py')
    checked=subprocess.run([sys.executable,str(a.out/'checker.py'),str(a.out),'--check-only'],check=True,capture_output=True,text=True,timeout=10)
    (a.out/'check-log.json').write_text(checked.stdout)
    spec=importlib.util.spec_from_file_location('context_demo_gate',ROOT/'skills/artifact-quality-gate/scripts/gate.py')
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    files=['committee-record.md','concept-deck.md','auto-summary.md','brief.md','claim-map.json','ledger/ledger-pending.json']
    artifacts=[{'id':'a'+str(i),'path':name} for i,name in enumerate(files)]
    run=gate.initialize({'schema_version':1,'artifacts':artifacts,'checks':[{'id':'fixture-coverage','artifact_ids':[x['id'] for x in artifacts],
          'requirement':'Exact synthetic fixture sentence/quote coverage; not general semantic verification.','kind':'file_check'}]},a.out)
    gate.write_new(a.out/'run.json',run);run,fp=gate.load_json(a.out/'run.json')
    empty=gate.aggregate(run,fp,[],a.out)
    record=gate.make_record(run,fp,{'schema_version':1,'check_id':'fixture-coverage','status':'pass','summary':'Executed exact authored-fixture coverage checker.',
                                  'evidence':[{'role':'checker','path':'checker.py'},{'role':'log','path':'check-log.json'}]},a.out)
    gate.write_new(a.out/'check-record.json',record)
    report=gate.aggregate(run,fp,[record],a.out);gate.write_new(a.out/'report.json',report)
    bad=fixture_checks(a.out,(a.out/'auto-summary.md').read_text())
    with (a.out/'committee-record.md').open('a') as f:f.write('\nSynthetic later amendment: decision deferred.\n')
    try:gate.aggregate(run,fp,[record],a.out)
    except gate.ValidationError as exc:stale=str(exc)
    else:raise AssertionError('Changed source was not rejected')
    assert empty['verdict']=='INCOMPLETE' and report['verdict']=='ATTESTED' and not bad['passed']
    result={'synthetic':True,'brief_origin':'authored_synthetic_fixture','ledger_acceptance':'pending',
            'missing_record':empty['verdict'],'completed_fixture_gate':report['verdict'],'incorrect_recap_rejected':not bad['passed'],
            'changed_source_rejected':stale,'semantic_verification':'NOT_PERFORMED_BY_DETERMINISTIC_CHECKER',
            'notice':'The copied source is intentionally changed at the end; the prior successful gate is now stale. No live work or model-performance claim.'}
    dump(a.out/'results.json',result);print(json.dumps(result));return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,subprocess.SubprocessError,AssertionError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(2)
