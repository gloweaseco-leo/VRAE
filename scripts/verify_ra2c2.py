"""Replay one sealed private SEO/product/path package and its separate contact defect."""
import argparse
import base64
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.findings.seo01_synthetic import BUILDER, EVALUATOR, diagnostic_input, pins  # noqa: E402
from vrae.domain.evidence import validate_evidence_graph  # noqa: E402
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.findings import build_findings, FindingPackage  # noqa: E402
from vrae.rules import execute  # noqa: E402

path = root / 'tests/findings/fixtures/seo01-private-package.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-example', action='store_true', help='Write only the new SEO package fixture.')
    args = parser.parse_args()
    if args.write_example:
        pack, execution = diagnostic_input()
        package = build_findings(pack, execution, **pins(pack, execution))
        historical = []
        for builder, evaluator in [('ra2c0-1.0.0', 'ra2b1-1.0.0'), ('ra2c1-1.0.0', 'ra2b3-1.0.0')]:
            old = execute(pack, expected_pack_ref=pack.ref, evaluator_version=evaluator)
            legacy = build_findings(pack, old, expected_pack_ref=pack.ref,
                expected_execution_ref=old['execution_ref'], expected_evaluator_version=evaluator,
                expected_builder_version=builder)
            historical.append({'builder_version': builder, 'evaluator_version': evaluator,
                               'execution_ref': old['execution_ref'], 'package_ref': legacy.ref})
        data = {'synthetic_only': True, **pins(pack, execution), 'expected_package_ref': package.ref,
            'document': pack.document,
            'objects_base64': {k: base64.b64encode(v).decode('ascii') for k, v in pack.objects.items()},
            'finding_package': package.document, 'historical_refs_on_this_new_pack': historical}
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['synthetic_only'] is True
    assert data['expected_builder_version'] == BUILDER and data['expected_evaluator_version'] == EVALUATOR
    pack = EvidencePack.load(data['document'], {k: base64.b64decode(v, validate=True)
        for k, v in data['objects_base64'].items()}, expected_ref=data['expected_pack_ref'])
    expected = {k: data[k] for k in ('expected_pack_ref', 'expected_execution_ref',
                                    'expected_evaluator_version', 'expected_builder_version')}
    package = FindingPackage.load(data['finding_package'], pack, **expected,
                                  expected_package_ref=data['expected_package_ref'])
    doc = package.document
    fresh_pack, fresh_execution = diagnostic_input()
    assert fresh_pack.ref == pack.ref and fresh_execution == doc['rule_execution']
    assert build_findings(pack, fresh_execution, **expected).ref == package.ref
    for old in data['historical_refs_on_this_new_pack']:
        execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version=old['evaluator_version'])
        assert execution['execution_ref'] == old['execution_ref']
        assert build_findings(pack, execution, expected_pack_ref=pack.ref,
            expected_execution_ref=old['execution_ref'], expected_evaluator_version=old['evaluator_version'],
            expected_builder_version=old['builder_version']).ref == old['package_ref']
    assert len(doc['checked_seo_signals']) == len(doc['checked_product_facts']) == 1
    assert len(doc['checked_positive_paths']) == 2
    seo = doc['checked_seo_signals'][0]['provenance']
    assert seo['seo_signals']['title']['value'] == 'SV industrial valves & components'
    assert seo['seo_signals']['canonical']['value'] == 'https://example.org/'
    assert seo['seo_signals']['robots']['status'] == seo['seo_signals']['sitemap']['status'] == 'UNKNOWN'
    for citation in seo['citations']:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        text, pos = resolved['content'].decode('utf-8-sig'), citation['element']
        assert text[pos['character_start']:pos['character_end']] == pos['raw_element']
        assert text.splitlines()[pos['line'] - 1][pos['column']:].startswith(pos['raw_element'])
        assert citation['content_sha256'] == resolved['evidence']['content_sha256']
    defects = [i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION']
    assert len(defects) == 1 and defects[0]['rule_id'] == 'CTA-02'
    issue = defects[0]
    assert issue['provenance']['target_response']['http_status'] == 404
    assert issue['provenance']['citations'][0]['raw_href'] == '/contact'
    bridge = issue['guard_bridge']
    validate_evidence_graph(bridge['native_snapshot'], bridge['native_evidence'],
                            bridge['guard_observation'], issue['finding'])
    unknowns = [i for i in doc['items'] if i['finding']['kind'] == 'UNKNOWN']
    assert {'UNKNOWN', 'ACCESS_BLOCKED'} == {i['outcome'] for i in unknowns}
    assert all(i['finding']['evidence_ids'] == [] for i in unknowns)
    assert doc['private'] is True and doc['shareable'] is False and doc['approval_status'] == 'NOT_APPROVED'
    print(json.dumps({'status': 'VERIFIED_PRIVATE_SYNTHETIC_SEO_PRODUCT_PATH_EVIDENCE', **expected,
        'package_ref': package.ref, 'checked_seo_signals': doc['checked_seo_signals'],
        'product_fact_groups': len(doc['checked_product_facts']),
        'positive_path_groups': len(doc['checked_positive_paths']), 'separate_broken_contact': issue,
        'unknown_items': len(unknowns), 'limits': doc['limitations'],
        'historical_refs_on_this_new_pack': data['historical_refs_on_this_new_pack']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
