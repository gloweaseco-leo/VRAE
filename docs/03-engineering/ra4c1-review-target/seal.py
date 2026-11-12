"""Accepted-main blob/mode and owned-artifact seal, no re-pinning targets."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE='e9ec1bd7f36a0446af14f04b66b71e4d45ebfb97'
ALLOWED=('apps/operator_console/','tests/operator_console/','docs/03-engineering/ra4c1-review-target/')


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def tree(ref):
    return {r.split(b'\t',1)[1].decode():r.split(b'\t',1)[0].decode().split()[::2]
            for r in git('ls-tree','-r','-z',ref).split(b'\0') if r}


head=git('rev-parse','HEAD').decode().strip()
base,current=tree(BASE),tree(head)
changed=[p for p in base if current.get(p)!=base[p]]
new=[p for p in current if p not in base]
assert all(p.startswith(ALLOWED) for p in changed+new)
assert base['tests/operator_console/test_console.py']==current['tests/operator_console/test_console.py']
assert all(p.startswith(ALLOWED) for p in git('diff','--name-only','HEAD').decode().splitlines())
assert not git('diff','HEAD','--name-only','--','apps/operator_console','tests/operator_console').strip()
protected={p:v for p,v in base.items() if not p.startswith(ALLOWED)}
fingerprint=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert fingerprint(protected)==fingerprint({p:current[p] for p in protected})
record={'head':head,'accepted_main':BASE,'baseline_entries':len(base),'owned_existing_changed':changed,
        'new_paths':new,'protected_blobs_modes_sha256':fingerprint(protected),
        'all_protected_blobs_modes_retained':True,'original_58_test_blob':base['tests/operator_console/test_console.py'],
        'apps_and_tests':{p:v for p,v in current.items() if p.startswith(ALLOWED[:2])}}
(HERE/'SOURCE-SEAL.json').write_bytes(json.dumps(record,indent=2).encode()+b'\n')
prefix=HERE.relative_to(ROOT).as_posix()
raw=git('ls-files','-z','--cached','--others','--exclude-standard','--',prefix)
files={}
for name in sorted({n.decode() for n in raw.split(b'\0') if n}):
    path=ROOT/name
    if path.name=='ARTIFACT-MANIFEST.json' or not path.is_file():
        continue
    assert path.resolve().is_relative_to(HERE)
    value=path.read_bytes()
    files[path.relative_to(HERE).as_posix()]={'sha256':hashlib.sha256(value).hexdigest(),'bytes':len(value)}
(HERE/'ARTIFACT-MANIFEST.json').write_bytes(json.dumps({'head':head,'files':files},indent=2).encode()+b'\n')
print(json.dumps({'head':head,'protected':len(protected),'changed':changed,'artifact_files':len(files)}))
