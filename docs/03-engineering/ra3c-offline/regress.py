"""Run the unchanged gates and every historical sealed replay on one interpreter."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / '.checks' / sys.argv[1]
OUT.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env['PYTEST_ADDOPTS'] = ('--basetemp=' + (OUT / 'tmp').as_posix()
    + ' --junitxml=' + (OUT / 'full.xml').as_posix())
commands = [
    (['-m', 'compileall', '-q', 'vrae'], 0),
    (['-m', 'ruff', 'check', 'vrae', 'tests', 'scripts/verify_ra3c.py', '--select', 'E4,E7,E9,F'], 0),
    (['-m', 'mypy', 'vrae'], 0),
    (['-m', 'pytest', '-q'], 0),
    (['-m', 'pip', 'check'], 0),
    *[([f'scripts/verify_{stage}.py'], 0) for stage in
      ('ra2a', 'ra2b0', 'ra2b1', 'ra2b2', 'ra2b3', 'ra2b4', 'ra2b5', 'ra2b6',
       'ra2b6_execution', 'ra2c0', 'ra2c1', 'ra2c2', 'ra2c3', 'ra2d0', 'ra2d1',
       'ra3a', 'ra3b', 'ra3c')],
    (['scripts/verify_ra2d1.py', '--reviews',
      'docs/03-engineering/ra2d1-review/SIMULATED_NOT_HUMAN_GOLD.json'], 0),
    (['scripts/verify_ra2d1.py', '--reviews',
      'docs/03-engineering/ra2d1-review/negative-forged-gold.json'], 1),
]
results = []
for index, (args, expected) in enumerate(commands, 1):
    result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env, capture_output=True)
    (OUT / f'{index:02}.log').write_bytes(result.stdout + result.stderr)
    results.append({'command': [sys.executable, *args], 'exit_code': result.returncode,
                    'expected_exit_code': expected, 'matches': result.returncode == expected})
    print(index, args, result.returncode, 'expected', expected, flush=True)
(OUT / 'summary.json').write_text(json.dumps({'python': sys.version,
    'source_root': str(ROOT), 'results': results}, indent=2) + '\n', encoding='utf-8')
sys.exit(int(any(not r['matches'] for r in results)))
