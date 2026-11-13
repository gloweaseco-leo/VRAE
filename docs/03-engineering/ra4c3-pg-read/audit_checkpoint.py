"""Read-only source scope and preserved evidence audit; no functional retry."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = '51e2ff3f592c206fddf8193ad7346efbd2a70136'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().splitlines()


paths = sorted(set(git('diff', '--name-only', BASE) +
                   git('ls-files', '--others', '--exclude-standard')))
allowed = ('apps/operator_console/', 'integration/ra4c3/',
           'docs/03-engineering/ra4c3-pg-read/')
assert all(p.startswith(allowed) or
           (p.startswith('tests/operator_console/test_ra4c3_') and p.endswith('.py'))
           for p in paths), paths
original_tests = set(git('ls-tree', '-r', '--name-only', BASE, 'tests'))
assert not original_tests.intersection(paths)
proof = ROOT / 'docs/03-engineering/ra4c3-pg-read/evidence/startup-01'
receipt = json.loads((proof / 'HARD_STOP.json').read_text(encoding='utf-8'))
for row in receipt['diagnostics']:
    assert hashlib.sha256((proof / row['file']).read_bytes()).hexdigest() == row['sha256']
assert all(row['label_verified'] and row['absent_after'] for row in receipt['cleanup'])
result = {'accepted_entry_main': BASE, 'changed_paths': paths,
          'scope_allowed': True, 'old_tests_modified': False,
          'raw_diagnostic_hashes_verified': True,
          'owned_cleanup_receipt_verified': True,
          'functional_or_ci_pass': False}
(proof.parent / 'checkpoint-audit.json').write_text(
    json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
