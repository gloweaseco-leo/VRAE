"""Offline synthetic example generation/replay, never starts a browser or network client."""
import argparse
import base64
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from vrae.evidence import EvidencePack, build_pack  # noqa: E402
from tests.evidence.synthetic import http, browser  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--write-example', action='store_true')
args = parser.parse_args()
path = root / 'tests/fixtures/evidence/combined.json'
if args.write_example:
    pack = build_pack([http(), browser(True)])
    data = {'synthetic_only': True, 'expected_pack_ref': pack.ref,
            'document': pack.document,
            'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
data = json.loads(path.read_text(encoding='utf-8'))
assert data['synthetic_only'] is True
objects = {k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()}
pack = EvidencePack.load(data['document'], objects, expected_ref=data['expected_pack_ref'])
assert pack.ref == build_pack([http(), browser(True)]).ref
for item in pack.document['evidence']:
    pack.resolve(item['evidence_ref'], expected_pack_ref=data['expected_pack_ref'])
print(json.dumps({'status': 'VERIFIED_SYNTHETIC_ONLY', 'pack_ref': pack.ref,
                  'sources': len(pack.document['sources']), 'evidence': len(pack.document['evidence']),
                  'blobs': len(pack.objects)}))
