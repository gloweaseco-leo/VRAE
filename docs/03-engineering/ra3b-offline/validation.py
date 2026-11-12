"""Capture local real command outputs without changing shared interpreters or old files."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def history():
    accepted = '7e62bfcd1a900630b80b02850a0086cc950e4138'
    paths = subprocess.check_output(['git', 'ls-files', 'contracts/v1', 'vrae/findings',
        'vrae/rules', 'tests/findings/fixtures', 'tests/benchmark', 'tests/fixtures/rules',
        'docs/03-engineering/ra2d1-review'], cwd=ROOT, text=True).splitlines()
    result = {'accepted_main': accepted, 'byte_basis': 'ACCEPTED_GIT_BLOB_LF_CHECKOUT_NORMALIZED',
              'sha256': {p: hashlib.sha256(subprocess.check_output(
                  ['git', 'show', accepted + ':' + p], cwd=ROOT)).hexdigest() for p in paths}}
    (OUT / 'preserved-history.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n',
                                               encoding='utf-8')
    (ROOT / 'tests/interpretation/fixtures/preserved-history.json').write_text(
        json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    archive = ROOT / 'tests/interpretation/fixtures/fixed-replay.json'
    if archive.exists():
        data = json.loads(archive.read_text(encoding='utf-8'))
        data['historical_sha256'] = {p: result['sha256'][p] for p in data['historical_sha256']}
        archive.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def run():
    label = sys.argv[1]
    commands = [[sys.executable, '-m', 'compileall', '-q', 'vrae'],
                [sys.executable, '-m', 'ruff', 'check', 'vrae', 'tests', '--select', 'E4,E7,E9,F'],
                [sys.executable, '-m', 'mypy', 'vrae'],
                [sys.executable, '-m', 'pip', 'check'],
                [sys.executable, 'scripts/verify_ra3b.py']]
    results = []
    for index, command in enumerate(commands):
        start = time.monotonic()
        completed = subprocess.run(command, cwd=ROOT, capture_output=True)
        name = f'{label}-check-{index}.log'
        (OUT / name).write_bytes(completed.stdout + completed.stderr)
        results.append({'command': command[1:], 'exit_code': completed.returncode,
                        'seconds': round(time.monotonic() - start, 3), 'log': name})
    (OUT / f'{label}-checks.json').write_text(json.dumps({'python': sys.version,
        'checks': results}, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results))
    return int(any(r['exit_code'] for r in results))


if __name__ == '__main__':
    if sys.argv[1] == '--history':
        history()
    else:
        raise SystemExit(run())
