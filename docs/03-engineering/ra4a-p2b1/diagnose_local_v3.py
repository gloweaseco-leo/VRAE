"""Bounded actual lab diagnostics; retain originals privately, never print secrets."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import psycopg

for root in (ROOT,ROOT.parent/'ra4a-p2b1-v3-py311'):
    state_path=root/'infra/ra4a/.venv/lab-state.json'
    s=json.loads(state_path.read_text())
    secrets=[s['admin_password'],*s['runtime_passwords'].values()]
    assert re.fullmatch(r'vrae-ra4a-p1-[0-9a-f]{12}',s['container'])
    private=root/'infra/ra4a/.venv/v3-local-failure-originals'
    out=root/'docs/03-engineering/ra4a-p2b1/local-v3-diagnostics'
    out.mkdir(exist_ok=False)
    private.mkdir(parents=True,exist_ok=True)
    redactions=[]
    # Save exact original failure bytes privately before redacting public copies.
    for path in (root/'docs/03-engineering/ra4a-p2b1').rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts: continue
        raw=path.read_bytes()
        if not any(secret.encode() in raw for secret in secrets): continue
        rel=path.relative_to(root/'docs/03-engineering/ra4a-p2b1')
        dest=private/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        assert not dest.exists()
        dest.write_bytes(raw)
        masked=raw
        hits=0
        for secret in secrets:
            hits+=masked.count(secret.encode())
            masked=masked.replace(secret.encode(),b'[REDACTED_DISPOSABLE_PG_CREDENTIAL]')
        path.write_bytes(masked)
        redactions.append({'path':rel.as_posix(),'original_sha256':hashlib.sha256(raw).hexdigest(),
                           'public_sha256':hashlib.sha256(masked).hexdigest(),'replacement_count':hits,
                           'private_original_relative_path':dest.relative_to(root).as_posix()})
    commands=[['docker','inspect','--format','{{json .State}}',s['container']],
              ['docker','port',s['container'],'5432/tcp'],
              ['docker','logs','--tail','100',s['container']],
              ['docker','stats','--no-stream','--format','{{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.PIDs}}',s['container']]
    ]
    records=[]
    for i,argv in enumerate(commands):
        before=time.monotonic()
        try:
            r=subprocess.run(argv,capture_output=True,timeout=25,check=False)
            raw=r.stdout+r.stderr
            code=r.returncode
        except subprocess.TimeoutExpired as e:
            raw=(e.stdout or b'')+(e.stderr or b'')
            code='TIMEOUT_25S'
        masked=raw
        for secret in secrets: masked=masked.replace(secret.encode(),b'[REDACTED_DISPOSABLE_PG_CREDENTIAL]')
        (out/(str(i)+'.log')).write_bytes(masked)
        records.append({'argv':argv,'exit':code,'seconds':time.monotonic()-before,'sha256':hashlib.sha256(masked).hexdigest()})
    connection={}
    try:
        with psycopg.connect(host=s['host'],port=s['port'],user='postgres',password=s['admin_password'],dbname='postgres',connect_timeout=5,autocommit=True) as c:
            connection={'current_cached_port_works':True,'server':c.execute('SELECT version(),pg_postmaster_start_time()::text').fetchone()}
    except psycopg.Error as e:
        connection={'current_cached_port_works':False,'error_class':type(e).__name__,'sqlstate':e.sqlstate}
    report={'worktree':str(root),'cached_host':s['host'],'cached_port':s['port'],'container':s['container'],
            'commands':records,'redactions':redactions,'connection_probe':connection,
            'root_cause':'UNCONFIRMED_LOCAL_CONNECTION_TIMEOUT','test_outcomes_unchanged':True,
            'raw_failure_bytes_retained_privately_not_for_publication':True}
    (out/'diagnostics-and-redactions.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'worktree':str(root),'connection_probe':connection,'redacted_files':len(redactions),'command_exits':[r['exit'] for r in records]}))
