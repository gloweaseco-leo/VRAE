"""Invoke unchanged frozen V1 with the already accepted legacy transport."""
from collections import Counter
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
out=HERE/'evidence'/('historical-replay-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S-%f')+'-'+str(sys.version_info.minor))
out.mkdir(parents=True)
adapter=ROOT/'docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/legacy_transport.py'
suite=ROOT/'tests/reporting/test_ra3c_independent_acceptance.py'
source_hash=hashlib.sha256(suite.read_bytes()).hexdigest()
env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',
    VRAE_RA3C_QA_ADAPTER_PATH=str(adapter))
env.pop('PYTEST_ADDOPTS',None)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
argv=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider','-o','addopts=-ra',str(suite),
      '--basetemp='+str(out/'runtime/pytest'),'--junitxml='+str(out/'tests.xml')]
with (out/'tests.log').open('wb') as log:
    result=subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
nodes=ET.parse(out/'tests.xml').getroot().findall('.//testcase')
counts=Counter('error' if n.find('error') is not None else 'failed' if n.find('failure') is not None
               else 'skipped' if n.find('skipped') is not None else 'passed' for n in nodes)
messages=Counter(n.find('failure').get('message') for n in nodes if n.find('failure') is not None)
receipt={'python':sys.version,'head':head,'argv':argv,'adapter':str(adapter.relative_to(ROOT)),
    'adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),'suite_sha256':source_hash,
    'actual_exit':result.returncode,'counts':dict(counts),'failure_messages':dict(messages)}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
assert result.returncode==1 and counts=={'passed':11,'failed':53},counts
assert messages=={'vrae.reporting.common.ReportError: REPORT_UNSUPPORTED_PROSE':52,
                   'vrae.reporting.common.ReportError: REPORT_GUARD_NOT_VALIDATED':1},messages
assert hashlib.sha256(suite.read_bytes()).hexdigest()==source_hash
assert not subprocess.check_output(['git','diff','--name-only','HEAD','--','vrae','contracts','tests',
    'docs/03-engineering/ra3c-independent-qa'],cwd=ROOT).strip()
print(json.dumps({'out':str(out),'head':head,'counts':dict(counts),'failure_messages':dict(messages)}))
