"""Append-only integration evidence; preserve all frozen QA source and old runs."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
out = Path(__file__).resolve().parent / sys.argv[1]
out.mkdir(exist_ok=False)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
old = '10b09efad8d198fda83f23f747169e891a95f99f'
owned = subprocess.check_output(['git', 'diff', '--name-only',
    '4b5ebe689f048ba20d38354ae7c03d4bbaf37c6a', old], cwd=ROOT, text=True).splitlines()
for path in owned:
    # Git text normalization may change CRLF; hash the Git blob for identity.
    actual = subprocess.check_output(['git', 'hash-object', path], cwd=ROOT, text=True).strip()
    expected = subprocess.check_output(['git', 'rev-parse', f'{old}:{path}'], cwd=ROOT, text=True).strip()
    assert actual == expected, path
commands = [(['-m', 'compileall', '-q', 'vrae'], 0),
    (['-m', 'ruff', 'check', 'vrae', 'tests', '--select', 'E4,E7,E9,F'], 0),
    (['-m', 'mypy', 'vrae'], 0),
    (['-m', 'pytest', '-q', '--tb=short', '--junitxml=' + str(out / 'junit.xml')], 0),
    (['-m', 'pip', 'check'], 0),
    *[([f'scripts/verify_{stage}.py'], 0) for stage in
      ('ra2a', 'ra2b0', 'ra2b1', 'ra2b2', 'ra2b3', 'ra2b4', 'ra2b5', 'ra2b6',
       'ra2b6_execution', 'ra2c0', 'ra2c1', 'ra2c2', 'ra2c3', 'ra2d0', 'ra2d1')],
    (['scripts/verify_ra2d1.py', '--reviews',
      'docs/03-engineering/ra2d1-review/SIMULATED_NOT_HUMAN_GOLD.json'], 0),
    (['scripts/verify_ra2d1.py', '--reviews',
      'docs/03-engineering/ra2d1-review/negative-forged-gold.json'], 1)]
results = []
for index, (args, expected) in enumerate(commands, 1):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    (out / f'{index}.log').write_bytes(result.stdout + result.stderr)
    results.append(dict(command=[sys.executable, *args], started_utc=started,
        finished_utc=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode,
        expected_exit_code=expected, matches=result.returncode == expected))
    print(index, args, result.returncode, 'expected', expected, flush=True)
counts, qa = {}, []
if (out / 'junit.xml').exists():
    tree = ET.parse(out / 'junit.xml')
    counts = {key: sum(int(e.get(key, '0')) for e in tree.findall('.//testsuite'))
              for key in ('tests', 'failures', 'errors', 'skipped')}
    qa = [e for e in tree.findall('.//testcase')
          if e.get('classname') == 'tests.findings.test_ra2c3_independent_adversarial']
qa_pass = len(qa) == 139 and all(not any(e.find(k) is not None for k in ('failure', 'error', 'skipped')) for e in qa)
payload = dict(python=sys.version, source_root=str(ROOT), tested_head=head,
    base='91d408bcdbe0a6667c1e356723e3385465cdd6ae',
    frozen_original_files_verified=len(owned), counts=counts,
    frozen_qa_count=len(qa), frozen_qa_all_passed=qa_pass,
    test_sha256=hashlib.sha256((ROOT / 'tests/findings/test_ra2c3_independent_adversarial.py').read_bytes()).hexdigest(),
    results=results)
(out / 'summary.json').write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
sys.exit(int(not qa_pass or any(not r['matches'] for r in results)))
