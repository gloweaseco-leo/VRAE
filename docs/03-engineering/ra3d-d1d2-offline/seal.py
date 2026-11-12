"""Seal source scope and raw local evidence without changing tested source."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = 'e40201bf399cc8c5d11a708fcbe33c31f01e67b2'
ALLOWED = ('vrae/reviewing/', 'tests/reviewing/', 'docs/03-engineering/ra3d-d1d2-offline/')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def tree(ref):
    result = {}
    for row in git('ls-tree', '-r', ref).decode().splitlines():
        metadata, path = row.split('\t')
        result[path] = metadata
    return result


def main():
    head = git('rev-parse', 'HEAD').decode().strip()
    before, after = tree(BASE), tree(head)
    assert all(after.get(p) == value for p, value in before.items())
    added = sorted(after.keys() - before.keys())
    assert all(p.startswith(ALLOWED) for p in added)
    dirty = git('diff', '--name-only', 'HEAD').decode().splitlines()
    assert all(p.startswith(ALLOWED[2]) for p in dirty), dirty
    frozen = []
    for folder in ALLOWED[:2]:
        for path in sorted((ROOT / folder).rglob('*')):
            if path.suffix not in ('.py', '.json') or '__pycache__' in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            raw = git('show', head + ':' + rel)
            frozen.append({'path': rel, 'git_blob': after[rel].split()[-1],
                           'git_bytes_sha256': hashlib.sha256(raw).hexdigest()})
    manifest = {'accepted_main': BASE, 'tested_source_head': head,
                'preserved_main_blob_and_modes': len(before), 'new_paths': added,
                'frozen_source_and_inputs': frozen}
    runs = HERE / 'runs' / head
    stages = [json.loads((runs / p / 'summary.json').read_text()) for p in ('py11', 'py13')]
    scenarios = [json.loads((runs / p / 'scenarios.json').read_text(encoding='utf-8'))
                 for p in ('py11', 'py13')]
    assert all(all(c['exit'] == 0 for c in s['commands']) for s in stages)
    assert scenarios[0]['paths'] == scenarios[1]['paths']
    assert scenarios[0]['refusals'] == scenarios[1]['refusals']
    manifest['dual_runtime_paths_byte_identical'] = True
    manifest['deterministic_targets'] = {p['case']: p['target_digest'] for p in scenarios[0]['paths']}
    encoded = json.dumps(frozen, sort_keys=True, separators=(',', ':')).encode()
    manifest['frozen_set_sha256'] = hashlib.sha256(encoded).hexdigest()
    (HERE / 'SOURCE_FREEZE.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    files = sorted(p for p in HERE.rglob('*') if p.is_file()
                   and p.name not in ('raw-local-evidence.zip', 'RAW_LOCAL_MANIFEST.json')
                   and '__pycache__' not in p.parts and 'post-ci' not in p.parts)
    members = []
    with zipfile.ZipFile(HERE / 'raw-local-evidence.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            raw = path.read_bytes()
            name = path.relative_to(HERE).as_posix()
            archive.writestr(name, raw)
            members.append({'member': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    with zipfile.ZipFile(HERE / 'raw-local-evidence.zip') as archive:
        assert archive.testzip() is None
        for row in members:
            assert hashlib.sha256(archive.read(row['member'])).hexdigest() == row['sha256']
    archive_raw = (HERE / 'raw-local-evidence.zip').read_bytes()
    receipt = {'zip_sha256': hashlib.sha256(archive_raw).hexdigest(), 'bytes': len(archive_raw),
               'members': members, 'frozen_set_sha256': manifest['frozen_set_sha256']}
    (HERE / 'RAW_LOCAL_MANIFEST.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'members'}))
    print('PRESERVED_BASELINE_BLOBS_AND_MODES=' + str(len(before)))


if __name__ == '__main__':
    main()
