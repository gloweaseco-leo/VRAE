"""Actual dual-runtime gates; raw bytes and JUnit are never rewritten into PASS."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = 'e40201bf399cc8c5d11a708fcbe33c31f01e67b2'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()


def main():
    run = HERE / 'runs' / git('rev-parse', 'HEAD') / ('py' + str(sys.version_info.minor))
    run.mkdir(parents=True, exist_ok=False)
    commands = [
        ('compile', ['-m', 'compileall', '-q', 'vrae']),
        ('ruff', ['-m', 'ruff', 'check', 'vrae', 'tests', '--select', 'E4,E7,E9,F']),
        ('mypy', ['-m', 'mypy', 'vrae']),
        ('reviewing', ['-m', 'pytest', '-q', 'tests/reviewing', '-o', 'junit_family=legacy',
                       '--junitxml=' + str(run / 'reviewing.xml')]),
        ('full', ['-m', 'pytest', '-q', '-o', 'junit_family=legacy',
                  '--junitxml=' + str(run / 'full.xml')]),
        ('pip', ['-m', 'pip', 'check']),
        ('scenarios', [str(HERE / 'scenarios.py'), str(run / 'scenarios.json')]),
    ]
    if '--targeted' in sys.argv:
        # Explicit final-source local stage. Complete default full regressions
        # run in both new hosted Python jobs and original isolated HTTP CI.
        commands = [(name, argv) for name, argv in commands if name != 'full']
    record = {'head': git('rev-parse', 'HEAD'), 'base': BASE, 'python': sys.version,
              'mode': 'FINAL_TARGETED_FULL_IN_HOSTED_CI' if '--targeted' in sys.argv else 'LOCAL_FULL',
              'executable': sys.executable, 'tracked_diff_at_start': git('diff', '--name-only', 'HEAD'),
              'commands': []}
    for name, args in commands:
        start = time.monotonic()
        result = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True)
        (run / (name + '.stdout.log')).write_bytes(result.stdout)
        (run / (name + '.stderr.log')).write_bytes(result.stderr)
        row = {'name': name, 'argv': [sys.executable, *args], 'exit': result.returncode,
               'elapsed_seconds': time.monotonic() - start,
               'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
               'stderr_sha256': hashlib.sha256(result.stderr).hexdigest()}
        if name in ('reviewing', 'full') and (run / (name + '.xml')).exists():
            suite = ET.parse(run / (name + '.xml')).getroot().find('testsuite')
            row['junit'] = dict(suite.attrib)
            row['junit'].pop('hostname', None)
        record['commands'].append(row)
        (run / 'summary.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(row), flush=True)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    print('ALL_LOCAL_GATES_PASS ' + str(run), flush=True)


if __name__ == '__main__':
    main()
