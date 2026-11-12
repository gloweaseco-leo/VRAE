"""One-time hold preparation from accepted Git objects, never a runtime re-pin."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = 'a185f9ce7e67904f2c0aef854716ca9844144592'


def baseline(path):
    return json.loads(subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT))


sources = baseline('tests/reporting/fixtures/sources.json')
holds = baseline('tests/reporting/fixtures/caller-pins.json')
result = {'accepted_baseline': BASE, 'cases': {}}
for case in ('404', '200'):
    raw = json.dumps(sources[case], ensure_ascii=False, sort_keys=True,
                     separators=(',', ':'), allow_nan=False).encode('utf-8')
    result['cases'][case] = {'held': holds[case], 'source_sha256': hashlib.sha256(raw).hexdigest()}
path = ROOT / 'apps/operator_console/native-pins.json'
if path.exists():
    raise SystemExit('Refuse to replace existing holds; review any new baseline separately.')
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(path)
