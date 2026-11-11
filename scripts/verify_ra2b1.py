"""Pinned offline HOME -> CATEGORY -> PRODUCT -> CONTACT path demonstration."""
import argparse
import base64
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.rules.test_journey import journey_pack  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.rules import execute, verify_execution  # noqa: E402

VERSION = 'ra2b1-1.0.0'
parser = argparse.ArgumentParser()
parser.add_argument('--write-example', action='store_true')
args = parser.parse_args()
path = root / 'tests/fixtures/rules/industrial-journey.json'
if args.write_example:
    pack = journey_pack()
    data = {'synthetic_only': True, 'expected_pack_ref': pack.ref,
        'document': pack.document,
        'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
        'expected_legacy_execution_ref': execute(pack, expected_pack_ref=pack.ref)['execution_ref'],
        'expected_execution': execute(pack, expected_pack_ref=pack.ref, evaluator_version=VERSION)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')

data = json.loads(path.read_text(encoding='utf-8'))
assert data['synthetic_only'] is True
pack = EvidencePack.load(data['document'], {
    k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()
}, expected_ref=data['expected_pack_ref'])
verify_execution(data['expected_execution'], pack, expected_pack_ref=data['expected_pack_ref'],
                 expected_evaluator_version=VERSION)
output = execute(pack, expected_pack_ref=data['expected_pack_ref'], evaluator_version=VERSION)
assert output == execute(pack, expected_pack_ref=data['expected_pack_ref'], evaluator_version=VERSION)
assert execute(pack, expected_pack_ref=pack.ref)['execution_ref'] == data['expected_legacy_execution_ref']
assert len(output['journeys']) == 1 and output['journeys'][0]['complete']
print(json.dumps({'status': 'VERIFIED_OFFLINE_STATIC_BUYER_PATH', 'pack_ref': pack.ref,
    'execution_ref': output['execution_ref'], 'evaluator_version': VERSION,
    'steps': [{'rule_id': step['rule_id'], 'source': step['source_page']['url'],
               'target': step['target_response']['url'], 'result': step['result']}
              for step in output['journeys'][0]['steps']]}, sort_keys=True))
