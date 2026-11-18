"""Explicit candidate-layer suite; preserve the original default inventory."""
from copy import deepcopy
from dataclasses import replace
import importlib

import pytest

from tests.s2_contract.batch2_fixtures import fixture, DIRECTORY
from tests.s2_contract.p1_industrial_cases import evaluate, scope, pins, rows
from vrae.collection.manifest import document_hash


def module():
    return importlib.import_module('vrae.reporting.s2_candidate')


def selection(pack, projection, *, model='P40', blocked=False):
    c = module()
    chosen = []
    for rule in ('INFO-02', 'TRUST-02'):
        if blocked:
            row = next(r for r in rows(projection, rule) if r['observation']['result'] == 'ACCESS_BLOCKED'
                       and any(s['url'].endswith('/p40') for s in r['source_pages']))
        else:
            row = next(r for r in rows(projection, rule) if r['model'] == model)
        chosen.append(c.ObservationPin(row['observation']['observation_id'], rule,
            row['observation']['rule_version'], row['source_version'],
            tuple(sorted(s['snapshot_ref'] for s in row['source_pages']))))
    anchor = next(s['snapshot_ref'] for s in pack.document['snapshots']
                  if s['url'].endswith('/p40' if model == 'P40' else '/v25'))
    return c.BuyerCandidatePins(**scope(pack), pack_ref=pack.ref,
        projection_ref=projection['projection_ref'], projection_version='s2-projection-1.2.0',
        industry_pins=pins(pack, projection['industrial_projection']['selected_profile_id']),
        subject_model=None if blocked else model, subject_snapshot_ref=anchor,
        observations=tuple(chosen))


@pytest.fixture(scope='module')
def baseline():
    pack = fixture()
    projection = evaluate(pack)
    return pack, projection, selection(pack, projection)


def test_replayable_buyer_task_slice_separates_source_and_review_hypotheses(baseline):
    pack, projection, held = baseline
    c = module()
    report = c.build_candidate(pack, projection, held=held)
    assert report['kind'] == 'S2BuyerTaskCandidate'
    assert report['candidate_ref'].startswith('s2br-')
    assert report['authority'] == 'READ_ONLY_REVIEW_CANDIDATE'
    assert len(report['cards']) == 2
    assert {card['result'] for card in report['cards']} == {'PASS'}
    for card in report['cards']:
        assert card['source_replay']['status'] == 'RECOMPUTED_FROM_PINNED_CURRENT_PACK'
        assert card['source_excerpts']
        assert card['review_hypothesis']['kind'] == 'HYPOTHESIS_REVIEW_REQUIRED'
        assert card['review_hypothesis']['basis_observation_ids'] == [card['observation_id']]
        assert card['native_fact_admission'] == 'NONE'
    assert report['cards'][0]['observed_fields']['data_revision'] == 'R1'
    assert report['cards'][1]['observed_fields']['authentication'] == 'UNKNOWN'
    c.verify_candidate(report, pack, projection, held=held, expected_candidate_ref=report['candidate_ref'])
    text = c.render_markdown(report, pack, projection, held=held, expected_candidate_ref=report['candidate_ref'])
    assert '采购' in text and 'R1' in text and '审阅假设' in text
    assert report['cards'][1]['observed_fields']['date_relation'] == 'BEFORE_CAPTURE'
    assert '早于采集日' in text and '字节' in text


@pytest.mark.parametrize('status', ['UNKNOWN', 'NOT_APPLICABLE', 'ACCESS_BLOCKED'])
def test_limited_states_are_preserved_without_turning_into_site_fault(status):
    c = module()
    if status == 'UNKNOWN':
        raw = (DIRECTORY / 'pump.html').read_bytes()
        pack = fixture(overrides={'/products/p40': raw})
        projection = evaluate(pack)
        held = selection(pack, projection)
    elif status == 'NOT_APPLICABLE':
        pack = fixture()
        projection = evaluate(pack, 'pump-only')
        held = selection(pack, projection, model='V25')
    else:
        pack = fixture(statuses={'/products/p40': 403})
        projection = evaluate(pack)
        held = selection(pack, projection, blocked=True)
    report = c.build_candidate(pack, projection, held=held)
    card = next(card for card in report['cards'] if card['result'] == status)
    assert card['limitation']['state'] == status
    assert card['native_fact_admission'] == 'NONE'
    if status == 'ACCESS_BLOCKED':
        assert card['source_excerpts'] == []
        assert card['observed_fields'] == {}
        assert card['source_replay']['basis'] == 'CONFIGURATION_OR_RESPONSE_METADATA_ONLY'
    elif status == 'NOT_APPLICABLE':
        assert card['configuration_locator']
    assert 'FAIL_WITH_EVIDENCE' not in {card['result'] for card in report['cards']}
    c.verify_candidate(report, pack, projection, held=held, expected_candidate_ref=report['candidate_ref'])


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version', 'pack_ref',
                                   'projection_ref', 'projection_version', 'reporting_version',
                                   'subject_model', 'subject_snapshot_ref'])
