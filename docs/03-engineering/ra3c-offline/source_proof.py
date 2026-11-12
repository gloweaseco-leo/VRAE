"""Read-only accepted-main blob/mode preservation and strict Issue45 path audit."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
ACCEPTED = '2429be6dc5d7dcb48221ab179f063b93ce4b1956'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8')


def allowed(path):
    return (path.startswith(('vrae/reporting/', 'tests/reporting/',
                             'docs/03-engineering/ra3c-offline/'))
            or path == 'scripts/verify_ra3c.py')


rows = []
for line in git('ls-tree', '-r', ACCEPTED).splitlines():
    mode_type_hash, path = line.split('\t', 1)
    mode, kind, blob = mode_type_hash.split()
    rows.append({'path': path, 'mode': mode, 'type': kind, 'blob': blob})
changes = git('diff', '--name-status', ACCEPTED).splitlines()
for line in changes:
    status, path = line.split('\t')
    assert status == 'A' and allowed(path), line
tracked = {line.split('\t')[1]: line.split('\t')[0].split()[:2]
           for line in git('ls-files', '--stage').splitlines()}
for row in rows:
    assert tracked[row['path']] == [row['mode'], row['blob']], row['path']
assert not git('diff', '--name-only'), 'WORKING_TREE_DIFFERS_FROM_STAGED_SOURCE'
proof = {'accepted_main': ACCEPTED, 'current_head': git('rev-parse', 'HEAD').strip(),
         'accepted_files_preserved': len(rows), 'new_owned_paths': len(changes),
         'audit': 'EXACT_ACCEPTED_INDEX_BLOB_MODE_AND_NO_WORKING_DIFF',
         'accepted_files': rows, 'changes': changes}
(OUT / 'source-proof.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in proof.items() if k not in ('accepted_files', 'changes')}))
