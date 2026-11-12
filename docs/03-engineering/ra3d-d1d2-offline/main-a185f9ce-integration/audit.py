"""Read-only integration proof; preserve all previous source and receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PREVIOUS = 'c849d3d01a2af976bfe0cdef4fabb7f840bfbd37'
MAIN = 'a185f9ce7e67904f2c0aef854716ca9844144592'
PREFIX = 'docs/03-engineering/ra3d-d1d2-offline/'
OWNED = ('vrae/reviewing/', 'tests/reviewing/', PREFIX)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def tree(ref):
    return {line.split('\t', 1)[1]: line.split('\t', 1)[0]
            for line in git('ls-tree', '-r', ref).decode().splitlines()}


def receipts():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / PREFIX / 'post-ci' / PREVIOUS).rglob('*')) if p.is_file()}


def main():
    mode = sys.argv[1]
    head = git('rev-parse', 'HEAD').decode().strip()
    assert not git('status', '--porcelain', '--untracked-files=no').strip()
    if mode == 'before':
        assert head == PREVIOUS
        assert git('rev-parse', 'origin/main').decode().strip() == MAIN
        delta = git('diff', '--name-only', 'e40201bf399cc8c5d11a708fcbe33c31f01e67b2', MAIN).decode().splitlines()
        assert all(p.startswith('docs/03-engineering/ra3d-phase06-native-review-bridge/') for p in delta)
        record = {'previous_head': head, 'main': MAIN, 'tracked_clean': True,
                  'accepted_main_changed_paths': delta, 'previous_untracked_receipt_hashes': receipts()}
        path = HERE / 'BEFORE_MERGE.json'
    else:
        old, accepted, current = tree(PREVIOUS), tree(MAIN), tree(head)
        assert all(current.get(p) == v for p, v in accepted.items())
        assert all(p.startswith(OWNED) for p in current.keys() - accepted.keys())
        owned_old = {p: v for p, v in old.items() if p.startswith(OWNED)}
        assert all(current.get(p) == v for p, v in owned_old.items())
        before = json.loads((HERE / 'BEFORE_MERGE.json').read_text(encoding='utf-8'))
        assert receipts() == before['previous_untracked_receipt_hashes']
        freeze = json.loads(git('show', PREVIOUS + ':' + PREFIX + 'SOURCE_FREEZE.json'))
        for r in freeze['frozen_source_and_inputs']:
            assert current[r['path']].split()[-1] == r['git_blob']
            assert hashlib.sha256(git('show', head + ':' + r['path'])).hexdigest() == r['git_bytes_sha256']
        record = {'audited_head': head, 'latest_main': MAIN, 'tracked_clean': True,
                  'preserved_latest_main_blob_modes': len(accepted),
                  'preserved_previous_owned_blob_modes': len(owned_old),
                  'preserved_untracked_receipt_files': len(receipts()),
                  'frozen_source_input_members_unchanged': len(freeze['frozen_source_and_inputs']),
                  'frozen_set_sha256': freeze['frozen_set_sha256'],
                  'head_parents': git('show', '-s', '--format=%P', head).decode().split(),
                  'all_new_paths_owned': sorted(current.keys() - accepted.keys())}
        path = Path(sys.argv[2])
    assert not path.exists(), 'Never overwrite previous proof'
    path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in record.items() if not isinstance(v, (list, dict))}))


if __name__ == '__main__':
    main()
