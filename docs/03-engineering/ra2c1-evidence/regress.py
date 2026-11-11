"""Record current-source checks and sealed offline replays; never reseal inputs."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
TARGET = Path(__file__).resolve().parent / 'latest-main' / f"python{sys.version_info.major}{sys.version_info.minor}"
TARGET.mkdir(parents=True, exist_ok=True)
commands = [
    ['-c', 'import vrae.findings.builder as b; print(b.__file__)'],
    ['-m', 'compileall', '-q', 'vrae'],
    ['-m', 'ruff', 'check', 'vrae', 'tests', '--select', 'E4,E7,E9,F'],
    ['-m', 'mypy', 'vrae'],
    ['-m', 'pytest', '-q', 'tests/findings/test_info01_integration.py'],
    ['-m', 'pytest', '-q'], ['-m', 'pip', 'check'],
    *[[f'scripts/verify_{name}.py'] for name in
      ('ra2a', 'ra2b0', 'ra2b1', 'ra2b2', 'ra2b3', 'ra2c0', 'ra2c1', 'ra2d0', 'ra2d1')],
]
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
results = []
for index, args in enumerate(commands, 1):
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True)
    log = f'{index}.log'
    (TARGET / log).write_bytes(proc.stdout + proc.stderr)
    results.append({'command': [sys.executable, *args], 'exit_code': proc.returncode, 'log': log})
    print(f'{index}: exit={proc.returncode} {args}', flush=True)
(TARGET / 'summary.json').write_text(json.dumps({
    'python': sys.version, 'root': str(ROOT), 'head_at_run': head,
    'base': 'acc5f7594dd5b96b1fda41dcf743f6c27bbac611', 'checks': results,
    'integration_main': '8f91dfd1783fa66c4827a6d2073c6237516de902',
}, indent=2) + '\n', encoding='utf-8')
sys.exit(int(any(item['exit_code'] for item in results)))
