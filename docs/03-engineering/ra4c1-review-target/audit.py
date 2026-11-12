"""Audit actual bounded, browser and final hosted outcomes; no strings-only PASS."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=HERE/'evidence'
DIGESTS={'404':'5705ac9e45e5118bc162bdece42f040a61360cf090b09500f7e9de5c89a9d256',
         '200':'c309bb1878103fdcb71200de644a685a52a04ab38d29325571cbc3a7f2bb4050'}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


python=[]
historical=[]
for folder in sorted(OUT.glob('python-*')):
    if not (folder/'receipt.json').exists():
        continue
    r=load(folder/'receipt.json')
    assert r['passed']==228 and r['baseline_app']==58 and r['new_app']==43 and r['original_reviewing']==127
    assert {c:d['target_digest'] for c,d in r['mapping'].items()}==DIGESTS
    assert r['mapping']['200']['native_h0'] is None and r['mapping']['404']['native_h0']
    if not all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in r['source_sha256'].items()):
        historical.append({'directory':folder.name,'head':r['head'],'reason':'completed_on_earlier_source_not_final'})
        continue
    python.append({'directory':folder.name,'head':r['head'],'python':r['python'],'passed':228,'mapping':r['mapping']})
assert len(python)==2,'Two source-frozen completed runtimes required'
browser=[]
for folder in sorted(OUT.glob('browser-*')):
    if not (folder/'receipt.json').exists():
        continue
    r=load(folder/'receipt.json')
    assertions=load(folder/'assertions.json')
    if any(not a['pass'] for a in assertions) or not any(a['id']=='url-input' for a in assertions):
        continue
    assert r['assertions']==r['passed']==123
    assert all(hashlib.sha256((folder/s['file']).read_bytes()).hexdigest()==s['sha256'] for s in r['screenshots'])
    if not all(hashlib.sha256((ROOT/'apps/operator_console'/p).read_bytes()).hexdigest()==h for p,h in r['sourceHashes'].items()):
        historical.append({'directory':folder.name,'head':r['sourceHead'],'reason':'completed_on_earlier_source_not_final'})
        continue
    assert all(a['pass'] for a in assertions if 'target' in a['id'] or 'history' in a['id'])
    browser.append({'directory':folder.name,'head':r['sourceHead'],'assertions':r['passed'],'screenshots':len(r['screenshots'])})
assert browser,'Completed real three-viewport target/source/history browser evidence required'
result={'state':'LOCAL_COMPLETE_FINAL_CI_PENDING','python':python,'browser':browser,'historical':historical,
        'real_human_decisions':0,'native_approvals':0,'share_grants':0,'human_gold':'0/26'}
if len(sys.argv)>1:
    folder=Path(sys.argv[1])
    r=load(folder/'receipt.json')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert r['run_head']==r['pr_head']==head and r['draft']
    assert r['accepted_main']=='9d138ba57e0b442b9dace1a2247d7aaa46ca38ac'
    assert r['merge_parents']==[r['accepted_main'],head] and r['merge_tree']==r['head_tree']
    assert len(r['jobs'])==4 and all(j['conclusion']=='success' and j['checkout']==r['merge_commit'] for j in r['jobs'])
    for job in r['jobs']:
        raw=(folder/job['log']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==job['log_sha256']
        if job['name']=='isolated-browser':
            continue
        collection=job['OWNER_RA3C_V2_ACTUAL_COLLECTION'][0]
        calls=job['OWNER_RA3C_V2_ACTUAL_CALL_REPORTS'][0]
        assert collection['primary_collected']==64 and collection['denials_collected']==54 and not collection['frozen_oracles_modified']
        assert calls['primary_count']==64 and calls['denial_count']==54 and not calls['setup_or_call_problems']
        assert len(calls['actual_call_reports'])==118 and set(calls['actual_call_reports'].values())=={'passed'}
        line=next(s for s in raw.decode().splitlines() if 'RA3D_D1D2_ACTUAL_RECEIPT=' in s)
        d1=json.loads(line.split('RA3D_D1D2_ACTUAL_RECEIPT=',1)[1])
        assert d1['collected']==d1['called']==d1['passed']==127
    assert len(r['artifacts'])==1
    a=r['artifacts'][0]
    assert hashlib.sha256((folder/a['file']).read_bytes()).hexdigest()==a['sha256']
    assert len(load(folder/'browser-summary-0.json'))==245
    result.update(state='FOUR_CI_GREEN_ENGINEERING_CANDIDATE_NOT_OWNER_FINAL_PASS',final_ci=r)
destination=(Path(sys.argv[1]) if len(sys.argv)>1 else HERE)/'ACCEPTANCE.json'
destination.write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8')+b'\n')
print(json.dumps({'state':result['state'],'python':python,'browser':browser,'destination':str(destination)},ensure_ascii=True))
