"""Replay accepted P2B1 tests in a separate owned C3 lab; no UI write wiring.

The protected runner cannot redirect its output outside the P2B1 directory.
This wrapper redirects only fixture STATE and evidence, retaining original tests.
"""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys

from integration.ra4c3 import lab


def run(output):
    output = lab.bounded(output)
    output.mkdir(parents=True, exist_ok=False)
    state = lab.OWN / 'runtime' / (output.name + '-state.json')
    try:
        lab.start(state, output / 'startup', option_a_local_trial=True)
        lab.migrate(state)
        env = dict(os.environ, RA4C3_STATE=str(state), RA4A_P2B1_EVIDENCE_DIR=str(output))
        argv = [sys.executable, '-B', '-m', 'pytest', '-q', '--import-mode=importlib',
                '-p', 'integration.ra4c3.pytest_adapter',
                '-p', 'integration.ra4a.p2b1_plugin', '--confcutdir=integration/ra4a/p2b1',
                'integration/ra4a/p2b1/cases.py', 'integration/ra4a/p2b1/parity_cases.py',
                '--basetemp=' + str(lab.OWN / 'runtime' / ('temp-' + output.name)),
                '--junitxml=' + str(output / 'tests.xml')]
        result = subprocess.run(argv, cwd=lab.ROOT, env=env, capture_output=True)
        for name, raw in [('stdout.log', result.stdout), ('stderr.log', result.stderr)]:
            (output / name).write_bytes(raw)
        receipt = {'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=lab.ROOT).decode().strip(),
                   'python': sys.version, 'argv': argv, 'returncode': result.returncode,
                   'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
                   'stderr_sha256': hashlib.sha256(result.stderr).hexdigest(),
                   'ui_write_integration': False, 'synthetic_only': True}
        (output / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps(receipt), flush=True)
        if result.returncode:
            print(result.stdout.decode(errors='replace')[-6000:])
            print(result.stderr.decode(errors='replace')[-1500:])
            raise RuntimeError('ORIGINAL_P2B1_RED')
    finally:
        if state.exists():
            held = json.loads(state.read_text(encoding='utf-8'))
            lab.stop(state, output / 'teardown')
            with socket.socket() as probe:
                probe.settimeout(2)
                code = probe.connect_ex(('127.0.0.1', held['port']))
            assert code != 0, 'REMOVED_PG_STILL_ACCESSIBLE'
            (output / 'closed-port.json').write_text(json.dumps({'closed': True, 'connect_ex': code}), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    run(parser.parse_args().output)
