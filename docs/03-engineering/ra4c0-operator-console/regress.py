"""Authorized-output-only full gates + unchanged sealed historical replays."""
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(ROOT))
out = HERE/'evidence'/('regress-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S-%f')+'-'+str(sys.version_info.minor))
out.mkdir(parents=True)
env = dict(os.environ,PYTHONPATH=str(ROOT),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',
           RUFF_CACHE_DIR=str(out/'runtime/ruff'),MYPY_CACHE_DIR=str(out/'runtime/mypy'))
rows=[]
start_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
source_files=[p for folder in ('vrae','contracts','tests','apps/operator_console')
              for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
start_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}


def run(name,args,expected=0):
    argv=[sys.executable,*args]
    with (out/(name+'.log')).open('wb') as log:
        r=subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    rows.append({'name':name,'argv':argv,'actual_exit':r.returncode,'expected_exit':expected})
    (out/'results.json').write_text(json.dumps({'python':sys.version,'start_head':start_head,
        'source_sha256':start_hashes,'rows':rows},indent=2)+'\n',encoding='utf-8')
    print(name,r.returncode,'expected',expected,flush=True)
    if r.returncode != expected:
        raise SystemExit('FAILED '+name+' (raw log retained)')


run('ruff',['-m','ruff','check','vrae','tests','apps/operator_console','--select','E4,E7,E9,F'])
run('mypy',['-m','mypy','vrae'])
run('full',['-m','pytest','-q','-s','-p','no:cacheprovider','--junitxml='+str(out/'full.xml')])
run('historical-v1',['-m','pytest','-q','-p','no:cacheprovider','-o','addopts=-ra',
    'tests/reporting/test_ra3c_independent_acceptance.py','--junitxml='+str(out/'historical.xml')],1)
run('pip-check',['-m','pip','check'])
for i,stage in enumerate(('ra2a','ra2b0','ra2b1','ra2b2','ra2b3','ra2b4','ra2b5','ra2b6',
    'ra2b6_execution','ra2c0','ra2c1','ra2c2','ra2c3','ra2d0','ra2d1','ra3a','ra3b')):
    run(f'replay-{i:02}-{stage}',[f'scripts/verify_{stage}.py'])
run('gold-simulated',['scripts/verify_ra2d1.py','--reviews','docs/03-engineering/ra2d1-review/SIMULATED_NOT_HUMAN_GOLD.json'])
run('gold-forged-rejection',['scripts/verify_ra2d1.py','--reviews','docs/03-engineering/ra2d1-review/negative-forged-gold.json'],1)
spec=importlib.util.spec_from_file_location('accepted_ra3c',ROOT/'scripts/verify_ra3c.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
native=out/'sealed-native'
native.mkdir()
for case in module.CASES:
    draft=module.replay(case)
    (native/(str(case)+'.html')).write_bytes(draft.html_bytes)
    (native/(str(case)+'.json')).write_text(json.dumps(draft.document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==value for p,value in start_hashes.items())
print('ALL GATES MATCHED; source hashes unchanged; historical V1 remains RED; Gold remains 0/26',out,flush=True)
