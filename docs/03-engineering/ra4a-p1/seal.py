"""Seal original local evidence and prove additive-only accepted-main scope."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BASE='225ded57add21680171cfaecac9f89df6b1af155'
ALLOWED=('db/migrations/','vrae/persistence/','integration/ra4a/','tests/persistence/',
         'infra/ra4a/','docs/03-engineering/ra4a-p1/')
SPECIAL={'requirements-ra4a.lock','.github/workflows/ra4a-pg.yml'}


def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)


def tree(ref):
    return {s.split('\t')[1]:s.split('\t')[0] for s in git('ls-tree','-r',ref).decode().splitlines()}


def main():
    head=git('rev-parse','HEAD').decode().strip()
    before,after=tree(BASE),tree(head)
    assert all(after.get(p)==v for p,v in before.items())
    added=sorted(after.keys()-before.keys())
    assert all(p in SPECIAL or p.startswith(ALLOWED) for p in added)
    assert not git('diff','--name-only','HEAD','--','vrae','tests','db','integration','infra','.github','requirements-ra4a.lock').strip()
    frozen=[]
    for p in added:
        if p.startswith('docs/'): continue
        assert '.venv/' not in p and 'lab-state' not in p
        raw=git('show',head+':'+p)
        frozen.append({'path':p,'mode_blob':after[p],'git_sha256':hashlib.sha256(raw).hexdigest()})
    source_set=hashlib.sha256(json.dumps(frozen,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    results=[]
    for runtime in ('py311','py313'):
        folder=HERE/('final-source-'+head[:7])/runtime
        r=json.loads((folder/'commands.json').read_text())
        assert all(c['exit']==0 for c in r['commands'])
        cat=json.loads((folder/'pg-catalog-and-calls.json').read_text())
        assert len(cat['calls'])==54 and all(c['outcome']=='passed' for c in cat['calls'])
        assert cat['migrations']==[[1,hashlib.sha256((ROOT/'db/migrations/0001_ra4a_test_only.sql').read_bytes().replace(b'\r\n',b'\n')).hexdigest()]]
        backup=json.loads((folder/'backup-restore.json').read_text())
        assert backup['source_data_sha256']==backup['restored_data_sha256']
        restart=json.loads((folder/'real-restart.json').read_text())
        assert restart['committed_ids_preserved'] and all(x=='on' for x in restart['settings'].values())
        results.append({'runtime':runtime,'python':r['python'],'pg_cases':54,
            'backup':backup,'restart':restart,'migrations':cat['migrations']})
    record={'accepted_main':BASE,'tested_source_head':head,'preserved_main_blob_modes':len(before),
            'new_paths':added,'frozen_sources':frozen,'source_set_sha256':source_set,
            'dual_actual_pg_results':results,'original_dependencies_ci_docker_schemas_tests_unchanged':True}
    (HERE/'SOURCE_SCOPE.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    # Local credentials are neither committed nor archived. Scan all candidate
    # source/evidence bytes for the actual lab secrets without printing them.
    state=json.loads((ROOT/'infra/ra4a/.venv/lab-state.json').read_text())
    secrets=[state['admin_password'],*state['runtime_passwords'].values()]
    stopped=subprocess.run([__import__('sys').executable,str(ROOT/'infra/ra4a/lab.py'),
        'stop','--output',str(HERE/'final-teardown')],cwd=ROOT,capture_output=True)
    (HERE/'final-teardown.stdout.log').write_bytes(stopped.stdout)
    (HERE/'final-teardown.stderr.log').write_bytes(stopped.stderr)
    assert stopped.returncode==0, 'OWNED_LAB_TEARDOWN_FAILED'
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                 and p.name not in ('raw-local-evidence.zip','RAW_LOCAL_MANIFEST.json'))
    for p in files:
        assert not any(s.encode() in p.read_bytes() for s in secrets), p.name
    members=[]
    with zipfile.ZipFile(HERE/'raw-local-evidence.zip','x',zipfile.ZIP_DEFLATED) as z:
        for p in files:
            raw=p.read_bytes(); name=p.relative_to(HERE).as_posix()
            z.writestr(name,raw)
            members.append({'member':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    with zipfile.ZipFile(HERE/'raw-local-evidence.zip') as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r['member'])).hexdigest()==r['sha256'] for r in members)
    raw=(HERE/'raw-local-evidence.zip').read_bytes()
    manifest={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'members':members,
              'source_set_sha256':source_set,'actual_secret_scan':'NO_MATCHES'}
    (HERE/'RAW_LOCAL_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='members'}))
    print('PRESERVED_BASELINE_BLOBS_AND_MODES='+str(len(before)))


if __name__=='__main__': main()
