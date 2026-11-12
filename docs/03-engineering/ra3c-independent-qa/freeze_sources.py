"""Freeze staged Git blobs and verify all accepted baseline blobs unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = '2429be6dc5d7dcb48221ab179f063b93ce4b1956'
PATHS = ['tests/reporting/test_ra3c_independent_acceptance.py',
    'tests/reporting/fixtures/ra3c_codex1_cases.json',
    'tests/reporting/fixtures/ra3c_codex1_inputs.json'] + [
    'docs/03-engineering/ra3c-independent-qa/'+p for p in (
        'MATRIX.md','SUBJECT_PROTOCOL.md','make_inputs.py','audit_inputs.py',
        'run_phase_a.py','freeze_sources.py')]


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def preserved():
    lines = git('ls-tree','-r',BASE).decode().splitlines()
    index = {line.split('\t',1)[1]:line.split('\t',1)[0].split()[1]
             for line in git('ls-files','--stage').decode().splitlines()}
    entries = {}
    for line in lines:
        meta,path = line.split('\t',1)
        blob = meta.split()[2]
        assert index[path] == blob, ('BASELINE_BLOB_CHANGED',path)
        entries[path] = blob
    diff = git('diff',BASE,'--name-status').decode().splitlines()
    for line in diff:
        status,path = line.split('\t',1)
        assert status == 'A', ('ONLY_ADDITIONS_AUTHORIZED',line)
        assert path == PATHS[0] or path.startswith('tests/reporting/fixtures/ra3c_codex1_') or path.startswith('docs/03-engineering/ra3c-independent-qa/')
    assert not git('diff','--name-only').strip(), 'Stage all intended source additions before freezing/checking'
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--create',action='store_true')
    args = parser.parse_args()
    entries = preserved()
    target = HERE/'FREEZE.json'
    if args.create:
        assert not target.exists(), 'Do not overwrite a freeze'
        files = {}
        for path in PATHS:
            content = git('show',':'+path)
            files[path] = dict(git_blob=git('rev-parse',':'+path).decode().strip(),
                git_blob_sha256=hashlib.sha256(content).hexdigest(),
                worktree_sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
        data = dict(version='CODEX1_RA3C_QA_V1_PRE_CANDIDATE',base_sha=BASE,
            cases=64,scenarios=14,guard_contexts=18,candidate_inspected=False,
            adapter='NOT_BOUND',visual='VISUAL_NOT_VERIFIED',files=files,
            baseline_blob_count=len(entries),baseline_blobs=entries)
        target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    else:
        data = json.loads(target.read_text(encoding='utf-8'))
        assert data['baseline_blobs'] == entries
        for path,expected in data['files'].items():
            assert git('rev-parse',':'+path).decode().strip() == expected['git_blob'], path
            assert hashlib.sha256(git('show',':'+path)).hexdigest() == expected['git_blob_sha256'], path
    print('Frozen source count:',len(PATHS),'accepted blobs preserved:',len(entries),'; no candidate execution/feature PASS')


if __name__ == '__main__':
    main()
