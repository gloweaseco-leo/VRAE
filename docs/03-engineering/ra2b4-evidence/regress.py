"""Run unchanged engineering gates and historical offline replays, preserving raw exits."""
import json
from pathlib import Path
import subprocess
import sys

out = Path(__file__).resolve().parent / sys.argv[1]
out.mkdir(exist_ok=True)
commands = [
    (['-m', 'compileall', '-q', 'vrae'], 0),
    (['-m', 'ruff', 'check', 'vrae', 'tests', 'scripts/verify_ra2b4.py', '--select', 'E4,E7,E9,F'], 0),
    (['-m', 'mypy', 'vrae'], 0),
    (['-m', 'pytest', '-q'], 0),
    (['-m', 'pip', 'check'], 0),
    *[([f'scripts/verify_{stage}.py'], 0) for stage in
      ('ra2a', 'ra2b0', 'ra2b1', 'ra2b2', 'ra2b3', 'ra2b4', 'ra2c0', 'ra2c1', 'ra2d0', 'ra2d1')],
    (['scripts/verify_ra2d1.py', '--reviews',
      'docs/03-engineering/ra2d1-review/SIMULATED_NOT_HUMAN_GOLD.json'], 0),
    (['scripts/verify_ra2d1.py', '--reviews',
      'docs/03-engineering/ra2d1-review/negative-forged-gold.json'], 1),
]
results = []
for index, (args, expected) in enumerate(commands, 1):
    result = subprocess.run([sys.executable, *args], capture_output=True)
    (out / f'{index}.log').write_bytes(result.stdout + result.stderr)
    results.append({'command': [sys.executable, *args], 'exit_code': result.returncode,
                    'expected_exit_code': expected, 'matches': result.returncode == expected})
    print(index, args, result.returncode, 'expected', expected, flush=True)
(out / 'summary.json').write_text(json.dumps({
    'python': sys.version, 'source_root': str(Path.cwd()),
    'results': results}, indent=2) + '\n', encoding='utf-8')
sys.exit(int(any(not r['matches'] for r in results)))
