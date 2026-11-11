from copy import deepcopy
from dataclasses import FrozenInstanceError
import base64
import json
from pathlib import Path

import pytest

from vrae.domain.contracts import validate_contract
from vrae.domain.evidence import validate_evidence_graph
from vrae.domain.errors import DomainError
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError, EvidencePack
from vrae.findings import build_findings, FindingError, FindingPackage
from tests.rules.test_journey import journey_pack, run
from .synthetic import diagnostic_input


def build(pack, execution):
    return build_findings(pack, execution, expected_pack_ref=pack.ref,
        expected_execution_ref=execution['execution_ref'], expected_evaluator_version='ra2b1-1.0.0')


def test_one_actual_broken_link_not_a_whole_site_or_blocked_failure():
    pack, execution = diagnostic_input()
    package = build(pack, execution)
    doc = package.document
    facts = [item for item in doc['items'] if item['finding']['kind'] == 'OBSERVATION']
    assert len(facts) == 1
    issue = facts[0]
    assert issue['finding']['buyer_task'] == 'INQUIRE'
    assert issue['finding']['severity'] is None
    assert issue['provenance']['target_response']['url'] == 'https://example.org/contact'
    assert issue['provenance']['target_response']['http_status'] == 404
    assert issue['provenance']['citations'][0]['raw_href'] == '/contact'
    assert any(item['outcome'] == 'ACCESS_BLOCKED' and item['finding']['kind'] == 'UNKNOWN'
               for item in doc['items'])
    assert len(doc['checked_positive_paths']) == 2
    assert doc['private'] is True and doc['approval_status'] == 'NOT_APPROVED'
    assert doc['shareable'] is False
    for item in doc['items']:
        validate_contract('Finding', item['finding'])
        if item['finding']['kind'] == 'UNKNOWN':
            assert item['finding']['evidence_ids'] == []
    assert package.ref == build(pack, execution).ref


@pytest.mark.parametrize('mutation', ['target_status', 'missing_response', 'href', 'evidence',
                                    'tenant', 'version'])
def test_tampered_rule_execution_rejected_before_finding(mutation):
    pack, original = diagnostic_input()
    execution = deepcopy(original)
    row = next(row for rule in execution['executions'] for row in rule['observations']
               if row['observation']['result'] == 'FAIL_WITH_EVIDENCE')
    if mutation == 'target_status':
        row['target_response']['http_status'] = 200
    elif mutation == 'missing_response':
        del row['target_response']
    elif mutation == 'href':
        row['citations'][0]['raw_href'] = '/invented'
    elif mutation == 'evidence':
        row['observation']['evidence_ids'] = ['ev-' + '0' * 64]
    elif mutation == 'tenant':
        row['observation']['tenant_id'] = 'other-tenant'
    else:
        execution['evaluator_version'] = 'ra2b0-1.0.0'
    with pytest.raises(FindingError):
        build(pack, execution)


def load(document, pack, execution):
    return FindingPackage.load(document, pack, expected_pack_ref=pack.ref,
        expected_execution_ref=execution['execution_ref'], expected_evaluator_version='ra2b1-1.0.0',
        expected_package_ref=document['package_ref'])


def reseal(document):
    document['package_ref'] = 'fp-' + document_hash({
        k: v for k, v in document.items() if k != 'package_ref'})
    return document


def test_exact_native_id_bridge_uses_unmodified_ra0_guard():
    pack, execution = diagnostic_input()
    package = build(pack, execution)
    item = next(i for i in package.document['items'] if i['finding']['kind'] == 'OBSERVATION')
    bridge = item['guard_bridge']
    mapping = bridge['evidence_mapping'][0]
    resolved = pack.resolve(mapping['evidence_ref'], expected_pack_ref=pack.ref)
    assert bridge['native_evidence'] == resolved['source_record']
    assert item['finding']['evidence_ids'] == [resolved['source_record']['evidence_id']]
    assert bridge['guard_observation']['evidence_ids'] == item['finding']['evidence_ids']
    assert bridge['native_snapshot']['snapshot_id'] == mapping['native_snapshot_id']
    validate_evidence_graph(bridge['native_snapshot'], bridge['native_evidence'],
                            bridge['guard_observation'], item['finding'])
    fake = deepcopy(item['finding'])
    fake['evidence_ids'] = [mapping['evidence_ref']]  # An EP ref is not a native Evidence ID.
    with pytest.raises(DomainError):
        validate_evidence_graph(bridge['native_snapshot'], bridge['native_evidence'],
                                bridge['guard_observation'], fake)
    assert load(package.document, pack, execution).ref == package.ref