def test_server_held_task_pins_cannot_be_rebound(baseline, field):
    pack, projection, held = baseline
    c = module()
    altered = replace(held, **{field: 999 if field == 'policy_version' else 'foreign'})
    with pytest.raises(c.BuyerCandidateError):
        c.build_candidate(pack, projection, held=altered)


@pytest.mark.parametrize('field', ['rule_version', 'source_version', 'observation_id', 'snapshot_refs'])
def test_observation_versions_and_sources_are_independently_pinned(baseline, field):
    pack, projection, held = baseline
    c = module()
    first = replace(held.observations[0], **{field: ('page-forged',) if field == 'snapshot_refs' else 'forged'})
    with pytest.raises(c.BuyerCandidateError):
        c.build_candidate(pack, projection, held=replace(held, observations=(first, held.observations[1])))


def test_cannot_combine_different_product_observations_from_same_verified_projection(baseline):
    pack, projection, held = baseline
    c = module()
    other = selection(pack, projection, model='V25')
    with pytest.raises(c.BuyerCandidateError):
        c.build_candidate(pack, projection, held=replace(held, observations=(held.observations[0], other.observations[1])))


def test_even_same_model_needs_shared_pinned_subject_snapshot(baseline):
    pack, projection, held = baseline
    c = module()
    about = next(s['snapshot_ref'] for s in pack.document['snapshots'] if s['url'].endswith('/about'))
    with pytest.raises(c.BuyerCandidateError):
        c.build_candidate(pack, projection, held=replace(held, subject_snapshot_ref=about))


@pytest.mark.parametrize('field', ['quote', 'result', 'hypothesis', 'authority', 'version', 'card_splice'])
def test_self_rehashed_report_forgery_cannot_be_rendered(baseline, field):
    pack, projection, held = baseline
    c = module()
    report = deepcopy(c.build_candidate(pack, projection, held=held))
    if field == 'quote':
        report['cards'][0]['source_excerpts'][0]['quote'] = 'forged source'
    elif field == 'result':
        report['cards'][0]['result'] = 'FAIL_WITH_EVIDENCE'
    elif field == 'hypothesis':
        report['cards'][1]['review_hypothesis']['text'] = 'The certificate is authentic and compliant.'
    elif field == 'authority':
        report['authority'] = 'GUARD_APPROVED'
    elif field == 'version':
        report['reporting_version'] = 'forged'
    else:
        report['cards'].append(deepcopy(report['cards'][0]))
    report['candidate_ref'] = 's2br-' + document_hash({k: v for k, v in report.items() if k != 'candidate_ref'})
    with pytest.raises(c.BuyerCandidateError):
        c.render_markdown(report, pack, projection, held=held, expected_candidate_ref=report['candidate_ref'])


def test_rehashed_source_projection_is_recomputed_not_trusted(baseline):
    pack, original, held = baseline
    c = module()
    projection = deepcopy(original)
    rows(projection, 'INFO-02', 'P40')[0]['citations'][0]['byte_start'] += 1
    projection['projection_ref'] = 's2p-' + document_hash({k: v for k, v in projection.items() if k != 'projection_ref'})
    with pytest.raises(c.BuyerCandidateError):
        c.build_candidate(pack, projection, held=replace(held, projection_ref=projection['projection_ref']))


def test_industry_profile_and_version_must_come_from_server_context(baseline):
    pack, projection, held = baseline
    c = module()
    for invalid in (None, replace(held.industry_pins, profile_id='pump-only'),
                    replace(held.industry_pins, version='9.0.0')):
        with pytest.raises(c.BuyerCandidateError):
            c.build_candidate(pack, projection, held=replace(held, industry_pins=invalid))


