"""Source-matching local receipts and exact-head six hosted checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE='cf11278ba4c9b62b3645cdbd6fd2cd8bb2f1838b'


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


python=[]
for folder in sorted((HERE/'evidence').glob('python-*')):
    if not (folder/'receipt.json').exists():
        continue
    r=load(folder/'receipt.json')
    if not all(sha(ROOT/p)==h for p,h in r['source_sha256'].items()):
        continue
    assert r['passed']==324 and r['baseline_app']==58 and r['baseline_c1']==43 and r['new_app']==96
    assert r['actual_reviewing_receipt']['collected']==r['actual_reviewing_receipt']['called']==r['actual_reviewing_receipt']['passed']==127
    python.append({'directory':folder.name,'head':r['head'],'python':r['python'],'passed':324})
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
result={'state':'LOCAL_COMPLETE_FINAL_CI_PENDING','python':python,'browser':browser,
        'real_decisions':0,'share_grants':0,'human_gold':'0/26'}
if len(sys.argv)>1:
    normal_dir,pg_dir=map(Path,sys.argv[1:])
    normal,pg=load(normal_dir/'receipt.json'),load(pg_dir/'receipt.json')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
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
    pg_calls=[]
    for a in pg['artifacts']:
        with zipfile.ZipFile(pg_dir/a['file']) as z:
            for name,count in [('pure.xml',54),('postgres.xml',11)]:
                member=next(n for n in z.namelist() if n.endswith('/'+name))
                nodes=ET.fromstring(z.read(member)).findall('.//testcase')
                assert len(nodes)==count and not any(n.find(k) is not None for n in nodes for k in ('failure','error','skipped'))
            source=json.loads(z.read(next(n for n in z.namelist() if n.endswith('/source-manifest.json'))))
            assert source['actual_git_head']==normal['merge_commit']
            commands=json.loads(z.read(next(n for n in z.namelist() if n.endswith('/commands.json'))))
            assert len(commands['commands'])==6 and all(c['exit']==0 for c in commands['commands'])
            restore=json.loads(z.read(next(n for n in z.namelist() if n.endswith('/backup-restore.json'))))
            assert restore['source_data_sha256']==restore['restored_data_sha256']
            assert restore['data_equal_before_and_after_idempotent_replay'] and restore['restored_tenant_isolation_and_write_denial']
            pg_calls.append({'artifact':a['name'],'pure':54,'pg':11,'restore_equal':True})
    result.update(state='SIX_CI_GREEN_ENGINEERING_CANDIDATE_NOT_OWNER_FINAL_PASS',final_sha=head,normal_ci=normal,pg_ci=pg,pg_calls=pg_calls)
destination=(Path(sys.argv[1]) if len(sys.argv)>1 else HERE)/'ACCEPTANCE.json'
destination.write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode()+b'\n')
print(json.dumps({'state':result['state'],'python':python,'browser':browser,'destination':str(destination)}))
