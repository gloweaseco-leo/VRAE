"""Run the existing Python checks unchanged and preserve UTF-8 raw command output."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
target = Path(__file__).resolve().parent
version = f'{sys.version_info.major}{sys.version_info.minor}'
commands = [
    ['-m', 'compileall', '-q', 'vrae'],
    ['-m', 'ruff', 'check', 'vrae', 'tests', '--select', 'E4,E7,E9,F'],
    ['-m', 'mypy', 'vrae'], ['-m', 'pytest', '-q'], ['-m', 'pip', 'check'],
    ['scripts/verify_ra2a.py'], ['scripts/verify_ra2b0.py'],
    ['scripts/verify_ra2b1.py'], ['scripts/verify_ra2b2.py'],
]
results = []
for index, args in enumerate(commands):
    proc = subprocess.run([sys.executable, *args], cwd=root, capture_output=True)
    log = target / f'py{version}-{index}.txt'
    log.write_bytes(proc.stdout + proc.stderr)
    results.append({'command': [sys.executable, *args], 'exit_code': proc.returncode,
                    'log': log.name})
(target / f'py{version}-results.json').write_text(json.dumps({
    'python': sys.version, 'head_at_run': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'checks': results}, indent=2) + '\n', encoding='utf-8')
print(json.dumps(results, indent=2))
sys.exit(int(any(item['exit_code'] for item in results)))
