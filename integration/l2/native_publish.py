"""Publish only the fixed C1/C2 component fixture, never arbitrary task data."""
import json
from pathlib import Path
import re
import sqlite3

from vrae.l2.report import DeepReport, sha
from .native_component import source as native_source


def publish(label,public,*,input_label=None):
    from .publish import report_md, blueprint_md, ROOT
    native_label=input_label or label+'-native'
    assert re.fullmatch('[a-z0-9-]{3,60}',native_label)
    root=ROOT/'integration/l2/.runtime'/native_label
    run=json.loads((root/'run.json').read_bytes())
    browser=json.loads((root/'browser.json').read_bytes())
    source=native_source()
    assert run['result']['pass'] and run['source_bundle_sha256']==source.expected
    assert run['runtime']['mode']=='L2_NATIVE_C1_C2_CONTROLLED_COMPONENT_NOT_APP202_E2E'
    assert browser['kind']=='L2_NATIVE_C2_COMPONENT_BROWSER_NOT_APP202_E2E'
    assert run['formal_human_reviews_claimed']==run['actual_external_customers']==0
    assert browser['formalHumanReviewsClaimed']==browser['realExternalCustomers']==0
    assert browser['records'] and all(r['pass'] for r in browser['records']) and not browser['exceptions']
    assert len(run['restarts'])==1 and all(run['restarts'][0].values())
    for name in ('process-cleanup.json','browser-cleanup.json'):
        assert all(json.loads((root/name).read_bytes()).values())
    with sqlite3.connect('file:'+str((root/'l2.sqlite').as_posix())+'?mode=ro',uri=True) as c:
        versions=[]
        for raw,pin,source_pin in c.execute('SELECT payload,display_hash,source_hash FROM versions ORDER BY version'):
            assert sha(raw)==pin and source_pin==source.expected
            view=DeepReport(raw,source_pin)
            source.validate(view.document)
            versions.append(view)
        decisions=[json.loads(r[0]) for r in c.execute('SELECT receipt FROM decisions ORDER BY seq')]
    assert len(versions)==len(decisions)==2
    assert all(x['scope']=='CONTROLLED_REVIEW_SIMULATION' and not x['formal_human_review']
               and not x['external_delivery'] for x in decisions)
    latest=versions[-1]
    assert {f['native_rule_id'] for f in latest.document['findings']}=={
        'IND-SELECTION','IND-SPEC','IND-DUTY','IND-FIT','IND-PROOF','IND-RFQ'}
    assert 'MP25' not in latest.payload.decode()
    blueprint=blueprint_md(latest).decode().replace('# 工业泵网站 Rebuild 改造蓝图','# P40 / V25 工业采购 Rebuild 改造蓝图',1).encode()
    files={'report-version-2.json':latest.payload,
        'versioned-decisions.json':json.dumps(decisions,ensure_ascii=False,indent=2).encode(),
        'l2-deep-report.md':b'> C1/C2 native component proof, NOT APP202/Worker E2E.\n\n'+report_md(latest),
        'l2-rebuild-blueprint.md':b'> C1/C2 native component proof, NOT APP202/Worker E2E.\n\n'+blueprint}
    for name in ('run.json','browser.json','process-cleanup.json','browser-cleanup.json'):
        files[name]=(root/name).read_bytes()
    for shot in browser['shots']:
        assert re.fullmatch('[a-z0-9-]+\\.png',shot['file'])
        raw=(root/shot['file']).read_bytes()
        assert sha(raw)==shot['sha256']
        files[shot['file']]=raw
    pages={}
    for name in ('l2-deep-report.pdf','l2-rebuild-blueprint.pdf'):
        raw=(root/name).read_bytes()
        record=next(r for r in browser['records'] if r['name']==name+'-actual-multipage-A4')
        assert record['metadata']['sha256']==sha(raw) and record['metadata']['pages']>1
        files[name]=raw
        pages[name]=record['metadata']['pages']
    target=Path(public)/'native'
    target.mkdir(exist_ok=False)
    manifest={}
    for name,raw in files.items():
        text=raw.decode('utf-8',errors='ignore')
        assert '-----BEGIN PRIVATE KEY' not in text and 'Bearer ' not in text
        assert not re.search(r'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',text)
        (target/name).write_bytes(raw)
        manifest[name]={'bytes':len(raw),'sha256':sha(raw)}
    return {'scope':'NATIVE_C1_C2_COMPONENT_NOT_APP202_WORKER_E2E','files':manifest,
        'producer':latest.document['producer'],'source_sha256':source.expected,
        'report_id':latest.version['report_id'],'report_version':latest.version['version'],
        'report_sha256':latest.display_hash,'content_hash':latest.version['content_hash'],
        'native_assessments':len(latest.findings),'source_facts':len(source.read().document['evidence'])-len(source._pack.document['evidence']),
        'blueprints':len(latest.document['blueprint']),'actual_pdf_pages':pages,
        'formal_human_reviews':0,'external_customers':0}
