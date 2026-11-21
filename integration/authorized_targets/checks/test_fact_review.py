"""Synthetic evidence only. No model calls or customer network requests."""
import json
from copy import deepcopy

import pytest

from integration.authorized_targets.automatic_result import deterministic_diagnosis, delivery
from integration.authorized_targets.fact_review import build
from integration.authorized_targets.form_facts import extract
from tests.s2_contract.batch2_fixtures import fixture
from vrae.collection.http_measurement import measure, validate
from vrae.industry.l2_v1 import diagnose, load

EV = dict(evidence_ref='ev-'+'a'*64, snapshot_ref='page-'+'b'*64,
          locator='/pages/0/evidence', content_sha256='c'*64)
HTML = b'''<html><body><form method="post" action="/send">
<label for="email">Email</label><input id="email" type="email" required value="private@example.org">
<label>Message<textarea name="private_name">private text</textarea></label>
<input type="hidden" value="private_token"><button>Send</button></form>
<form><input type="search" name="q"></form></body></html>'''


def test_forms_export_semantics_and_offsets_without_values_or_delivery_claims():
    result = extract(HTML, EV, 'https://example.org/contact')
    inquiry, search = result['forms']
    assert inquiry['purpose'] == 'INQUIRY_CANDIDATE'
    assert search['purpose'] == 'SEARCH_CANDIDATE'
    assert [f['kind'] for f in inquiry['fields']] == ['EMAIL', 'MESSAGE']
    assert inquiry['fields'][0]['required_attribute'] is True
    assert inquiry['hidden_control_count'] == 1 and inquiry['submit_control_observed']
    assert inquiry['action_scope'] == 'SAME_ORIGIN'
    assert inquiry['delivery'] == inquiry['visibility'] == 'UNKNOWN'
    assert inquiry['submission_tested'] is False
    assert 'private' not in json.dumps(result)
    for field in inquiry['fields']:
        b = field['binding']
        assert HTML[b['byte_start']:b['byte_end']].startswith((b'<input', b'<textarea'))


@pytest.mark.parametrize('html', [b'<form><form><input type="email"></form></form>',
    b'<form hidden><input type="email"></form>', b'<template><form></form></template>'])
def test_excluded_forms_do_not_establish_absence_or_inquiry(html):
    assert not extract(html, EV, 'https://example.org')['forms']


def test_static_bounds_ambiguity_and_utf8_offsets():
    with pytest.raises(ValueError):
        extract(b'x'*131073, EV, 'https://example.org')
    with pytest.raises(ValueError):
        extract(b'<form><div></form>', EV, 'https://example.org')
    html = '\u4e2d<form><label>\u90ae\u7bb1<input type="text"></label></form>'.encode()
    f = extract(html, EV, 'https://example.org')['forms'][0]['fields'][0]
    assert f['kind'] == 'EMAIL'
    assert html[f['binding']['byte_start']:f['binding']['byte_end']] == b'<input type="text">'


def test_limits_and_unresolved_form_labels_are_explicit():
    html = b'<form><label for="x">Email</label><label for="x">Phone</label><input id="x">'+b'<input>'*35+b'</form>'
    form = extract(html, EV, 'https://example.org')['forms'][0]
    assert form['fields'][0]['kind'] == 'UNKNOWN'
    assert form['field_coverage'] == dict(total=36, returned=32, truncated=True)


def test_monotonic_measurement_is_one_final_hop_not_browser_performance():
    m = measure(1,1.01,1.03,1.04,1.06,1.07,1.09)
    assert m['connect_ms'] == 10 and m['exchange_ms'] == 90
    assert m['first_byte_after_send_ms'] == 20 and m['body_after_headers_ms'] == 20
    for key, value in [('connect_ms', True), ('samples', 2), ('exchange_ms', 1)]:
        bad = dict(m, **{key:value})
        with pytest.raises(ValueError):
            validate(bad)


def test_projection_reuses_native_trust_and_historical_timing_stays_unknown():
    pack = fixture(overrides={'/contact':HTML})
    diagnosis = deterministic_diagnosis(pack, diagnose(pack, expected_pack_ref=pack.ref,
        expected_industry_ref=load(tenant_id=pack.document['tenant_id'])['industry_ref'],
        diagnostic_version='l2-industrial-1.0.7'))
    before = deepcopy(diagnosis)
    result = build(pack, diagnosis, 'a'*64)
    assert result['technical'] and all(t['measurement'] is None for t in result['technical'])
    assert all(t['timing_state'] == 'UNKNOWN' for t in result['technical'])
    assert result['trust'] and all(not t['identity_verified'] for t in result['trust'])
    assert any(i['static_forms'] and i['static_forms']['forms'] for i in result['inquiry'])
    assert diagnosis == before and not result['inquiry_submitted']
    _, output = delivery(200, dict(state='AI_UNAVAILABLE',analysis_outcome='PROVIDER_FAILED',
        claims=[],artifact_sha256='a'*64,deterministic_diagnosis=diagnosis,fact_review=result))
    assert output['customer_presentation']['fact_review'] == result


def test_optional_measurement_persists_in_manifest_and_corruption_is_rejected(monkeypatch):
    from dataclasses import replace
    from tests.collection.test_pipeline import SyntheticTransport, collect
    from vrae.collection.manifest import CaptureBundle, document_hash
    original = SyntheticTransport.exchange
    m = measure(1,1.01,1.03,1.04,1.06,1.07,1.09)
    async def measured(self, *args, **kwargs):
        response = await original(self, *args, **kwargs)
        assert 'measurement' not in response.document()
        response = replace(response, measurement=m)
        assert response.document()['measurement'] == m
        return response
    monkeypatch.setattr(SyntheticTransport, 'exchange', measured)
    bundle, _ = collect(retain_raw_html=True)
    assert bundle.manifest['pages'][0]['http_measurement'] == m
    bundle.verify()
    corrupted = deepcopy(bundle.manifest)
    corrupted['pages'][0]['http_measurement']['exchange_ms'] = 1
    del corrupted['manifest_sha256']
    corrupted['manifest_sha256'] = document_hash(corrupted)
    with pytest.raises(ValueError):
        CaptureBundle(corrupted,bundle.objects).verify()


def test_redirect_response_is_counted_even_when_following_is_rejected():
    pack = fixture(statuses={'/about':302})
    diagnosis = deterministic_diagnosis(pack, diagnose(pack, expected_pack_ref=pack.ref,
        expected_industry_ref=load(tenant_id=pack.document['tenant_id'])['industry_ref'],
        diagnostic_version='l2-industrial-1.0.7'))
    result = build(pack, diagnosis, 'a'*64)
    failed = [p for p in result['technical'] if p['capture_status'] != 'FETCHED']
    assert failed and any(p['redirect_count'] == 1 for p in failed)
    assert all(p['measurement'] is None and not p['is_defect'] for p in failed)
