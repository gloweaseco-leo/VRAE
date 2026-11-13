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
comparisons = []
for name in ('loopback-diag-03', 'loopback-diag-04-explicit'):
    folder = proof.parent / name
    actual = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
    assert actual['internal_network_unchanged']
    assert actual['outcome'] == 'INTERNAL_PG_AUTHENTICATED_BUT_NO_HOST_PUBLICATION'
    assert all(row['absent_after'] for row in actual['cleanup'])
    for row in actual['events']:
        assert hashlib.sha256((folder / row['file']).read_bytes()).hexdigest() == row['sha256']
    comparisons.append({'folder': name, 'raw_hashes_verified': True,
                        'owned_resources_absent': True, 'host_sql_verified': False})
result['bounded_comparisons'] = comparisons
result['protected_lab_blob'] = git('rev-parse', BASE + ':infra/ra4a/lab.py')[0]
actual_cleanup = []
for name in ('startup-05-auto-cleanup/recovered-cleanup',
             'startup-06-auto-cleanup/failure-cleanup'):
    file = proof.parent / name / 'teardown.json'
    actual = json.loads(file.read_text(encoding='utf-8'))
    assert actual['owned_only'] and len(actual['resources']) == 3
    assert all(row['absent_after'] for row in actual['resources'])
    actual_cleanup.append({'file': str(file.relative_to(ROOT)).replace('\\', '/'),
                           'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
assert not (proof.parent.parent / 'runtime/auto-cleanup-state-06.json').exists()
result['actual_cleanup_receipts'] = actual_cleanup
(proof.parent / 'checkpoint-audit.json').write_text(
    json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