@pytest.mark.parametrize('stage', [1, 2, 3])
@pytest.mark.parametrize('status', [404, 410])
def test_each_enabled_rule_can_supply_a_bounded_fact(stage, status):
    pack = journey_pack(stage, status)
    execution = run(pack)
    doc = build(pack, execution).document
    facts = [item for item in doc['items'] if item['finding']['kind'] == 'OBSERVATION']
    assert len(facts) == 1
    assert facts[0]['rule_id'] == {1: 'DISC-01', 2: 'DISC-02', 3: 'CTA-02'}[stage]
    assert facts[0]['provenance']['target_response']['http_status'] == status


@pytest.mark.parametrize('gap', ['no_raw', 'unvisited', '403', 'waf', 'robots', 'pass'])
def test_no_missing_or_blocked_evidence_becomes_a_defect(gap):
    if gap == 'no_raw':
        pack = journey_pack(retained=False)
    elif gap == 'unvisited':
        pack = journey_pack(max_pages=2)
    elif gap == '403':
        pack = journey_pack(3, 403)
    elif gap in ('waf', 'robots'):
        pack = journey_pack(3, blocked=gap)
    else:
        pack = journey_pack()
    doc = build(pack, run(pack)).document
    assert all(item['finding']['kind'] == 'UNKNOWN' for item in doc['items'])
    assert all(item['finding']['evidence_ids'] == [] for item in doc['items'])
    if gap in ('403', 'waf', 'robots'):
        assert any(item['outcome'] == 'ACCESS_BLOCKED' for item in doc['items'])


@pytest.mark.parametrize('mutation', ['missing_response', 'target_status', 'trace', 'source_ref',
    'snapshot', 'href', 'native_mapping', 'statement', 'severity', 'approved', 'public',
    'shareable', 'unknown_fact', 'coverage', 'duplicate', 'positive_defect'])
