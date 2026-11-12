"""Summarize completed evidence without turning a missing CI gate green."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=HERE/'evidence'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def pytest_counts(path):
    nodes=ET.parse(path).getroot().findall('.//testcase')
    return {'tests':len(nodes),'failed':sum(n.find('failure') is not None for n in nodes),
            'errors':sum(n.find('error') is not None for n in nodes),
            'skipped':sum(n.find('skipped') is not None for n in nodes)}


def qa(content):
    result={}
    for label in ('OWNER_RA3C_V2_ACTUAL_COLLECTION','OWNER_RA3C_V2_ACTUAL_CALL_REPORTS'):
        values=[json.loads(line.split(label+' ',1)[1].strip()) for line in content.splitlines() if label+' ' in line]
        assert len(values)==1,(label,len(values))
        result[label]=values[0]
    collection=result['OWNER_RA3C_V2_ACTUAL_COLLECTION']
    calls=result['OWNER_RA3C_V2_ACTUAL_CALL_REPORTS']
    assert collection['primary_collected']==64 and collection['denials_collected']==54
    assert collection['frozen_oracles_modified'] is False
    assert calls['primary_count']==64 and calls['denial_count']==54 and not calls['setup_or_call_problems']
    assert len(calls['actual_call_reports'])==118 and set(calls['actual_call_reports'].values())=={'passed'}
    return {'primary_actual':64,'denials_actual':54,'passed_actual':118,
            'frozen_oracles_modified':False,'source_sha256':calls['source_sha256']}


histories={}
for folder in sorted(OUT.glob('historical-replay-*')):
    if not (folder/'receipt.json').exists():
        continue
    r=load(folder/'receipt.json')
    history=pytest_counts(folder/'tests.xml')
    assert history=={'tests':64,'failed':53,'errors':0,'skipped':0},history
    assert r['failure_messages']=={'vrae.reporting.common.ReportError: REPORT_UNSUPPORTED_PROSE':52,
                                   'vrae.reporting.common.ReportError: REPORT_GUARD_NOT_VALIDATED':1}
    histories[folder.name.rsplit('-',1)[-1]]={'directory':folder.name,'head':r['head'],
                                           'counts':dict(history,passed=11),'messages':r['failure_messages']}
assert set(histories)=={'11','13'},'Need both actual V1 replays with accepted adapter'
regress=[]
for name in ('regress-20261112T134051-860215-11','regress-20261112T134118-775985-13'):
    folder=OUT/name
    result=load(folder/'results.json')
    assert len(result['rows'])==24 and all(r['actual_exit']==r['expected_exit'] for r in result['rows'])
    counts=pytest_counts(folder/'full.xml')
    assert counts=={'tests':2144,'failed':0,'errors':0,'skipped':25},counts
    invalid_history=pytest_counts(folder/'historical.xml')
    assert invalid_history=={'tests':64,'failed':0,'errors':64,'skipped':0}
    assert len(list((folder/'sealed-native').glob('*.json')))==8
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in result['source_sha256'].items())
    regress.append({'directory':name,'python':result['python'],'start_head':result['start_head'],
        'full':dict(counts,passed=counts['tests']-counts['skipped']),
        'historical_v1':histories[name.rsplit('-',1)[-1]],
        'prior_invalid_history':{'directory':name,'counts':invalid_history,'counted_as_red':False},
        'qa_v2':qa((folder/'full.log').read_text(encoding='utf-8')),
        'historical_commands':19,'sealed_native_cases':8,'all_source_hashes_unchanged':True})

browser=[]
for folder in sorted(OUT.glob('browser-*')):
    if not (folder/'receipt.json').exists():
        continue
    receipt=load(folder/'receipt.json')
    if not receipt.get('sourceHashes') or receipt['passed']!=75:
        continue
    records=load(folder/'assertions.json')
    assert len(records)==75 and all(r['pass'] for r in records)
    assert all(hashlib.sha256((folder/s['file']).read_bytes()).hexdigest()==s['sha256'] for s in receipt['screenshots'])
    assert all(hashlib.sha256((ROOT/'apps/operator_console'/p).read_bytes()).hexdigest()==h for p,h in receipt['sourceHashes'].items())
    browser.append({'directory':folder.name,'source_head':receipt['sourceHead'],
        'product':receipt['version']['product'],'assertions':75,'screenshots':len(receipt['screenshots']),
        'zero_external_requests':next(r['pass'] for r in records if r['id']=='zero-external-network'),
        'all_app_source_hashes_unchanged':True})
assert browser,'No completed source-bound browser run'
postmerge=[]
for folder in sorted(OUT.glob('postmerge-*')):
    if not (folder/'receipt.json').exists():
        continue
    r=load(folder/'receipt.json')
    assert r['accepted_main']=='225ded57add21680171cfaecac9f89df6b1af155'
    counts=pytest_counts(folder/'tests.xml')
    assert counts['failed']==counts['errors']==counts['skipped']==0
    assert counts['tests']>=62 and r['pytest_exit']==0
    assert [x['issues'] for x in r['native']]==[1,0]
    postmerge.append({'directory':folder.name,'head':r['head'],'python':r['python'],
                      'tests':counts,'native_cases':2,'imports_reviewing_for_ui':False})
assert len(postmerge)==2,'Need both real postmerge runtimes'
ci=load(OUT/'hosted-43227963343-20261112T134426/receipt.json')
for job in ci['jobs']:
    assert job['checkout']==ci['merge_commit']
    raw=(OUT/'hosted-43227963343-20261112T134426'/job['log']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==job['log_sha256']
    if job['name'].startswith('contracts-domain'):
        qa(raw.decode('utf-8'))
assert ci['merge_parents']==[ci['accepted_main'],ci['run_head']]
summary={'state':'LOCAL_EVIDENCE_READY_FINAL_HOSTED_CI_PENDING','application_source':ci['run_head'],
    'regressions':regress,'postmerge':postmerge,'browser':browser,'historical_pre_exception_ci':{
        'run_id':ci['run_id'],'head':ci['run_head'],'checkout':ci['merge_commit'],
        'parents':ci['merge_parents'],'successes':sum(j['conclusion']=='success' for j in ci['jobs']),
        'required':4,'missing_apps_source_in_http_image':True},
    'copy_exception':'https://github.com/gloweaseco-leo/VRAE/pull/61#issuecomment-6825546180',
    'human_gold':'0/26 - NOT EVALUABLE','real_approval':'NOT_IMPLEMENTED','customer_share':'NO_GO'}
if len(sys.argv)>1:
    final_path=Path(sys.argv[1])
    final=load(final_path/'receipt.json')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert final['run_status']=='completed' and final['run_head']==final['pr_head']==head and final['draft']
    assert final['accepted_main']=='225ded57add21680171cfaecac9f89df6b1af155'
    assert final['merge_parents']==[final['accepted_main'],head]
    assert final['head_tree']==final['merge_tree']
    assert len(final['jobs'])==4 and all(j['conclusion']=='success' for j in final['jobs'])
    for job in final['jobs']:
        assert job['checkout']==final['merge_commit']
        raw=(final_path/job['log']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==job['log_sha256']
        if job['name']!='isolated-browser':
            qa(raw.decode('utf-8'))
    assert len(final['artifacts'])==1
    artifact=final['artifacts'][0]
    assert hashlib.sha256((final_path/artifact['file']).read_bytes()).hexdigest()==artifact['sha256']
    security=load(final_path/'browser-summary-0.json')
    assert len(security)==245
    names={row['name'] for row in security}
    controls={'kernel-control','kernel-deny','sandbox'}
    cases={'readonly','writes','private','resources','channels','escape','storage','redirect',
           'redirect_private','rebinding','infinite','memory','revocation','crash','sigkill','worker_kill'}
    assert controls <= names and {c+'-worker' for c in cases} <= names
    summary['state']='ENGINEERING_CANDIDATE_FOUR_CI_GREEN_NOT_OWNER_FINAL_PASS'
    summary['final_ci']={'head':head,'main':final['accepted_main'],'checkout':final['merge_commit'],
                         'parents':final['merge_parents'],'run_id':final['run_id'],'successes':4,
                         'jobs':[{k:j[k] for k in ('name','job_id','url','log_sha256')} for j in final['jobs']],
                         'browser_security_commands':245,'worker_cases':sorted(cases),'artifact':artifact}
destination=(Path(sys.argv[1]) if len(sys.argv)>1 else HERE)/'ACCEPTANCE.json'
destination.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
