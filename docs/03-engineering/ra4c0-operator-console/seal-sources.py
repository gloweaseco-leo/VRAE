"""Prove unchanged accepted files and record exact read-side application blobs."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE='225ded57add21680171cfaecac9f89df6b1af155'
ALLOWED=('apps/operator_console/','tests/operator_console/','docs/03-engineering/ra4c0-operator-console/')
EXCEPTION='infra/ra1a/Dockerfile'


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def tree(ref):
    return {r.split(b'\t',1)[1].decode():r.split(b'\t',1)[0].decode().split()[::2]
            for r in git('ls-tree','-r','-z',ref).split(b'\0') if r}


base=tree(BASE)
head=git('rev-parse','HEAD').decode().strip()
current=tree(head)
changed=[p for p,h in base.items() if current.get(p)!=h]
assert changed==[EXCEPTION],changed
assert base[EXCEPTION][0]==current[EXCEPTION][0]
old=git('show',BASE+':'+EXCEPTION)
assert git('show',head+':'+EXCEPTION)==old.replace(b'COPY vrae ./vrae\n',
    b'COPY vrae ./vrae\nCOPY apps/operator_console ./apps/operator_console\n',1)
new=[p for p in current if p not in base]
assert all(p.startswith(ALLOWED) for p in new)
assert not git('diff','--name-only','HEAD','--','apps/operator_console','tests/operator_console').strip()
assert all(p.startswith(ALLOWED) for p in git('diff','--name-only','HEAD').decode().splitlines())
untracked=git('ls-files','--others','--exclude-standard').decode().splitlines()
assert all(p.startswith(ALLOWED) for p in untracked)
application={p:{'git_mode':h[0],'git_blob':h[1],'git_bytes_sha256':hashlib.sha256(git('show',head+':'+p)).hexdigest()}
             for p,h in current.items() if p.startswith(('apps/operator_console/','tests/operator_console/'))}
retained={p:h for p,h in base.items() if p!=EXCEPTION}
actual={p:current[p] for p in retained}
def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert fingerprint(retained)==fingerprint(actual)
seal={'accepted_main':BASE,'source_head':head,'baseline_file_count':len(base),
      'baseline_files_changed':changed,'authorized_new_file_count':len(new),
      'baseline_modes_and_blobs_retained_except_exact_copy':True,
      'accepted_retained_modes_blobs_sha256':fingerprint(retained),
      'actual_retained_modes_blobs_sha256':fingerprint(actual),
      'exception_authorization':'https://github.com/gloweaseco-leo/VRAE/pull/61#issuecomment-6825546180',
      'allowed_roots':ALLOWED,'application':application,
      'human_gold':'0/26 - NOT EVALUABLE','real_approval':'NOT_IMPLEMENTED','customer_share':'NO_GO'}
existing=HERE/'SOURCE-SEAL.json'
archive=HERE/'SOURCE-SEAL-a185-initial.json'
if existing.exists() and json.loads(existing.read_text(encoding='utf-8'))['accepted_main']!=BASE:
    assert not archive.exists()
    archive.write_bytes(existing.read_bytes())
existing.write_text(json.dumps(seal,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_head':head,'baseline_files':len(base),'baseline_files_unchanged':len(base)-1,
                  'exact_authorized_copy_exception':True,'application_files':len(application)}))
