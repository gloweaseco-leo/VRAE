"""Record Phase A tests and unchanged accepted replays without resealing history."""
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
label = sys.argv[1] if len(sys.argv) == 2 else f'python{sys.version_info.major}{sys.version_info.minor}'
if not label.replace('-', '').isalnum():
    raise ValueError('Invalid evidence directory')
target = Path(__file__).resolve().parent / label
target.mkdir(exist_ok=True)
commands = [
    ['-c', 'import vrae.rules.trust01 as t; print(t.__file__)'],
    ['-m', 'compileall', '-q', 'vrae'],
    ['-m', 'ruff', 'check', 'vrae', 'tests', '--select', 'E4,E7,E9,F'],
    ['-m', 'mypy', 'vrae'], ['-m', 'pytest', '-q', 'tests/rules/test_trust01.py'],
    ['-m', 'pytest', '-q'], ['-m', 'pip', 'check'],
    *[[f'scripts/verify_{name}.py'] for name in
      ('ra2a', 'ra2b0', 'ra2b1', 'ra2b2', 'ra2b3', 'ra2b5', 'ra2b6', 'ra2c0', 'ra2c1', 'ra2d0', 'ra2d1')],
]
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
results = []
for index, args in enumerate(commands, 1):
    proc = subprocess.run([sys.executable, *args], cwd=root, capture_output=True)
    log = f'{index}.log'
    (target / log).write_bytes(proc.stdout + proc.stderr)
    results.append({'command': [sys.executable, *args], 'exit_code': proc.returncode, 'log': log})
    print(f'{index}: exit={proc.returncode} {args}', flush=True)
(target / 'summary.json').write_text(json.dumps({
    'python': sys.version, 'root': str(root), 'head_at_run': head, 'phase': 'PREP_ONLY',
    'trust01_enabled': False, 'development_base': 'a55b362cad7147b2c8da31a7842f6d4f36eba5fa',
    'checks': results,
}, indent=2) + '\n', encoding='utf-8')
sys.exit(int(any(item['exit_code'] for item in results)))
