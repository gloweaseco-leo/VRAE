"""Publish bounded synthetic receipts, never copied runtime trees or raw inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'docs/03-engineering/evidence-pack-perf'
RUNTIME = DOC / '.runtime'
BASE = '6b2a2dfff8d6de2cf16c2509e9cdcf30a2267d83'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    junit = {}
    for name in ('cache-311-r1.xml', 'cache-311-r2.xml', 'cache-313-r1.xml',
                 'native-311.xml', 'native-313.xml'):
        raw = (RUNTIME / name).read_bytes()
        cases = ET.fromstring(raw).findall('.//testcase')
        ids = sorted(c.get('classname', '') + '::' + c.attrib['name'] for c in cases)
        junit[name] = {'raw_sha256': sha(raw), 'tests': len(cases),
            'failures': sum(c.find('failure') is not None for c in cases),
            'errors': sum(c.find('error') is not None for c in cases),
            'skipped': sum(c.find('skipped') is not None for c in cases),
            'exact_test_ids_sha256': sha('\n'.join(ids).encode())}
    for name in ('cache-311-r2.xml', 'cache-313-r1.xml', 'native-311.xml', 'native-313.xml'):
        assert junit[name]['failures'] == junit[name]['errors'] == 0
    for left, right in (('cache-311-r2.xml', 'cache-313-r1.xml'), ('native-311.xml', 'native-313.xml')):
        assert junit[left]['exact_test_ids_sha256'] == junit[right]['exact_test_ids_sha256']
    for minor in ('311', '313'):
        raw = (RUNTIME / f'compare-{minor}-r1/comparison.json').read_bytes()
        data = json.loads(raw)
        assert data['identical_outputs'] is True
        (DOC / f'comparison-{minor}.json').write_bytes(raw)
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT)
    diff = git('diff', BASE, '--', 'vrae/evidence/pack.py')
    (DOC / 'pack.patch').write_bytes(diff)
    original = set(git('ls-tree', '-r', '--name-only', BASE).decode().splitlines())
    protected = sorted(original & set(git('diff', '--name-only', BASE).decode().splitlines()))
    assert protected == ['vrae/evidence/pack.py'], protected
    receipt = {'base': BASE, 'existing_files_changed': protected,
        'old_pack_blob': git('rev-parse', BASE + ':vrae/evidence/pack.py').decode().strip(),
        'new_pack_blob': git('hash-object', 'vrae/evidence/pack.py').decode().strip(),
        'diff_sha256': sha(diff), 'junit': junit,
        'preserved_b5a_source_red': {'assertion': 'ACCEPTED_SOURCE_CHANGED',
            'location': 'integration/ra4c_b5a/publication.py:65',
            'raw_log_sha256': sha((RUNTIME / 'original-b5a-source-red.log').read_bytes())},
        'actual_pg_worker_trial': 'NOT_PERFORMED_C3_UNMERGED_PR112_LAUNCHER_NOT_IMPORTED',
        'local_timing_environment': 'Shared Windows host; concurrent native regressions and other owners processes; wall time is not a production SLA'}
    (DOC / 'local-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