def test_other_pack_and_cross_run_source_cannot_be_combined(baseline):
    _, projection, held = baseline
    c = module()
    other = fixture(statuses={'/products/proof': 403})
    with pytest.raises(c.BuyerCandidateError):
        c.build_candidate(other, projection, held=replace(held, pack_ref=other.ref))


def test_read_only_candidate_never_becomes_native_finding_or_guard_fact(baseline):
    from vrae.rules import verify_execution
    from vrae.findings import build_findings, FindingError
    from vrae.evidence import EvidenceError
    pack, projection, held = baseline
    c = module()
    report = c.build_candidate(pack, projection, held=held)
    with pytest.raises(EvidenceError):
        verify_execution(report, pack, expected_pack_ref=pack.ref, expected_evaluator_version='ra2b6-1.0.0')
    with pytest.raises(FindingError):
        build_findings(pack, report, expected_pack_ref=pack.ref, expected_execution_ref=report['candidate_ref'],
            expected_evaluator_version='ra2b6-1.0.0', expected_builder_version='ra2c3-1.0.0')


def test_single_card_is_a_valid_bounded_vertical_slice(baseline):
    pack, projection, held = baseline
    c = module()
    report = c.build_candidate(pack, projection, held=replace(held, observations=held.observations[:1]))
    assert len(report['cards']) == 1
    assert report['cards'][0]['rule_id'] == 'INFO-02'


@pytest.mark.parametrize('case', ['empty', 'duplicate', 'too-many'])
def test_no_unpinned_extra_or_duplicate_cards(baseline, case):
    pack, projection, held = baseline
    c = module()
    selected = () if case == 'empty' else (held.observations[0],) * (3 if case == 'too-many' else 2)
    with pytest.raises(c.BuyerCandidateError):
        c.build_candidate(pack, projection, held=replace(held, observations=selected))


def test_configuration_only_exclusion_does_not_fabricate_product_evidence():
    c = module()
    pack = fixture()
    projection = evaluate(pack, 'technical-only')
    standard = evaluate(pack)
    initial = selection(pack, standard)
    info = rows(projection, 'INFO-02', 'P40')[0]
    excluded = next(r for r in rows(projection, 'TRUST-02') if r['observation']['result'] == 'NOT_APPLICABLE')
    chosen = tuple(c.ObservationPin(r['observation']['observation_id'], r['observation']['rule_id'],
        r['observation']['rule_version'], r['source_version'],
        tuple(sorted(s['snapshot_ref'] for s in r['source_pages']))) for r in (info, excluded))
    held = replace(initial, projection_ref=projection['projection_ref'],
                   industry_pins=pins(pack, 'technical-only'), observations=chosen)
    report = c.build_candidate(pack, projection, held=held)
    card = report['cards'][1]
    assert card['result'] == 'NOT_APPLICABLE'
    assert card['source_excerpts'] == []
    assert card['source_replay']['basis'] == 'CONFIGURATION_OR_RESPONSE_METADATA_ONLY'


def altered_conditions(value):
    pack = fixture()
    raw = next(pack.resolve(e['evidence_ref'], expected_pack_ref=pack.ref)['content']
        for e in pack.document['evidence'] if next(s for s in pack.document['snapshots']
        if s['snapshot_ref'] == e['snapshot_ref'])['url'].endswith('/p40'))
    import re
    raw = re.sub(b'(<th>Specification conditions</th><td>)[^<]*',
                 lambda m: m[1] + value.encode(), raw)
    return fixture(overrides={'/products/p40': raw})


def test_source_markup_and_markdown_are_displayed_as_text():
    c = module()
    pack = altered_conditions('&lt;img src=x onerror=alert(1)&gt; [link](https://example.invalid)')
    projection = evaluate(pack)
    held = selection(pack, projection)
    report = c.build_candidate(pack, projection, held=held)
    text = c.render_markdown(report, pack, projection, held=held, expected_candidate_ref=report['candidate_ref'])
    assert '<img' not in text
    assert '](https://example.invalid)' not in text


def test_unreadable_directional_source_text_is_rejected_before_display():
    c = module()
    pack = altered_conditions('Water\u202e unsafe direction')
    projection = evaluate(pack)
    with pytest.raises(c.BuyerCandidateError, match='^S2_BUYER_CANDIDATE_INTEGRITY$'):
        c.build_candidate(pack, projection, held=selection(pack, projection))
