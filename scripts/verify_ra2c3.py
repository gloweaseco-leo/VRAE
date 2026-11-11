"""Offline version-pinned private TRUST source facts and contact-response status matrix."""
import argparse
import base64
import hashlib
from html import unescape
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.findings.ra2c3_synthetic import BUILDER, EVALUATOR, diagnostic_input, pins  # noqa: E402
from vrae.domain.evidence import validate_evidence_graph  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.findings import build_findings, FindingPackage  # noqa: E402
from vrae.rules import execute  # noqa: E402

path = root / 'tests/findings/fixtures/ra2c3-private-packages.json'
CASES = [('positive-contact-200', 200, 'PASS', 0), ('broken-contact-404', 404, 'UNKNOWN', 1),
         ('broken-contact-410', 410, 'UNKNOWN', 1), ('blocked-contact-403', 403, 'ACCESS_BLOCKED', 0),
         ('unknown-contact-500', 500, 'UNKNOWN', 0)]


def check(case):
    expected = {k: case[k] for k in ('expected_pack_ref', 'expected_execution_ref',
                                    'expected_evaluator_version', 'expected_builder_version')}
    assert expected['expected_builder_version'] == BUILDER and expected['expected_evaluator_version'] == EVALUATOR
    pack = EvidencePack.load(case['document'], {k: base64.b64decode(v, validate=True)
        for k, v in case['objects_base64'].items()}, expected_ref=case['expected_pack_ref'])
    package = FindingPackage.load(case['finding_package'], pack, **expected,
                                  expected_package_ref=case['expected_package_ref'])
    doc = package.document
    fresh_pack, fresh_execution = diagnostic_input(contact_status=case['contact_status'])
    assert fresh_pack.ref == pack.ref and fresh_execution == doc['rule_execution']
    assert build_findings(pack, fresh_execution, **expected).ref == package.ref
    trust = next(r['observations'][0] for r in fresh_execution['executions'] if r['rule_id'] == 'TRUST-01')
    assert trust['observation']['result'] == case['expected_trust_result']
    for citation in trust['citations']:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        text, pos = resolved['content'].decode('utf-8'), citation['element']
        offset = sum(len(s) + 1 for s in text.split('\n')[:pos['line'] - 1]) + pos['column']
        assert text[offset:].startswith(citation['raw_element'])
        assert unescape(citation['raw_element'].split('>', 1)[1].rsplit('</', 1)[0]) == citation['text']
        assert hashlib.sha256(resolved['content']).hexdigest() == citation['content_sha256']
    assert len(doc['checked_seo_signals']) == len(doc['checked_product_facts']) == 1
    defects = [i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION']
    assert len(defects) == case['expected_defects']
    if defects:
        issue = defects[0]
        assert issue['rule_id'] == 'CTA-02'
        assert issue['provenance']['target_response']['http_status'] == case['contact_status']
        assert issue['provenance']['citations'][0]['raw_href'] == '/contact'
        bridge = issue['guard_bridge']
        validate_evidence_graph(bridge['native_snapshot'], bridge['native_evidence'],
                                bridge['guard_observation'], issue['finding'])
    if case['expected_trust_result'] == 'PASS':
        assert len(doc['checked_trust_source_facts']) == 1 and len(doc['checked_positive_paths']) == 3
        assert doc['checked_trust_source_facts'][0]['provenance'] == trust
    else:
        assert doc['checked_trust_source_facts'] == []
        item = next(i for i in doc['items'] if i['rule_id'] == 'TRUST-01')
        assert item['finding']['kind'] == 'UNKNOWN' and item['finding']['evidence_ids'] == []
        assert item['provenance'] == trust
    assert all(i['finding']['evidence_ids'] == [] for i in doc['items'] if i['finding']['kind'] == 'UNKNOWN')
    assert doc['private'] is True and doc['shareable'] is False and doc['approval_status'] == 'NOT_APPROVED'
    return {'case': case['name'], **expected, 'package_ref': package.ref,
        'trust_result': case['expected_trust_result'], 'trust_sources': trust['source_pages'],
        'trust_positive_groups': len(doc['checked_trust_source_facts']),
        'seo_positive_groups': len(doc['checked_seo_signals']),
        'product_positive_groups': len(doc['checked_product_facts']),
        'path_positive_groups': len(doc['checked_positive_paths']), 'captured_defects': defects,
        'limits': doc['limitations']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-example', action='store_true', help='Write only new C3 status-matrix fixtures.')
    args = parser.parse_args()
    if args.write_example:
        cases = []
        for name, status, trust, defects in CASES:
            pack, execution = diagnostic_input(contact_status=status)
            package = build_findings(pack, execution, **pins(pack, execution))
            cases.append({'name': name, 'contact_status': status, 'expected_trust_result': trust,
                'expected_defects': defects, **pins(pack, execution), 'expected_package_ref': package.ref,
                'document': pack.document,
                'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
                'finding_package': package.document})
        historical = []
        pack, _ = diagnostic_input()
        for builder, evaluator in [('ra2c0-1.0.0', 'ra2b1-1.0.0'), ('ra2c1-1.0.0', 'ra2b3-1.0.0'),
                                   ('ra2c2-1.0.0', 'ra2b4-1.0.0')]:
            execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version=evaluator)
            package = build_findings(pack, execution, expected_pack_ref=pack.ref,
                expected_execution_ref=execution['execution_ref'], expected_evaluator_version=evaluator,
                expected_builder_version=builder)
            historical.append({'builder_version': builder, 'evaluator_version': evaluator,
                'execution_ref': execution['execution_ref'], 'package_ref': package.ref})
        path.write_text(json.dumps({'synthetic_only': True, 'cases': cases,
            'historical_refs_on_positive_pack': historical}, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['synthetic_only'] is True and len(data['cases']) == len(CASES)
    results = [check(case) for case in data['cases']]
    pack, _ = diagnostic_input()
    for old in data['historical_refs_on_positive_pack']:
        execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version=old['evaluator_version'])
        assert execution['execution_ref'] == old['execution_ref']
        assert build_findings(pack, execution, expected_pack_ref=pack.ref,
            expected_execution_ref=old['execution_ref'], expected_evaluator_version=old['evaluator_version'],
            expected_builder_version=old['builder_version']).ref == old['package_ref']
    print(json.dumps({'status': 'VERIFIED_PRIVATE_SELF_DECLARED_SOURCE_FACTS_AND_STATUS_MATRIX',
        'same_capture_trust_pass_with_contact_defect': False,
        'scope_constraint': 'FROZEN_B6_TRUST_ABSTAINS_ON_ANY_RELEVANT_CONTACT_404_410',
        'cases': results, 'historical_refs_on_positive_pack': data['historical_refs_on_positive_pack']},
        sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
