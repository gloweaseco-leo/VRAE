"""Bounded current-source app+127 reviewing regressions, no foreign outputs."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
out=HERE/'evidence'/('python-'+str(sys.version_info.minor)+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
out.mkdir(parents=True)
env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',
    RUFF_CACHE_DIR=str(out/'runtime/ruff'))
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
files=[p for folder in ('apps/operator_console','vrae/reviewing','tests/operator_console','tests/reviewing')
       for p in (ROOT/folder).rglob('*') if p.suffix in ('.py','.json','.css') and '__pycache__' not in p.parts]
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
commands=[('ruff',['-m','ruff','check','apps/operator_console','vrae','tests','--select','E4,E7,E9,F']),
    ('bounded',['-m','pytest','-q','-s','-p','no:cacheprovider','tests/operator_console','tests/reviewing',
                '--basetemp='+str(out/'runtime/pytest'),'--junitxml='+str(out/'tests.xml')])]
rows=[]
for name,args in commands:
    argv=[sys.executable,*args]
    with (out/(name+'.log')).open('wb') as log:
        r=subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    rows.append({'name':name,'argv':argv,'exit':r.returncode})
    assert r.returncode==0,(name,r.returncode)
nodes=ET.parse(out/'tests.xml').getroot().findall('.//testcase')
assert len(nodes)==228 and not any(n.find('failure') is not None or n.find('error') is not None
                                 or n.find('skipped') is not None for n in nodes)
reporting=(out/'bounded.log').read_text(encoding='utf-8')
line=next(s for s in reporting.splitlines() if 'RA3D_D1D2_ACTUAL_RECEIPT=' in s)
d1=json.loads(line.split('RA3D_D1D2_ACTUAL_RECEIPT=',1)[1])
assert d1['collected']==d1['called']==d1['passed']==127
assert d1['real_human_decisions']==d1['native_approvals']==d1['share_grants']==0
from apps.operator_console.fixtures import make_fixture
service,context=make_fixture()
mapping={}
for case in ('404','200'):
    task=service.detail(context,'task-'+case)
    _,d=service.review(context,task['task_id'],1,task['report_pins']['expected_draft_ref'])
    v=d['review_target']
    (out/(case+'-target.json')).write_bytes(json.dumps(v,ensure_ascii=False,indent=2).encode('utf-8'))
    mapping[case]={'target_digest':v['target_digest'],'native_h0':v['native_h0'],
                   'html_sha256':v['target']['html_sha256'],'claims':len(v['target']['claims'])}
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
result={'head':head,'python':sys.version,'commands':rows,'passed':228,'baseline_app':58,
        'new_app':43,'original_reviewing':127,'mapping':mapping,'source_sha256':hashes,
        'actual_reviewing_receipt':d1,'real_decisions':0,'share_grants':0}
(out/'receipt.json').write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8'))
print(json.dumps({'out':str(out),'head':head,'passed':228,'mapping':mapping}))
