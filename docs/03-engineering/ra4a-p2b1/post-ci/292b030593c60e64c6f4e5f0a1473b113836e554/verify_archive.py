"""Read-only exact committed binary archive/member check after final HEAD."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
meta=json.loads((HERE/'ARCHIVE_RECEIPT.json').read_text())
p=HERE/meta['archive']
raw=p.read_bytes()
assert len(raw)==meta['bytes'] and hashlib.sha256(raw).hexdigest()==meta['sha256']
committed=subprocess.check_output(['git','show','HEAD:'+p.relative_to(ROOT).as_posix()],cwd=ROOT)
assert committed==raw
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None and len(z.namelist())==meta['members']
    manifest=z.read('RAW_MANIFEST.json')
    assert hashlib.sha256(manifest).hexdigest()==meta['manifest_sha256']
    rows=json.loads(manifest)
    for row in rows:
        member=z.read(row['path'])
        assert len(member)==row['bytes'] and hashlib.sha256(member).hexdigest()==row['sha256']
proof={'final_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
       'committed_archive_matches_working_bytes':True,'crc':True,'all_manifest_members_verified':len(rows),
       'archive_sha256':meta['sha256'],'archive_members':meta['members']}
(OUT/'LOCAL_ARCHIVE_INTEGRITY.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof))
