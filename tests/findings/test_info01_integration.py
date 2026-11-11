"""Explicit new builder; product positives never become diagnostic defects."""
import base64
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from vrae.findings import build_findings, FindingError, FindingPackage
from vrae.collection.manifest import document_hash
from vrae.domain.evidence import validate_evidence_graph
from vrae.evidence import EvidencePack
from tests.rules.test_product_facts import product_pack
from vrae.rules import execute
from .info01_synthetic import BUILDER, EVALUATOR, diagnostic_input


def pins(pack, execution):
    return dict(expected_pack_ref=pack.ref, expected_execution_ref=execution['execution_ref'],
                expected_evaluator_version=EVALUATOR, expected_builder_version=BUILDER)


def build(pack, execution):
    return build_findings(pack, execution, **pins(pack, execution))


def reseal(document, key, prefix):
    document[key] = prefix + document_hash({k: v for k, v in document.items() if k != key})
    return document


def load(document, pack, execution):
    return FindingPackage.load(document, pack, **pins(pack, execution),
                               expected_package_ref=document['package_ref'])


@pytest.fixture(scope='module')
def demo():
    pack, execution = diagnostic_input()
    return pack, execution, build(pack, execution)


def test_explicit_product_positive_group():
    pack = product_pack()
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b3-1.0.0')
    package = build_findings(pack, execution, expected_pack_ref=pack.ref,
        expected_execution_ref=execution['execution_ref'],
        expected_evaluator_version='ra2b3-1.0.0', expected_builder_version='ra2c1-1.0.0')
    doc = package.document
    assert doc['builder_version'] == 'ra2c1-1.0.0'
    assert len(doc['checked_product_facts']) == 1
    assert all(item['rule_id'] != 'INFO-01' for item in doc['items'])
    assert all(item['rule_id'] != 'INFO-01' for item in doc['checked_positive_paths'])


def test_demo_preserves_exact_source_and_separate_native_broken_link(demo):
    pack, execution, package = demo
    doc = package.document
    product = doc['checked_product_facts'][0]
    assert len(doc['checked_product_facts']) == 1
    assert product['buyer_task'] == 'UNDERSTAND'
    row = product['provenance']
    assert row['observation']['result'] == 'PASS'
    assert row['source_page']['url'] == 'https://example.org/products/sv-40'
    assert [c['text'] for c in row['citations']] == [
        'SV-40 flanged isolation valve', 'Body material', 'Stainless steel 316L',
        'Nominal pressure', 'PN 40 (4.0 MPa)', 'Nominal diameter', 'DN 50']
    assert row['citations'][0]['element']['line'] == 3
    assert row['citations'][4]['element']['line'] == 6
    assert row['citations'][4]['element']['column'] == 29
    for citation in row['citations']:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        pos = citation['element']
        raw = resolved['content'].decode('utf-8')
        assert raw.splitlines()[pos['line'] - 1][pos['column']:].startswith(
            pos['start_tag'] + citation['text'] + '</')
        assert citation['content_sha256'] == resolved['evidence']['content_sha256']
        assert citation['url'] == row['source_page']['url']
        assert citation['observed_at'] == row['source_page']['observed_at']
    defects = [i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION']
    assert len(defects) == 1
    issue = defects[0]
    assert issue['rule_id'] == 'CTA-02' and issue['finding']['buyer_task'] == 'INQUIRE'
    assert issue['provenance']['target_response']['http_status'] == 404
    assert issue['provenance']['citations'][0]['raw_href'] == '/contact'
    bridge = issue['guard_bridge']
    validate_evidence_graph(bridge['native_snapshot'], bridge['native_evidence'],
                            bridge['guard_observation'], issue['finding'])
    info_unknown = [i for i in doc['items'] if i['finding']['kind'] == 'UNKNOWN']
    assert {i['outcome'] for i in info_unknown} == {'UNKNOWN', 'ACCESS_BLOCKED'}
    assert all(i['finding']['kind'] == 'UNKNOWN' and i['finding']['evidence_ids'] == []
               and i['coverage_note'] for i in info_unknown)
    assert load(doc, pack, execution).ref == package.ref == build(pack, execution).ref


@pytest.mark.parametrize('fixture,kwargs,outcome', [
    ('empty', {}, 'UNKNOWN'), ('conflict', {}, 'UNKNOWN'), ('variant', {}, 'UNKNOWN'),
    ('no-parameters', {}, 'UNKNOWN'), ('valve', {'retained': False}, 'UNKNOWN'),
    ('valve', {'max_pages': 1}, 'UNKNOWN'), ('valve', {'status': 403}, 'ACCESS_BLOCKED'),
    ('valve', {'blocked': 'waf'}, 'ACCESS_BLOCKED'),
    ('valve', {'blocked': 'robots'}, 'ACCESS_BLOCKED'),
    ('valve', {'markup': b'<html><h1>V</h1><table><tr><th>X</th><td>1</td></tr>'
                         b'<tr><th>X</th><td>1</td></tr></table></html>'}, 'UNKNOWN'),
])
def test_info_gaps_do_not_become_defects(fixture, kwargs, outcome):
    pack = product_pack(fixture, **kwargs)
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version=EVALUATOR)
    doc = build(pack, execution).document
    assert doc['checked_product_facts'] == []
    rows = [i for i in doc['items'] if i['rule_id'] == 'INFO-01']
    assert rows and all(i['outcome'] == outcome and i['finding']['kind'] == 'UNKNOWN'
                        and i['finding']['evidence_ids'] == [] for i in rows)


