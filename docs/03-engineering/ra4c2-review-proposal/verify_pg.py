"""Reuse the now accepted main PG auditor, without modifying QA or opening DBs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def verify(folder, head, main, merge):
    folder=Path(folder).resolve()
    assert folder.is_relative_to(HERE/'evidence')
    shutil.copyfile(folder/'jobs.json',folder/'pg-jobs.json')
    shutil.copyfile(folder/'artifacts.json',folder/'pg-artifacts.json')
    for version in ('3.11','3.13'):
        shutil.copyfile(folder/('ra4a-pg16-'+version+'.zip'),folder/('pg-'+version+'.zip'))
    driver=HERE/'runtime/pg-driver'
    env=dict(os.environ,PYTHONPATH=str(driver)+os.pathsep+str(ROOT),PYTHONDONTWRITEBYTECODE='1')
    command=[sys.executable,'-B',str(ROOT/'docs/03-engineering/ra4a-p2a/audit_hosted_pg.py'),
             str(folder),head,main,merge]
    result=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (folder/'accepted-main-pg-audit.log').write_bytes(result.stdout)
    if result.returncode:
        print(result.stdout.decode('utf-8',errors='replace'))
        raise RuntimeError('ACCEPTED_MAIN_PG_AUDIT_FAILED')
    return json.loads((folder/'PG_P2A_ACTUAL_RECEIPT.json').read_text(encoding='utf-8'))


if __name__=='__main__':
    print(json.dumps(verify(*sys.argv[1:]),ensure_ascii=True))