def test_recomputed_wrapper_cannot_hide_invalid_finding_provenance(mutation):
    pack, execution = diagnostic_input()
    doc = build(pack, execution).document
    item = next(i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION')
    if mutation == 'missing_response':
        del item['provenance']['target_response']
    elif mutation == 'target_status':
        item['provenance']['target_response']['http_status'] = 200
    elif mutation == 'trace':
        item['provenance']['target_response']['redirect_trace'] = []
    elif mutation == 'source_ref':
        item['provenance']['target_response']['source_ref'] = 'src-' + '0' * 64
    elif mutation == 'snapshot':
        item['provenance']['target_response']['snapshot_ref'] = 'page-' + '0' * 64
    elif mutation == 'href':
        item['provenance']['citations'][0]['raw_href'] = '/fabrication'
    elif mutation == 'native_mapping':
        item['guard_bridge']['evidence_mapping'][0]['native_evidence_id'] = 'fake-evidence'
    elif mutation == 'statement':
        item['finding']['statement'] = 'The entire site cannot receive inquiries and loses revenue'
    elif mutation == 'severity':
        item['finding']['severity'] = 'HIGH'
    elif mutation == 'approved':
        doc['approval_status'] = 'APPROVED'
    elif mutation == 'public':
        doc['private'] = False
    elif mutation == 'shareable':
        doc['shareable'] = True
    elif mutation == 'unknown_fact':
        next(i for i in doc['items'] if i['finding']['kind'] == 'UNKNOWN')['finding']['kind'] = 'OBSERVATION'
    elif mutation == 'coverage':
        doc['coverage'] = []
    elif mutation == 'duplicate':
        doc['items'].append(deepcopy(item))
    else:
        doc['checked_positive_paths'][0]['defect'] = True
    with pytest.raises(FindingError):
        load(reseal(doc), pack, execution)


def test_tampered_embedded_execution_is_not_a_proof_even_with_fresh_hashes():
    pack, execution = diagnostic_input()
    doc = build(pack, execution).document
    embedded = doc['rule_execution']
    row = next(r for e in embedded['executions'] for r in e['observations']
               if r['observation']['result'] == 'FAIL_WITH_EVIDENCE')
    del row['target_response']
    embedded['execution_ref'] = 'rx-' + document_hash({k: v for k, v in embedded.items() if k != 'execution_ref'})
    doc['execution_ref'] = embedded['execution_ref']
    with pytest.raises(FindingError):
        load(reseal(doc), pack, embedded)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_pack_scope_drift_rejected_before_build(field):
    pack, execution = diagnostic_input()
    doc = pack.document
    doc[field] = 2 if field == 'policy_version' else 'other-scope'
    doc['pack_ref'] = 'ep-' + document_hash({k: v for k, v in doc.items() if k != 'pack_ref'})
    tampered = EvidencePack(json.dumps(doc).encode(), tuple(sorted(pack.objects.items())))
    with pytest.raises(FindingError):
        build(tampered, execution)


def test_cross_site_sources_remain_rejected_and_not_findings():
    from tests.evidence.synthetic import http
    from tests.evidence.test_site_coherence import relocate_browser
    from vrae.evidence import build_pack
    with pytest.raises(EvidenceError):
        build_pack([http(), relocate_browser(True)])


def test_package_is_immutable_and_detached_and_requires_all_trusted_pins():
    pack, execution = diagnostic_input()
    package = build(pack, execution)
    original = package.document
    package.document['items'].clear()
    execution['executions'].clear()
    assert package.document == original
    with pytest.raises((FrozenInstanceError, AttributeError)):
        package._payload = b'changed'
    with pytest.raises(FindingError):
        FindingPackage(bytearray(b'{}'))
    with pytest.raises(FindingError):
        FindingPackage.load(original['items'][0]['finding'], pack, expected_pack_ref=pack.ref,
            expected_execution_ref=original['execution_ref'], expected_evaluator_version='ra2b1-1.0.0',
            expected_package_ref=package.ref)
    for key, value in [('expected_pack_ref', None), ('expected_execution_ref', ''),
                       ('expected_evaluator_version', 'ra2b0-1.0.0')]:
        pins = dict(expected_pack_ref=pack.ref, expected_execution_ref=original['execution_ref'],
                    expected_evaluator_version='ra2b1-1.0.0')
        pins[key] = value
        with pytest.raises(FindingError):
            build_findings(pack, original['rule_execution'], **pins)
    with pytest.raises(FindingError):
        package.verify(pack, expected_pack_ref=pack.ref, expected_execution_ref=original['execution_ref'],
            expected_evaluator_version='ra2b1-1.0.0', expected_package_ref='fp-' + '0' * 64)


def test_oversize_input_is_refused_and_two_inputs_get_distinct_immutable_refs():
    pack, execution = diagnostic_input()
    first = build(pack, execution)
    changed = journey_pack(3, 410)
    second = build(changed, run(changed))
    assert second.ref != first.ref
    fake = deepcopy(execution)
    fake['padding'] = 'x' * 8_000_001
    with pytest.raises(FindingError):
        build(pack, fake)


def test_actual_legacy_execution_and_wrong_execution_pin_rejected():
    from vrae.rules import execute
    pack, execution = diagnostic_input()
    legacy = execute(pack, expected_pack_ref=pack.ref)
    with pytest.raises(FindingError):
        build(pack, legacy)
    with pytest.raises(FindingError):
        build_findings(pack, execution, expected_pack_ref=pack.ref,
            expected_execution_ref='rx-' + '0' * 64, expected_evaluator_version='ra2b1-1.0.0')


def test_browser_without_http_href_stays_unknown_with_no_fabricated_native_ids():
    from tests.evidence.synthetic import browser
    from vrae.evidence import build_pack
    pack = build_pack([browser(True)])
    doc = build(pack, run(pack)).document
    assert doc['checked_positive_paths'] == []
    assert all(item['finding']['kind'] == 'UNKNOWN' and item['finding']['evidence_ids'] == []
               for item in doc['items'])
    assert all(item['guard_bridge']['kind'] == 'UNKNOWN_RUN_CONTEXT'
               and item['guard_bridge']['evidence_mapping'] == [] for item in doc['items'])


def test_sealed_diagnostic_example_independently_replays():
    data = json.loads((Path(__file__).parents[1] /
        'fixtures/findings/industrial-diagnostic.json').read_text(encoding='utf-8'))
    pack = EvidencePack.load(data['document'], {
        k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()
    }, expected_ref=data['expected_pack_ref'])
    package = FindingPackage.load(data['finding_package'], pack,
        expected_pack_ref=data['expected_pack_ref'], expected_execution_ref=data['expected_execution_ref'],
        expected_evaluator_version=data['expected_evaluator_version'], expected_package_ref=data['expected_package_ref'])
    assert package.ref == build(pack, package.document['rule_execution']).ref
