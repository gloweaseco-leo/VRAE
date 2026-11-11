"""Offline industrial B2B EvidencePack -> Observation demo, never uses real sockets."""
import argparse
import base64
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.collection.test_pipeline import collect  # noqa: E402
from vrae.evidence import EvidencePack, build_pack  # noqa: E402
from vrae.rules import execute, verify_execution  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--write-example', action='store_true')
args = parser.parse_args()
path = root / 'tests/fixtures/rules/industrial-navigation.json'
if args.write_example:
    source, _ = collect({
        'https://example.org/': (200, {'content-type': 'text/html'},
            b'<html><body><h1>Synthetic industrial parts supplier</h1><nav>'
            b'<a href="/category/valves">Valve components</a>'
            b'<a href="/category/pumps">Pump components</a></nav></body></html>'),
        'https://example.org/category/valves': (200, {'content-type': 'text/html'},
            b'<html><h1>Valve components</h1><a href="/products/valve-v1">Valve V1</a></html>'),
        'https://example.org/category/pumps': (404, {'content-type': 'text/html'},
            b'<html>Not found</html>'),
        'https://example.org/products/valve-v1': (200, {'content-type': 'text/html'},
            b'<html><h1>Valve V1</h1><p>Synthetic stainless steel valve</p></html>'),
    }, retain_raw_html=True)
    pack = build_pack([source])
    data = {'synthetic_only': True, 'expected_pack_ref': pack.ref,
        'document': pack.document,
        'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
        'expected_execution': execute(pack, expected_pack_ref=pack.ref)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')

data = json.loads(path.read_text(encoding='utf-8'))
assert data['synthetic_only'] is True
pack = EvidencePack.load(data['document'], {
    k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()
}, expected_ref=data['expected_pack_ref'])
verify_execution(data['expected_execution'], pack, expected_pack_ref=data['expected_pack_ref'])
output = execute(pack, expected_pack_ref=data['expected_pack_ref'])
assert output == execute(pack, expected_pack_ref=data['expected_pack_ref'])
print(json.dumps({'status': 'VERIFIED_SYNTHETIC_RULE_EXECUTION',
    'pack_ref': pack.ref, 'execution_ref': output['execution_ref'],
    'rules': [{r['rule_id']: [row['observation']['result'] for row in r['observations']]}
              for r in output['executions']]}, sort_keys=True))
