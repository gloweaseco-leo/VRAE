"""Explicit INFO-03/TECH-02 source and authority negatives, not default inventory."""
import json
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from integration.s2_source_quality.fixture import prepared
from vrae.collection.manifest import document_hash
from vrae.rules.s2.source_quality import (
    SourceQualityError,
    evaluate_source_quality,
    verify_source_quality,
)


@pytest.fixture(scope='module')
def base():
    p, parent, held = prepared()
    return p, parent, held, evaluate_source_quality(p, parent, held=held)


def items(out, rule):
    return next(row for row in out['rows'] if row['rule_id'] == rule)['items']


def test_byte_positions_time_and_original_parent_are_replayable(base):
    pack, parent, held, out = base
    assert out['parent_s2p_ref'] == parent['projection_ref']
    assert sum(row['enabled'] for row in parent['baseline_execution']['executions']) == 6
    for row in out['rows']:
        assert row['semantic_quality'] == 'UNKNOWN' and row['native_fact_admission'] == 'NONE'
        for item in row['items']:
            for c in item['citations']:
                raw = pack.resolve(c['evidence_ref'], expected_pack_ref=pack.ref)['content']
                assert raw[c['byte_start']:c['byte_end']].decode() == c['quote']
                assert c['observed_at'] == held.pages[0].observed_at
                assert c['source_ref'] in {s['source_ref'] for s in pack.document['sources']}
    verify_source_quality(out, pack, parent, held=held, expected_quality_ref=out['quality_ref'])
    assert out['coverage']['selected'] == 1 and out['coverage']['whole_site_denominator'] is None
    assert out['coverage']['pages'][0]['role'] == 'PRODUCT'


def test_negation_acronyms_and_definition_are_clues_never_language_failure(base):
    out = base[3]
    signals = items(out, 'INFO-03')
    assert any('NPSH' in i['details'].get('acronyms', []) for i in signals)
    assert any('Do not assume' in c['quote'] for i in signals for c in i['citations'])
    assert any(i['kind'] == 'ABBREVIATION_TITLE' for i in signals)
    assert all(i['state'] != 'FAIL' for i in signals)
    assert out['quality']['status'] == 'NOT_EVALUABLE' and out['quality']['precision'] is None


def test_missing_empty_alt_heading_skip_and_uncaptured_images_are_distinct(base):
    signals = items(base[3], 'TECH-02')
    assert {'ALT_ATTRIBUTE_ABSENT', 'ALT_EMPTY_PURPOSE_REVIEW', 'SOURCE_LEVEL_SKIP'} <= {i['reason'] for i in signals}
    for i in signals:
        if i['kind'] == 'IMAGE_ALT_SOURCE':
            assert i['details']['decorative_intent'] == 'UNKNOWN'
            assert i['details']['resource']['actual_load'] == 'UNKNOWN'
    resource = next(i['details']['resource'] for i in signals if i['kind'] == 'IMAGE_ALT_SOURCE'
                    and i['details']['resource'].get('requested_url', '').endswith('diagram-response'))
    assert resource['state'] == 'CAPTURE_METADATA_ONLY'
    assert resource['response_metadata']['http_status'] == 404
    assert resource['retained_evidence_ref'] is None and not resource['retained_body']


@pytest.mark.parametrize('scenario', ['static', 'cms', 'spa', 'multi-sku', 'multilingual', 'ambiguous', 'no-images', 'hostile'])
def test_site_families_counterexamples_preserve_coverage_and_unknown(scenario):
    pack, parent, held = prepared(scenario)
    out = evaluate_source_quality(pack, parent, held=held)
    assert len(out['rows']) == 2 and out['scope']['run_id'] == pack.document['run_id']
    assert all(r['semantic_quality'] == 'UNKNOWN' for r in out['rows'])
    if scenario == 'spa':
        assert any(i['reason'] == 'JAVASCRIPT_RENDERING_NOT_OBSERVED' for i in items(out, 'INFO-03'))
    if scenario == 'ambiguous':
        assert {r['state'] for r in out['rows']} == {'UNKNOWN'}
    if scenario == 'no-images':
        subset = next(i for i in items(out, 'TECH-02') if i['kind'] == 'IMAGE_ALT_SUBSET')
        assert subset['state'] == 'NOT_APPLICABLE' and subset['details']['css_svg_canvas_and_js_images'] == 'UNKNOWN'


@pytest.mark.parametrize('kwargs', [{'status': 403}, {'status': 404}, {'retain': False}])
def test_denied_unavailable_or_unretained_sources_do_not_become_site_defects(kwargs):
    pack, parent, held = prepared(**kwargs)
    out = evaluate_source_quality(pack, parent, held=held)
    assert {r['state'] for r in out['rows']} == {'ACCESS_BLOCKED' if kwargs.get('status') == 403 else 'UNKNOWN'}
    assert all(not i['citations'] for r in out['rows'] for i in r['items'])


@pytest.mark.parametrize('key', ['tenant_id', 'run_id', 'policy_id', 'policy_version', 'pack_ref',
                                'parent_ref', 'parent_version', 'quality_version', 'source_version'])
def test_independent_scope_and_version_pins_cannot_be_rebound(base, key):
    pack, parent, held, _ = base
    wrong = replace(held, **{key: 999 if key == 'policy_version' else 'foreign'})
    with pytest.raises(SourceQualityError):
        evaluate_source_quality(pack, parent, held=wrong)


@pytest.mark.parametrize('key', ['snapshot_ref', 'url', 'role', 'observed_at', 'model', 'data_revision'])
def test_page_metadata_model_and_revision_are_not_client_claims(base, key):
    pack, parent, held, _ = base
    page = replace(held.pages[0], **{key: 'foreign'})
    with pytest.raises(SourceQualityError):
        evaluate_source_quality(pack, parent, held=replace(held, pages=(page,)))


@pytest.mark.parametrize('key', ['source_ref', 'evidence_ref', 'quote', 'observed_at', 'content_sha256'])
def test_self_rehashed_cross_source_citation_forgery_is_rejected(base, key):
    pack, parent, held, original = base
    bad = deepcopy(original)
    cite = next(c for r in bad['rows'] for i in r['items'] for c in i['citations'])
    cite[key] = 'forged-source-or-claim'
    bad['quality_ref'] = 's2q-' + document_hash({k: v for k, v in bad.items() if k != 'quality_ref'})
    with pytest.raises(SourceQualityError):
        verify_source_quality(bad, pack, parent, held=held, expected_quality_ref=bad['quality_ref'])


def test_scope_selection_is_bounded_and_capture_time_is_not_renewed(base):
    pack, parent, held, _ = base
    for pages in ((), held.pages * 2, held.pages * 9):
        with pytest.raises(SourceQualityError):
            evaluate_source_quality(pack, parent, held=replace(held, pages=pages))
    with pytest.raises(SourceQualityError):
        evaluate_source_quality(pack, parent, held=replace(held,
            observed_before=held.observed_after - timedelta(seconds=1)))
    assert 'real_model_calls' not in json.dumps(evaluate_source_quality(pack, parent, held=held))


def test_captured_200_image_mime_still_has_no_retained_asset_or_load_claim():
    pack, parent, held = prepared(resource_status=200)
    out = evaluate_source_quality(pack, parent, held=held)
    resource = next(i['details']['resource'] for i in items(out, 'TECH-02') if i['kind'] == 'IMAGE_ALT_SOURCE'
        and i['details']['resource'].get('requested_url', '').endswith('diagram-response'))
    assert resource['response_metadata']['http_status'] == 200
    assert not resource['retained_body'] and resource['actual_load'] == 'UNKNOWN'
