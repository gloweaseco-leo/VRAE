"""Read-only source and real dual-Python evidence seal after accepted main merge."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MAIN = '9d138ba57e0b442b9dace1a2247d7aaa46ca38ac'
SOURCE = '3eceea972ef1ec4bf68ee68654b90a5ff7e30a14'
OLD = '469ccb6cf88b7a66d97b2572be7653048a513dd0'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def tree(ref):
    return {s.split('\t')[1]: s.split('\t')[0] for s in git('ls-tree', '-r', ref).decode().splitlines()}


def main():
    before, after, old = tree(MAIN), tree(SOURCE), tree(OLD)
    assert all(after.get(p) == v for p, v in before.items())
    exceptions = {'infra/ra4a/lab.py', '.github/workflows/ra4a-pg.yml'}
    accepted_upstream_changes = set(git('diff', '--name-only',
        '225ded57add21680171cfaecac9f89df6b1af155', MAIN).decode().splitlines())
    old_changed_by_main = {p for p in old if p in accepted_upstream_changes}
    assert old_changed_by_main == {'infra/ra1a/Dockerfile'}
    assert all(after.get(p) == v for p, v in old.items()
               if p not in exceptions | old_changed_by_main)
    assert not git('diff', '--name-only', SOURCE).strip()
    frozen = []
    allowed = ('db/migrations/', 'vrae/persistence/', 'integration/ra4a/',
               'tests/persistence/', 'infra/ra4a/', 'docs/03-engineering/ra4a-p1/')
    added = sorted(after.keys() - before.keys())
    assert all(p.startswith(allowed) or p in {'requirements-ra4a.lock', '.github/workflows/ra4a-pg.yml'}
               for p in added)
    for p in added:
        if p.startswith('docs/'):
            continue
        raw = git('show', SOURCE + ':' + p)
        frozen.append({'path': p, 'mode_blob': after[p], 'git_sha256': hashlib.sha256(raw).hexdigest()})
    local = []
    for runtime in ('py311', 'py313'):
        folder = HERE / 'source-3eceea9' / runtime
        commands = json.loads((folder / 'commands.json').read_text())
        assert all(r['exit'] == 0 for r in commands['commands'])
        for filename, count in [('postgres.xml', 54), ('pure.xml', 11)]:
            suite = ET.parse(folder / filename).getroot().find('testsuite')
            assert int(suite.attrib['tests']) == count
            assert all(int(suite.attrib[k]) == 0 for k in ('errors', 'failures', 'skipped'))
            assert len(suite.findall('testcase')) == count
        catalog = json.loads((folder / 'pg-catalog-and-calls.json').read_text())
        assert len(catalog['calls']) == 54 and all(r['outcome'] == 'passed' for r in catalog['calls'])
        assert catalog['migrations'] == [[1, '0557738e22e83a6f1c991e8c2a796749ce43845ad80fec44d8dc4c891fd9b5e2']]
        backup = json.loads((folder / 'backup-restore.json').read_text())
        assert backup['source_data_sha256'] == backup['restored_data_sha256']
        restart = json.loads((folder / 'real-restart.json').read_text())
        assert restart['committed_ids_preserved'] and all(v == 'on' for v in restart['settings'].values())
        local.append({'runtime': runtime, 'python': commands['python'], 'pg_pass': 54, 'pure_pass': 11,
                      'backup': backup, 'restart': restart})
    scope = {'accepted_main': MAIN, 'tested_source_head': SOURCE,
             'merge_parents': git('show', '-s', '--format=%P', SOURCE).decode().strip().split(),
             'preserved_latest_main_blob_modes': len(before),
             'preserved_previous_candidate_blob_modes_except_harness_and_accepted_main_delta': len(old)-len(exceptions | old_changed_by_main),
             'owner_accepted_upstream_modified_existing_paths': sorted(old_changed_by_main),
             'authorized_modified_existing_paths': sorted(exceptions),
             'frozen_sources': frozen,
             'source_set_sha256': hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
             'dual_actual_local': local}
    (HERE / 'MAIN_INTEGRATION_SCOPE.json').write_text(json.dumps(scope, indent=2)+'\n', encoding='utf-8')
    state = json.loads((ROOT / 'infra/ra4a/.venv/lab-state.json').read_text())
    secrets = [state['admin_password'], *state['runtime_passwords'].values()]
    teardown = subprocess.run([__import__('sys').executable, 'infra/ra4a/lab.py', 'stop', '--output',
                               str(HERE / 'main-9d138-teardown')], cwd=ROOT, capture_output=True)
    (HERE / 'final-teardown.stdout.log').write_bytes(teardown.stdout)
    (HERE / 'final-teardown.stderr.log').write_bytes(teardown.stderr)
    assert teardown.returncode == 0
    files = sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                   and p.name not in ('resumed-local-evidence.zip', 'RESUMED_LOCAL_MANIFEST.json'))
    members = []
    with zipfile.ZipFile(HERE / 'resumed-local-evidence.zip', 'x', zipfile.ZIP_DEFLATED) as z:
        for p in files:
            raw = p.read_bytes()
            assert not any(s.encode() in raw for s in secrets), p.name
            name = p.relative_to(HERE).as_posix()
            z.writestr(name, raw)
            members.append({'member': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    with zipfile.ZipFile(HERE / 'resumed-local-evidence.zip') as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(r['member'])).hexdigest() == r['sha256'] for r in members)
    raw = (HERE / 'resumed-local-evidence.zip').read_bytes()
    manifest = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'members': members,
                'source_set_sha256': scope['source_set_sha256'], 'actual_lab_credential_scan': 'NO_MATCHES'}
    (HERE / 'RESUMED_LOCAL_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'members'}))
    print('PRESERVED_LATEST_MAIN_BLOBS_AND_MODES=' + str(len(before)))


if __name__ == '__main__':
    main()
