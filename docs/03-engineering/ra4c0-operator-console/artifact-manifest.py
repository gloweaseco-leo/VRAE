"""Seal retained documentation/evidence bytes, excluding only the seal itself."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
relative=HERE.relative_to(ROOT).as_posix()
raw=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard','--',relative],cwd=ROOT)
files={}
for name in sorted({n.decode('utf-8') for n in raw.split(b'\0') if n}):
    path=ROOT/name
    if path.name=='ARTIFACT-MANIFEST.json' or not path.is_file():
        continue
    assert path.resolve().is_relative_to(HERE)
    data=path.read_bytes()
    files[path.relative_to(HERE).as_posix()]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
result={'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'accepted_main':'225ded57add21680171cfaecac9f89df6b1af155','file_count':len(files),
    'raw_bytes_preserved_by_local_gitattributes':True,'files':files}
(HERE/'ARTIFACT-MANIFEST.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'files':len(files),'total_bytes':sum(r['bytes'] for r in files.values())}))
