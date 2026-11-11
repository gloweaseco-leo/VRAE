"""Offline sealed INFO-01 positive evidence -> private FindingPackage replay."""
import argparse
import base64
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.findings.info01_synthetic import BUILDER, EVALUATOR, diagnostic_input  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.findings import build_findings, FindingPackage  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--write-example', action='store_true', help='Write only the new synthetic example.')
args = parser.parse_args()
path = root / 'tests/findings/fixtures/info01-private-package.json'
if args.write_example:
    pack, execution = diagnostic_input()
    pins = dict(expected_pack_ref=pack.ref, expected_execution_ref=execution['execution_ref'],
                expected_evaluator_version=EVALUATOR, expected_builder_version=BUILDER)
    package = build_findings(pack, execution, **pins)
    data = {'synthetic_only': True, **pins, 'expected_package_ref': package.ref,
            'document': pack.document,
            'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
            'finding_package': package.document}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')

data = json.loads(path.read_text(encoding='utf-8'))
assert data['synthetic_only'] is True
assert data['expected_builder_version'] == BUILDER and data['expected_evaluator_version'] == EVALUATOR
pack = EvidencePack.load(data['document'], {
    k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()
}, expected_ref=data['expected_pack_ref'])
pins = {k: data[k] for k in ('expected_pack_ref', 'expected_execution_ref',
                            'expected_evaluator_version', 'expected_builder_version')}
package = FindingPackage.load(data['finding_package'], pack, **pins,
                              expected_package_ref=data['expected_package_ref'])
doc = package.document
assert build_findings(pack, doc['rule_execution'], **pins).ref == package.ref
# Reproduce the same inputs with the fixed synthetic transport, without network access.
fresh_pack, fresh_execution = diagnostic_input()
assert fresh_pack.ref == pack.ref and fresh_execution == doc['rule_execution']
assert len(doc['checked_product_facts']) == 1 and len(doc['checked_positive_paths']) == 2
positive = doc['checked_product_facts'][0]['provenance']
assert positive['observation']['result'] == 'PASS'
citations = positive['citations']
assert [c['text'] for c in citations] == [
    'SV-40 flanged isolation valve', 'Body material', 'Stainless steel 316L',
    'Nominal pressure', 'PN 40 (4.0 MPa)', 'Nominal diameter', 'DN 50']
for citation in citations:
    resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
    element = citation['element']
    line = resolved['content'].decode('utf-8').splitlines()[element['line'] - 1]
    assert line[element['column']:].startswith(element['start_tag'] + citation['text'] + '</')
    assert citation['content_sha256'] == resolved['evidence']['content_sha256']
assert citations[0]['element']['line'] == 3
assert citations[4]['element']['line'] == 6 and citations[4]['element']['column'] == 29
issues = [i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION']
assert len(issues) == 1 and issues[0]['rule_id'] == 'CTA-02'
issue = issues[0]
assert issue['finding']['buyer_task'] == 'INQUIRE'
assert issue['provenance']['target_response']['http_status'] == 404
assert issue['provenance']['citations'][0]['raw_href'] == '/contact'
assert any(i['outcome'] == 'ACCESS_BLOCKED' for i in doc['items'])
assert all(i['finding']['evidence_ids'] == [] for i in doc['items']
           if i['finding']['kind'] == 'UNKNOWN')
assert doc['private'] is True and doc['shareable'] is False and doc['approval_status'] == 'NOT_APPROVED'
print(json.dumps({'status': 'VERIFIED_PRIVATE_SYNTHETIC_PRODUCT_EVIDENCE', **pins,
    'package_ref': package.ref, 'positive_product': positive,
    'separate_broken_href_finding': issue,
    'unknown_items': sum(i['finding']['kind'] == 'UNKNOWN' for i in doc['items']),
    'limits': doc['limitations']}, indent=2, sort_keys=True))