@pytest.mark.parametrize('mutation', [
    'text', 'name', 'line', 'column', 'path', 'hash', 'url', 'time', 'evidence_ref',
    'source_ref', 'snapshot_ref', 'missing_source', 'missing_target', 'status', 'trace',
    'target_snapshot', 'target_error', 'native_id', 'scope', 'coverage', 'private',
    'approved', 'shareable', 'builder', 'evaluator', 'positive_defect', 'unknown_fact',
    'severity', 'execution_text', 'execution_fail', 'execution_target', 'execution_scope',
    'execution_spoof404',
])
def test_rehashed_forgery_is_rejected(demo, mutation):
    pack, execution, package = demo
    doc = package.document
    product = doc['checked_product_facts'][0]['provenance']
    citation = product['citations'][4]
    issue = next(i for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION')
    if mutation in ('text', 'hash', 'url', 'time', 'evidence_ref', 'source_ref', 'snapshot_ref'):
        key = {'hash': 'content_sha256', 'time': 'observed_at'}.get(mutation, mutation)
        citation[key] = 'fabricated'
    elif mutation == 'name':
        product['citations'][0]['text'] = 'Invented valve'
    elif mutation in ('line', 'column', 'path'):
        citation['element'][mutation] = 999 if mutation != 'path' else '/invented'
    elif mutation == 'missing_source':
        del product['source_page']
    elif mutation == 'missing_target':
        del issue['provenance']['target_response']
    elif mutation in ('status', 'trace', 'target_snapshot', 'target_error'):
        key, value = {'status': ('http_status', 200), 'trace': ('redirect_trace', []),
                      'target_snapshot': ('snapshot_ref', 'fake'),
                      'target_error': ('error', None)}[mutation]
        issue['provenance']['target_response'][key] = value
    elif mutation == 'native_id':
        issue['guard_bridge']['evidence_mapping'][0]['native_evidence_id'] = 'fake'
    elif mutation == 'scope':
        doc['run_id'] = 'other'
    elif mutation == 'coverage':
        doc['coverage'] = []
    elif mutation in ('private', 'approved', 'shareable', 'builder', 'evaluator'):
        key, value = {'private': ('private', False), 'approved': ('approval_status', 'APPROVED'),
                      'shareable': ('shareable', True), 'builder': ('builder_version', 'ra2c0-1.0.0'),
                      'evaluator': ('evaluator_version', 'ra2b1-1.0.0')}[mutation]
        doc[key] = value
    elif mutation == 'positive_defect':
        doc['checked_product_facts'][0]['defect'] = True
    elif mutation == 'unknown_fact':
        next(i for i in doc['items'] if i['finding']['kind'] == 'UNKNOWN')['finding']['kind'] = 'OBSERVATION'
    elif mutation == 'severity':
        issue['finding']['severity'] = 'HIGH'
    else:
        execution = deepcopy(execution)
        info = next(e for e in execution['executions'] if e['rule_id'] == 'INFO-01')
        row = next(r for r in info['observations'] if r['observation']['result'] == 'PASS')
        if mutation == 'execution_text':
            row['citations'][4]['text'] = 'PN 999'
        elif mutation == 'execution_fail':
            row['observation']['result'] = 'FAIL_WITH_EVIDENCE'
        elif mutation == 'execution_target':
            bad = next(r for e in execution['executions'] for r in e['observations']
                       if r['observation']['result'] == 'FAIL_WITH_EVIDENCE')
            del bad['target_response']
        elif mutation == 'execution_spoof404':
            good = next(r for e in execution['executions'] for r in e['observations']
                        if e['rule_id'] == 'DISC-01' and r['observation']['result'] == 'PASS')
            good['observation']['result'] = 'FAIL_WITH_EVIDENCE'
            good['target_response']['http_status'] = 404
            good['target_response']['error'] = {'code': 'HTTP_ERROR', 'retryable': False,
                'safe_message': 'HTTP_ERROR', 'schema_version': '1.0'}
        else:
            execution['tenant_id'] = 'other'
        reseal(execution, 'execution_ref', 'rx-')
        doc['rule_execution'] = execution
        doc['execution_ref'] = execution['execution_ref']
        with pytest.raises(FindingError):
            build(pack, execution)
    with pytest.raises(FindingError):
        load(reseal(doc, 'package_ref', 'fp-'), pack, execution)


@pytest.mark.parametrize('key,value', [
    ('expected_pack_ref', 'ep-' + '0' * 64), ('expected_execution_ref', 'rx-' + '0' * 64),
    ('expected_evaluator_version', 'ra2b1-1.0.0'), ('expected_builder_version', 'ra2c0-1.0.0'),
    ('expected_builder_version', 'future'), ('expected_builder_version', None),
])
def test_all_pins_required_for_build_load_verify(demo, key, value):
    pack, execution, package = demo
    expected = pins(pack, execution)
    expected[key] = value
    with pytest.raises(FindingError):
        build_findings(pack, execution, **expected)
    with pytest.raises(FindingError):
        FindingPackage.load(package.document, pack, **expected, expected_package_ref=package.ref)
    with pytest.raises(FindingError):
        package.verify(pack, **expected, expected_package_ref=package.ref)


def test_no_implicit_upgrade_and_immutable_detached_payload(demo):
    pack, execution, package = demo
    default_pins = pins(pack, execution)
    del default_pins['expected_builder_version']
    with pytest.raises(FindingError):
        build_findings(pack, execution, **default_pins)
    with pytest.raises(FindingError):
        FindingPackage.load(package.document, pack, **default_pins, expected_package_ref=package.ref)
    detached = package.document
    detached['checked_product_facts'].clear()
    assert package.document['checked_product_facts']
    altered = deepcopy(execution)
    built = build(pack, altered)
    altered['executions'].clear()
    assert built.ref == package.ref
    with pytest.raises((FrozenInstanceError, AttributeError)):
        package._payload = b'{}'


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_cross_scope_and_untrusted_pack_rejected(demo, field):
    pack, execution, _ = demo
    document = pack.document
    document[field] = 2 if field == 'policy_version' else 'other'
    reseal(document, 'pack_ref', 'ep-')
    untrusted = EvidencePack(json.dumps(document).encode(), tuple(sorted(pack.objects.items())))
    with pytest.raises(FindingError):
        build_findings(untrusted, execution, **pins(pack, execution))


def test_actual_execution_and_aggregate_limits(demo, monkeypatch):
    from vrae.findings import builder
    pack, execution, package = demo
    legacy = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b1-1.0.0')
    with pytest.raises(FindingError):
        build(pack, legacy)
    huge = deepcopy(execution)
    huge['padding'] = 'x' * 8_000_001
    with pytest.raises(FindingError):
        build(pack, huge)
    # Verified execution fits, but duplication of evidence in the final package exceeds budget.
    assert len(builder._encode(execution)) < len(package._payload)
    monkeypatch.setattr(builder, 'MAX_BYTES', len(package._payload) - 1)
    with pytest.raises(FindingError):
        build(pack, execution)


def test_legacy_sealed_package_identity_unchanged():
    path = Path(__file__).parents[1] / 'fixtures/findings/industrial-diagnostic.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    pack = EvidencePack.load(data['document'], {
        k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()
    }, expected_ref=data['expected_pack_ref'])
    expected = {k: data[k] for k in ('expected_pack_ref', 'expected_execution_ref',
                                    'expected_evaluator_version')}
    old = build_findings(pack, data['finding_package']['rule_execution'], **expected)
    assert old.document == data['finding_package'] and old.ref == data['expected_package_ref']
    assert 'checked_product_facts' not in old.document
    assert FindingPackage.load(old.document, pack, **expected,
                               expected_package_ref=old.ref).ref == old.ref


def test_new_sealed_package_replays_offline():
    data = json.loads((Path(__file__).parent / 'fixtures/info01-private-package.json').read_text(
        encoding='utf-8'))
    pack = EvidencePack.load(data['document'], {
        k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()
    }, expected_ref=data['expected_pack_ref'])
    execution = data['finding_package']['rule_execution']
    assert load(data['finding_package'], pack, execution).ref == data['expected_package_ref']
    fresh_pack, fresh_execution = diagnostic_input()
    assert fresh_pack.ref == pack.ref and fresh_execution == execution


def test_product_raw_object_forgery_cannot_be_rehashed_into_trusted_pack(demo):
    pack, execution, package = demo
    objects = dict(pack.objects)
    key = next(k for k, value in objects.items() if b'PN 40' in value)
    objects[key] = objects[key].replace(b'PN 40', b'PN 99')
    forged = EvidencePack(pack._payload, tuple(sorted(objects.items())))
    with pytest.raises(FindingError):
        build_findings(forged, execution, **pins(pack, execution))
    with pytest.raises(FindingError):
        load(package.document, forged, execution)
