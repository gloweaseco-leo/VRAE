"""Five-task review over synthetic retained evidence; no network or model."""
from copy import deepcopy
import json
import socket

import pytest

from integration.authorized_targets.automatic_result import deterministic_diagnosis, delivery
from integration.authorized_targets.buyer_review import build
from tests.s2_contract.batch2_fixtures import fixture
from vrae.evidence import EvidenceError
from vrae.industry.l2_v1 import diagnose, load


@pytest.fixture(scope='module')
def held():
    pack = fixture(overrides={'/products/p40': b'<html><body><main><h1>Grinding wheel W100</h1>'
        b'<table><tr><th>Size</th><td>100 mm</td></tr></table>'
        b'<a href="/contact">Contact</a></main></body></html>'})
    diagnosis = diagnose(pack, expected_pack_ref=pack.ref,
        expected_industry_ref=load(tenant_id=pack.document['tenant_id'])['industry_ref'],
        diagnostic_version='l2-industrial-1.0.6')
    return pack, deterministic_diagnosis(pack, diagnosis)


def test_five_task_candidates_do_not_promote_or_replace_native_unknown(held):
    pack, diagnosis = held
    before = deepcopy(diagnosis)
    review = build(pack, diagnosis, 'a'*64)
    assert [t['task'] for t in review['tasks']] == [t['task'] for t in diagnosis['buyer_tasks']]
    native = next(r for t in diagnosis['buyer_tasks'] for r in t['rules'] if r['rule_id']=='TECH-01')
    assert all(r['observation']['result']=='UNKNOWN' for r in native['observations'])
    technical = review['tasks'][4]['candidates']
    assert any(c['rule_id']=='TECH-01' and c['candidate_result']=='PASS' for c in technical)
    assert all(c['native_fact_admission']=='NONE' and c['human_review_required'] for t in review['tasks'] for c in t['candidates'])
    assert review['state']=='AVAILABLE' and review['s2_projection_ref'].startswith('s2p-')
    assert diagnosis == before


def test_paths_follow_original_snapshot_joins_and_never_claim_inquiry_delivery(held):
    pack, diagnosis = held
    review = build(pack, diagnosis, 'a'*64)
    assert any(p['static_path_complete'] for p in review['paths'])
    for path, original in zip(review['paths'], diagnosis['buyer_journey']):
        assert path['journey_ref']==original['journey_ref']
        assert [s['observation_id'] for s in path['steps']]==[s['observation_id'] for s in original['steps']]
        assert path['product_context_transfer']=='UNKNOWN' and not path['inquiry_submitted']
    assert review['technical_material_route']==review['proof_route']=='UNKNOWN'


def test_candidate_source_bindings_resolve_to_original_evidence_without_raw_quotes(held):
    pack, diagnosis = held
    review = build(pack, diagnosis, 'a'*64)
    evidence = {e['evidence_ref']: e for e in pack.document['evidence']}
    for task in review['tasks']:
        for row in task['candidates']:
            for binding in row['evidence_bindings']:
                assert {k: binding[k] for k in ('evidence_ref','snapshot_ref','locator','content_sha256')} == {
                    k: evidence[binding['evidence_ref']][k] for k in ('evidence_ref','snapshot_ref','locator','content_sha256')}
                assert 0 <= binding['byte_start'] < binding['byte_end'] <= 131072
            assert all('quote' not in b and 'text' not in b for b in row['evidence_bindings'])
    assert 'buyer@example.org' not in json.dumps(review)


@pytest.mark.parametrize('error', [EvidenceError, ValueError])
def test_candidate_layer_failure_preserves_native_facts_procurement_and_paths(held, monkeypatch, error):
    import integration.authorized_targets.buyer_review as module
    pack, diagnosis = held
    def unavailable(*args, **kwargs):
        raise error('SYNTHETIC_PROJECTION_FAILURE')
    monkeypatch.setattr(module, 'evaluate_s2', unavailable)
    review = build(pack, diagnosis, 'a'*64)
    assert review['state']=='CANDIDATES_UNAVAILABLE' and review['paths']
    assert not any(t['candidates'] for t in review['tasks'])
    _, result = delivery(200, {'state':'AI_UNAVAILABLE','analysis_outcome':'PROVIDER_FAILED',
        'claims':[], 'artifact_sha256':'a'*64,'deterministic_diagnosis':diagnosis,'buyer_review':review})
    assert len(result['customer_presentation']['tasks'])==5
    assert result['customer_presentation']['procurement_review']['products']
    assert result['customer_presentation']['buyer_review']==review


def test_review_limits_are_explicit_not_a_whole_site_denominator(held, monkeypatch):
    import integration.authorized_targets.buyer_review as module
    pack, diagnosis = held
    original = module.evaluate_s2
    def many(*args, **kwargs):
        result = original(*args, **kwargs)
        row = result['static_projection']['rows'][0]
        result['static_projection']['rows'] += [deepcopy(row) for _ in range(20)]
        return result
    monkeypatch.setattr(module, 'evaluate_s2', many)
    changed = deepcopy(diagnosis)
    changed['buyer_journey'] *= 20
    review = build(pack, changed, 'a'*64)
    coverage = next(c for t in review['tasks'] for c in t['coverage'] if c['rule_id']=='TECH-01')
    assert coverage['truncated'] and coverage['returned']==16
    assert review['path_coverage']['truncated'] and len(review['paths'])==16
    assert review['path_coverage']['whole_site_coverage_known'] is False


def test_projection_has_no_network_and_rejects_a_different_pack_pin(held, monkeypatch):
    pack, diagnosis = held
    def denied(*args, **kwargs):
        pytest.fail('read projection attempted network access')
    monkeypatch.setattr(socket, 'socket', denied)
    monkeypatch.setattr(socket, 'getaddrinfo', denied)
    assert build(pack, diagnosis, 'a'*64)['state']=='AVAILABLE'
    changed = deepcopy(diagnosis)
    changed['expected_pack_ref']='ep-'+'0'*64
    with pytest.raises(EvidenceError):
        build(pack, changed, 'a'*64)
