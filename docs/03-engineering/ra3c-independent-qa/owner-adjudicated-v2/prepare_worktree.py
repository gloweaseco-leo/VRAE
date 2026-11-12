"""Synchronous detached exact-SHA checkout and QA-only overlay; never pushes."""
import argparse
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = 'docs/03-engineering/ra3c-independent-qa/'


def git(root,*args):
    return subprocess.check_output(['git',*args],cwd=root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--qa-source',required=True)
    args = parser.parse_args()
    assert re.fullmatch('[0-9a-f]{40}',args.candidate) and re.fullmatch('[0-9a-f]{40}',args.qa_source)
    binding = json.loads(git(ROOT,'show',args.qa_source+':'+PREFIX+'owner-adjudicated-v2/fixtures/candidate-binding.json'))
    assert binding['candidate_sha'] == args.candidate
    target = ROOT.parent/('ra3c-qa-v2-'+args.candidate[:12])
    assert target.parent.resolve() == ROOT.parent.resolve() and not target.exists()
    paths = ['tests/reporting/test_ra3c_independent_acceptance.py',
        'tests/reporting/fixtures/ra3c_codex1_cases.json','tests/reporting/fixtures/ra3c_codex1_inputs.json',
        PREFIX+'owner-adjudicated-v2',PREFIX+'phase-b-native-v1/adapter.py',
        PREFIX+'adapter-preflight-v1/adapter_draft.py']
    # Complete checkout before any status/restore: an active index.lock is not
    # evidence of real deletion and is never removed to force an overlay.
    collision = git(ROOT,'ls-tree','-r','--name-only',args.candidate,'--',*paths)
    assert not collision.strip(), 'QA ownership collision; stop for Owner'
    subprocess.run(['git','worktree','add','--detach',str(target),args.candidate],cwd=ROOT,check=True)
    assert not git(target,'status','--porcelain=v1').strip()
    subprocess.run(['git','restore','--source',args.qa_source,'--staged','--worktree','--',*paths],cwd=target,check=True)
    assert git(target,'rev-parse','HEAD').decode().strip() == args.candidate
    assert not git(target,'diff','--name-only').strip()
    print('Detached/no-push candidate worktree prepared:',target)


if __name__ == '__main__':
    main()
