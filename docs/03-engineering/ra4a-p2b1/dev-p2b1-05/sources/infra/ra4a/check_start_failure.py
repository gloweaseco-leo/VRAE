"""Actual Docker failure before STATE, followed by verified idempotent cleanup."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to((ROOT / 'docs/03-engineering/ra4a-p1').resolve())
    output.mkdir(parents=True, exist_ok=False)
    state = ROOT / 'infra/ra4a/.venv/lab-state.json'
    assert not state.exists()
    start = subprocess.run([sys.executable, 'infra/ra4a/lab.py', 'start', '--output',
                            str(output / 'startup'), '--startup-timeout', '0'],
                           cwd=ROOT, capture_output=True, timeout=150)
    (output / 'start.stdout.log').write_bytes(start.stdout)
    (output / 'start.stderr.log').write_bytes(start.stderr)
    assert start.returncode != 0 and b'REAL_PG_STARTUP_DEADLINE' in start.stderr
    assert not state.exists(), 'Failure must precede credential STATE publication'
    first = output / 'startup/failure-cleanup/teardown.json'
    first_hash = hashlib.sha256(first.read_bytes()).hexdigest()
    for iteration in (1, 2):
        p = subprocess.run([sys.executable, 'infra/ra4a/lab.py', 'stop', '--output',
                            str(output / ('repeat-cleanup-' + str(iteration))),
                            '--startup-output', str(output / 'startup')],
                           cwd=ROOT, capture_output=True, timeout=60)
        (output / ('repeat-' + str(iteration) + '.stdout.log')).write_bytes(p.stdout)
        (output / ('repeat-' + str(iteration) + '.stderr.log')).write_bytes(p.stderr)
        assert p.returncode == 0
    for folder in ('startup/failure-cleanup', 'repeat-cleanup-1', 'repeat-cleanup-2'):
        proof = json.loads((output / folder / 'teardown.json').read_text())
        assert all(proof[k] is True for k in
                   ('owned_container_removed', 'owned_network_removed', 'owned_volume_removed'))
        assert len(proof['actual_results']) == 3
        assert all(r['absent_after'] and 'error' not in r for r in proof['actual_results'])
    assert hashlib.sha256(first.read_bytes()).hexdigest() == first_hash
    result = {'deliberate_harness_failure': 'startup deadline 0 after actual Docker resource creation',
              'startup_exit': start.returncode, 'business_tests_executed': 0,
              'state_never_published': True, 'actual_cleanup_passes': 3,
              'first_cleanup_sha256': first_hash}
    (output / 'failure-probe.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('RA4A_START_FAILURE_CLEANUP_PROOF=' + json.dumps(result))


if __name__ == '__main__':
    main()
