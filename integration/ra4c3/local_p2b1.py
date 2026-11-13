"""Replay accepted P2B1 and optional B2 tests in an owned C3 lab; no UI wiring.

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


def run(output, *, include_identity=False):
    output = lab.bounded(output)
    output.mkdir(parents=True, exist_ok=False)
    state = lab.OWN / 'runtime' / (output.name + '-state.json')
    try:
        lab.start(state, output / 'startup', option_a_local_trial=True)
        lab.migrate(state)
        env = dict(os.environ, RA4C3_STATE=str(state), RA4A_P2B1_EVIDENCE_DIR=str(output))
        argv = [sys.executable, '-B', '-m', 'pytest', '-q', '--import-mode=importlib',
                '-o', 'consider_namespace_packages=true',
                '-p', 'integration.ra4c3.pytest_adapter',
                '-p', 'integration.ra4a.p2b1_plugin', '--confcutdir=integration/ra4a/p2b1',
                'integration/ra4a/p2b1/cases.py', 'integration/ra4a/p2b1/parity_cases.py',
                '--basetemp=' + str(lab.OWN / 'runtime' / ('temp-' + output.name)),
                '--junitxml=' + str(output / 'tests.xml')]
        records = []

        def execute(stage, folder, command):
            folder.mkdir(exist_ok=True)
            result = subprocess.run(command, cwd=lab.ROOT,
                env=dict(env, RA4A_EVIDENCE_DIR=str(folder),
                         RA4A_P2A_EVIDENCE_DIR=str(folder), RA4A_P2B1_EVIDENCE_DIR=str(folder)),
                capture_output=True)
            for name, raw in [('stdout.log', result.stdout), ('stderr.log', result.stderr)]:
                (folder / name).write_bytes(raw)
            row = {'stage': stage, 'argv': command, 'returncode': result.returncode,
                   'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
                   'stderr_sha256': hashlib.sha256(result.stderr).hexdigest()}
            records.append(row)
            receipt = {'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=lab.ROOT).decode().strip(),
                       'python': sys.version, 'commands': records,
                       'returncode': result.returncode, 'identity_requested': include_identity,
                       'expected_stages': ['p2b1', 'identity-crypto', 'identity-pg'] if include_identity else ['p2b1'],
                       'ui_write_integration': False, 'synthetic_only': True}
            (output / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
            print(json.dumps(row), flush=True)
            if result.returncode:
                print(result.stdout.decode(errors='replace')[-6000:])
                print(result.stderr.decode(errors='replace')[-1500:])
                raise RuntimeError('ORIGINAL_ACCEPTED_SUITE_RED_' + stage)

        execute('p2b1', output, argv)
        if include_identity:
            # Accepted B2 suites remain unchanged and separate from the C3 UI.
            for stage, cases, plugins, confcut in (
                ('identity-crypto', ['tests/identity/crypto_cases.py'], [], 'tests/identity'),
                ('identity-pg', ['integration/ra4a/p2b2a/cases.py'],
                 ['-p', 'integration.ra4a.p2b1_plugin'], 'integration/ra4a/p2b2a'),
            ):
                folder = output / stage
                execute(stage, folder, [sys.executable, '-B', '-m', 'pytest', '-q',
                    '--import-mode=importlib', '-o', 'consider_namespace_packages=true',
                    '-p', 'integration.ra4c3.pytest_adapter', *plugins,
                    '--confcutdir=' + confcut, *cases,
                    '--basetemp=' + str(lab.OWN / 'runtime' / ('temp-' + output.name + '-' + stage)),
                    '--junitxml=' + str(folder / 'tests.xml')])
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
    parser.add_argument('--include-identity', action='store_true',
                        help='Also replay accepted B2 crypto and PG tests without UI wiring')
    args = parser.parse_args()
    run(args.output, include_identity=args.include_identity)
