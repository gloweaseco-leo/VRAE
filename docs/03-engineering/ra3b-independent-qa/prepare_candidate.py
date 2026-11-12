"""Create a detached disposable candidate only after explicit final-ready notice.

No checkout/cherry-pick/commit/push in either developer branch. Existing paths
are never overwritten. The supplied candidate commit must already be fetched.
"""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--ready-notice', required=True, help='Owner/Codex-2 final-ready comment URL')
    args = p.parse_args()
    assert re.fullmatch('[0-9a-f]{40}', args.source)
    assert args.ready_notice.startswith('https://github.com/gloweaseco-leo/VRAE/')
    assert git('rev-parse', args.source+'^{commit}') == args.source
    paths = git('ls-files', 'tests/interpretation/test_ra3b_independent_adversarial.py',
        'tests/interpretation/fixtures/ra3b_codex1_*.json',
        'docs/03-engineering/ra3b-independent-qa').splitlines()
    assert paths
    candidate_paths = set(git('ls-tree', '-r', '--name-only', args.source).splitlines())
    assert not candidate_paths.intersection(paths), 'STOP: exclusive QA paths already occupied'
    target = ROOT.parent/('ra3b-qa-candidate-'+args.source[:12])
    # Original worktree is root/.worktrees/qa, so this stays under the project root.
    assert target.resolve().is_relative_to(ROOT.parents[1].resolve()) and not target.exists()
    git('worktree', 'add', '--detach', str(target), args.source)
    for path in paths:
        data = subprocess.check_output(['git', 'show', 'HEAD:'+path], cwd=ROOT)
        dest = target/path
        assert not dest.exists()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    assert not git('diff', '--name-only', args.source, cwd=target)
    assert git('rev-parse', 'HEAD', cwd=target) == args.source
    print('Detached candidate source:', args.source)
    print('Final-ready notice:', args.ready_notice)
    print('Frozen overlay paths:', len(paths))
    print('Workspace:', target)
    print('Next: run_qa.py --mode candidate --expected-source <exact SHA> --out <new path>, both Pythons')


if __name__ == '__main__':
    main()
