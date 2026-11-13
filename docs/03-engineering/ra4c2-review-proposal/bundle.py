"""Seal post-CI evidence without mutating the frozen Git head."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
destination=Path(sys.argv[1]).resolve()
assert destination.is_relative_to(HERE/'evidence')
acceptance=json.loads((destination/'ACCEPTANCE.json').read_text(encoding='utf-8'))
assert acceptance['state']=='SIX_CI_GREEN_ENGINEERING_CANDIDATE_NOT_OWNER_FINAL_PASS'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert head==acceptance['final_sha']
assert not subprocess.check_output(['git','diff','HEAD','--name-only','--','apps/operator_console','tests/operator_console'],cwd=ROOT)
prefix=HERE.relative_to(ROOT).as_posix()
names=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard','--',prefix],cwd=ROOT)
paths=sorted({ROOT/n.decode() for n in names.split(b'\0') if n})
excluded={'RA4C2-final-evidence.zip','BUNDLE.json','FINAL-ARTIFACTS.json','PR-BODY.md'}
paths=[p for p in paths if p.is_file() and p.name not in excluded]
assert all(p.resolve().is_relative_to(HERE) for p in paths)
files={p.relative_to(HERE).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                                   'bytes':p.stat().st_size} for p in paths}
manifest=destination/'FINAL-ARTIFACTS.json'
manifest.write_bytes(json.dumps({'final_sha':head,'files':files},indent=2).encode()+b'\n')
paths.append(manifest)
archive=destination/'RA4C2-final-evidence.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in paths:
        z.write(p,p.relative_to(HERE).as_posix())
record={'final_sha':head,'file':archive.name,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'bytes':archive.stat().st_size,'members':len(paths),'post_ci_no_head_drift':True}
(destination/'BUNDLE.json').write_bytes(json.dumps(record,indent=2).encode()+b'\n')
print(json.dumps(record))
