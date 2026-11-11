"""Replay the private synthetic EvidencePack -> RuleExecution -> Finding chain."""
import argparse
import base64
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.findings.synthetic import diagnostic_input  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.findings import build_findings, FindingPackage  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--write-example', action='store_true')
args = parser.parse_args()
path = root / 'tests/fixtures/findings/industrial-diagnostic.json'
if args.write_example:
    pack, execution = diagnostic_input()
    package = build_findings(pack, execution, expected_pack_ref=pack.ref,
        expected_execution_ref=execution['execution_ref'], expected_evaluator_version='ra2b1-1.0.0')
    data = {'synthetic_only': True, 'expected_pack_ref': pack.ref,
        'expected_execution_ref': execution['execution_ref'], 'expected_evaluator_version': 'ra2b1-1.0.0',
        'expected_package_ref': package.ref, 'document': pack.document,
        'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
        'finding_package': package.document}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')

data = json.loads(path.read_text(encoding='utf-8'))
assert data['synthetic_only'] is True
pack = EvidencePack.load(data['document'], {
    k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()
}, expected_ref=data['expected_pack_ref'])
pins = {key: data[key] for key in ('expected_pack_ref', 'expected_execution_ref', 'expected_evaluator_version')}
package = FindingPackage.load(data['finding_package'], pack,
    **pins, expected_package_ref=data['expected_package_ref'])
assert package.ref == build_findings(pack, package.document['rule_execution'], **pins).ref
facts = [item for item in package.document['items'] if item['finding']['kind'] == 'OBSERVATION']
assert len(facts) == 1 and len(package.document['checked_positive_paths']) == 2
assert any(item['outcome'] == 'ACCESS_BLOCKED' for item in package.document['items'])
print(json.dumps({'status': 'VERIFIED_PRIVATE_SYNTHETIC_DIAGNOSTIC', 'package_ref': package.ref,
    **pins, 'issue': {'finding_id': facts[0]['finding']['finding_id'],
        'buyer_task': facts[0]['finding']['buyer_task'],
        'source': facts[0]['provenance']['source_page']['url'],
        'target': facts[0]['provenance']['target_response']['url'],
        'http_status': facts[0]['provenance']['target_response']['http_status']},
    'unknown_items': sum(item['finding']['kind'] == 'UNKNOWN' for item in package.document['items']),
    'private': package.document['private'], 'approval_status': package.document['approval_status']}, sort_keys=True))
