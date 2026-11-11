"""Original engineering gates and five pinned offline demos; quality stays pending."""
import json
from pathlib import Path
import subprocess
import sys

out = Path(__file__).resolve().parent / sys.argv[1]
out.mkdir(exist_ok=True)
commands = [
    ['-m', 'compileall', '-q', 'vrae'],
    ['-m', 'ruff', 'check', 'vrae', 'tests', '--select', 'E4,E7,E9,F'],
    ['-m', 'mypy', 'vrae'],
    ['-m', 'pytest', '-q'],
    ['-m', 'pip', 'check'],
    ['scripts/verify_ra2a.py'],
    ['scripts/verify_ra2b0.py'],
    ['scripts/verify_ra2b1.py'],
    ['scripts/verify_ra2c0.py'],
    ['scripts/verify_ra2d0.py'],
]
results = []
for index, args in enumerate(commands, 1):
    result = subprocess.run([sys.executable, *args], capture_output=True)
    (out / f'{index}.log').write_bytes(result.stdout + result.stderr)
    results.append({'command': [sys.executable, *args], 'exit_code': result.returncode})
    print(index, args, result.returncode, flush=True)
(out / 'summary.json').write_text(json.dumps({
    'python': sys.version, 'source_root': str(Path.cwd()),
    'results': results}, indent=2) + '\n', encoding='utf-8')
sys.exit(int(any(r['exit_code'] for r in results)))
