"""Actual post-main application/P1 regression; does not replace full hosted gates."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
out=HERE/'evidence'/('postmerge-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S-%f')+'-'+str(sys.version_info.minor))
out.mkdir(parents=True)
env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
main=subprocess.check_output(['git','rev-parse','origin/main'],cwd=ROOT,text=True).strip()
argv=[sys.executable,'-m','pytest','-q','-s','-p','no:cacheprovider',
      'tests/operator_console','tests/reviewing/test_strict_metadata.py',
      '--basetemp='+str(out/'runtime/pytest'),'--junitxml='+str(out/'tests.xml')]
with (out/'tests.log').open('wb') as log:
    result=subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
assert result.returncode==0,'postmerge pytest failed; raw log retained'
from apps.operator_console.fixtures import make_fixture
service,context=make_fixture()
native=[]
for case in ('404','200'):
    task=service.detail(context,'task-'+case)
    _,dossier=service.review(context,task['task_id'],1,task['report_pins']['expected_draft_ref'])
    path=out/(case+'.json')
    path.write_text(json.dumps(dossier,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    native.append({'case':case,'draft_ref':dossier['document']['draft_ref'],
                   'issues':len(dossier['document']['issues']),
                   'html_sha256':dossier['document']['html_sha256'],
                   'saved_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
summary={'python':sys.version,'head':head,'accepted_main':main,'argv':argv,
         'pytest_exit':result.returncode,'native':native,'imports_reviewing_for_ui':False}
(out/'receipt.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'out':str(out),'head':head,'main':main,'pytest_exit':result.returncode}))
