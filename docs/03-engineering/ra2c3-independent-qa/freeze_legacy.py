"""Freeze only accepted baseline Git objects, never a candidate's self-reported pins."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = '4b5ebe689f048ba20d38354ae7c03d4bbaf37c6a'
paths = ('tests/fixtures/findings/industrial-diagnostic.json',
         'tests/findings/fixtures/info01-private-package.json',
         'tests/findings/fixtures/seo01-private-package.json')
fixtures = {}
for path in paths:
    data = json.loads(subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT))
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    fixtures[path] = {'canonical_fixture_sha256': hashlib.sha256(canonical).hexdigest(),
        'pack_ref': data['expected_pack_ref'], 'execution_ref': data['expected_execution_ref'],
        'package_ref': data['expected_package_ref']}
target = ROOT / 'tests/findings/fixtures/ra2c3_codex2_legacy_pins.json'
target.write_text(json.dumps({'baseline_sha': BASE, 'fixtures': fixtures}, sort_keys=True, indent=2) + '\n', encoding='utf-8')
print(json.dumps(fixtures, sort_keys=True, indent=2))
