"""Source-matching local receipts and exact-head six hosted checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from verify_pg import verify

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE='558d183624a0a36d1f4eaf9d3d75af73b9c88547'


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


python_by_minor={}
historical=[]
for folder in sorted((HERE/'evidence').glob('python-*')):
    if not (folder/'receipt.json').exists():
        continue
    r=load(folder/'receipt.json')
    if not all(sha(ROOT/p)==h for p,h in r['source_sha256'].items()):
        continue
    assert r['passed']==324 and r['baseline_app']==58 and r['baseline_c1']==43 and r['new_app']==96
    assert r['actual_reviewing_receipt']['collected']==r['actual_reviewing_receipt']['called']==r['actual_reviewing_receipt']['passed']==127
    minor=r['python'].split()[0].split('.')[1]
    if minor in python_by_minor:
        historical.append(python_by_minor[minor])
    python_by_minor[minor]={'directory':folder.name,'head':r['head'],'python':r['python'],'passed':324}
python=[python_by_minor[k] for k in sorted(python_by_minor)]
assert len(python)==2
browser=[]
for folder in sorted((HERE/'evidence').glob('browser-*')):
    if (folder/'failure.txt').exists() or not (folder/'receipt.json').exists():
        continue
    r=load(folder/'receipt.json')
    if not all(sha(ROOT/'apps/operator_console'/p)==h for p,h in r['sourceHashes'].items()):
        continue
    a=load(folder/'assertions.json')
    assert len(a)==r['assertions']==r['passed']==75 and all(v['pass'] for v in a)
    assert len(r['screenshots'])==24 and all(sha(folder/s['file'])==s['sha256'] for s in r['screenshots'])
    assert not r['serverError']
    raw=load(folder/'raw-cdp.json')
    assert len([x for x in raw['network'] if x['request']['method']=='POST'])==21
    browser.append({'directory':folder.name,'head':r['sourceHead'],'assertions':75,'screenshots':24})
assert browser
result={'state':'LOCAL_COMPLETE_FINAL_CI_PENDING','python':python,'browser':browser,'same_source_older_main':historical,
        'real_decisions':0,'share_grants':0,'human_gold':'0/26'}
if len(sys.argv)>1:
    normal_dir,pg_dir=map(Path,sys.argv[1:])
    normal,pg=load(normal_dir/'receipt.json'),load(pg_dir/'receipt.json')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    def tree(ref):
        raw=subprocess.check_output(['git','ls-tree','-r','-z',ref],cwd=ROOT)
        return {r.split(b'\t',1)[1].decode():r.split(b'\t',1)[0].decode().split()[::2]
                for r in raw.split(b'\0') if r}
    base,current=tree(BASE),tree(head)
    allowed=('apps/operator_console/','tests/operator_console/',
             'docs/03-engineering/ra4c2-review-proposal/')
    assert all(current.get(p)==v for p,v in base.items() if not p.startswith(allowed))
    assert all(p in base or p.startswith(allowed) for p in current)
    assert all(current[p]==base[p] for p in ('tests/operator_console/test_console.py',
                                            'tests/operator_console/test_targets.py'))
    seal=load(HERE/'SOURCE-SEAL.json')
    assert seal['apps_and_tests']=={p:v for p,v in current.items() if p.startswith(allowed[:2])}
    assert all(p['head']==seal['head'] for p in python)
    for folder,r,count in ((normal_dir,normal,4),(pg_dir,pg,2)):
        assert r['run_head']==r['pr_head']==head and r['accepted_main']==BASE and r['draft']
        assert r['merge_parents']==[BASE,head] and r['head_tree']==r['merge_tree']==normal['merge_tree']
        assert len(r['jobs'])==count and all(j['conclusion']=='success' and j['checkout']==normal['merge_commit'] and sha(folder/j['log'])==j['log_sha256'] for j in r['jobs'])
        for a in r['artifacts']:
            assert sha(folder/a['file'])==a['sha256']
    for j in normal['jobs']:
        if j['name']=='isolated-browser':
            continue
        c=j['OWNER_RA3C_V2_ACTUAL_COLLECTION'][0]
        r=j['OWNER_RA3C_V2_ACTUAL_CALL_REPORTS'][0]
        assert c['primary_collected']==64 and c['denials_collected']==54 and not c['frozen_oracles_modified']
        assert r['primary_count']==64 and r['denial_count']==54 and not r['setup_or_call_problems']
        assert len(r['actual_call_reports'])==118 and set(r['actual_call_reports'].values())=={'passed'}
        lines=(normal_dir/j['log']).read_text(encoding='utf-8').splitlines()
        receipt=json.loads(next(s for s in lines if 'RA3D_D1D2_ACTUAL_RECEIPT=' in s).split('RA3D_D1D2_ACTUAL_RECEIPT=',1)[1])
        assert receipt['collected']==receipt['called']==receipt['passed']==127
    assert len(normal['artifacts'])==1 and len(pg['artifacts'])==2
    assert len(load(normal_dir/'browser-summary-0.json'))==245
    pg_calls=verify(pg_dir,head,BASE,normal['merge_commit'])
    assert len(pg_calls)==2 and all(p['p1_v1']==54 and p['p1_v2_compat']==54 and p['p1_pure']==11
                                  and p['p2a_pure']==14 and p['p2a_pg']==86 for p in pg_calls)
    result.update(state='SIX_CI_GREEN_ENGINEERING_CANDIDATE_NOT_OWNER_FINAL_PASS',final_sha=head,normal_ci=normal,pg_ci=pg,pg_calls=pg_calls)
destination=(Path(sys.argv[1]) if len(sys.argv)>1 else HERE)/'ACCEPTANCE.json'
destination.write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode()+b'\n')
print(json.dumps({'state':result['state'],'python':python,'browser':browser,'destination':str(destination)}))
