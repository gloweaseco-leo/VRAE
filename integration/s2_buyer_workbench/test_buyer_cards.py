"""UI admission uses the accepted C1 verifier and the original signed report read."""
from dataclasses import replace
import json

import pytest

from vrae.reporting.common import digest
from vrae.reporting.s2_candidate import verify_candidate
from .fixture import application
from .test_workbench import request, headers
from . import workbench, buyer_cards


@pytest.fixture
def setup(tmp_path):
    return application(tmp_path)


def test_two_verified_cards_and_details_keep_original_report_and_review_items(setup):
    _, _, ledger, app, binding, rid = setup
    before = binding.source.read()
    sid, response = request(setup)
    assert response.status == 200
    text = response.body.decode()
    assert text.count('data-key="buyer-task-card"') == 2
    assert text.count('data-buyer-authority="READ_ONLY_REVIEW_CANDIDATE"') == 2
    assert all(label in text for label in ('看到什么', '采购帮助', '还不知道', '下一步向企业索取'))
    dto = json.loads(binding.buyer_payload)
    assert {card['rule_id'] for card in dto['cards']} == {'INFO-02','TRUST-02'}
    assert all(card['native_fact_admission']=='NONE' for card in dto['cards'])
    for index in (0,1):
        page = app.handle('GET', '/b5a/l2/r/'+rid+'/source-tasks/buyer-cite/'+str(index), headers(sid)).response
        assert page.status == 200 and b'READ_ONLY_REVIEW_CANDIDATE' in page.body
        assert b'&lt;th&gt;' in page.body and b'<table>' not in page.body
    assert ledger.read(sid,rid).payload == before.payload
    assert [row['id'] for row in ledger.read(sid,rid).document['findings']] == [row['id'] for row in before.document['findings']]


def test_self_rehashed_prose_is_rejected_even_with_matching_supplied_ref(setup):
    binding = setup[-2]
    candidate = json.loads(binding.buyer_payload)
    candidate['cards'][0]['review_hypothesis']['text'] = '已确认全部工程适配'
    candidate['candidate_ref'] = 's2br-'+digest({k:v for k,v in candidate.items() if k!='candidate_ref'})
    binding.buyer_payload = json.dumps(candidate).encode()
    binding.expected_buyer_ref = candidate['candidate_ref']
    _, response = request(setup)
    assert response.status == 403 and b'buyer-task-card' not in response.body


@pytest.mark.parametrize('field,value', [
    ('tenant_id','foreign'), ('run_id','foreign'), ('pack_ref','ep-'+'0'*64),
    ('subject_snapshot_ref','page-'+'0'*64), ('reporting_version','future'),
])
def test_ui_cannot_accept_rebound_server_pins(setup, field, value):
    binding = setup[-2]
    binding.buyer_pins = replace(binding.buyer_pins, **{field:value})
    _, response = request(setup)
    assert response.status == 403 and b'buyer-task-card' not in response.body


def test_observation_version_mismatch_blocks_card_details(setup):
    binding = setup[-2]
    first = replace(binding.buyer_pins.observations[0], source_version='future')
    binding.buyer_pins = replace(binding.buyer_pins, observations=(first,binding.buyer_pins.observations[1]))
    _, response = request(setup, suffix='/buyer-cite/0')
    assert response.status == 403


@pytest.mark.parametrize('field,value', [('profile_id','technical-only'),('version','future')])
def test_independent_profile_and_version_mismatch_block_card_details(setup, field, value):
    binding = setup[-2]
    binding.buyer_pins = replace(binding.buyer_pins, industry_pins=replace(binding.buyer_pins.industry_pins, **{field:value}))
    _, response = request(setup, suffix='/buyer-cite/0')
    assert response.status == 403


def test_original_revocation_blocks_both_candidate_detail_routes(setup):
    _, directory, _, app, _, rid = setup
    sid, response = request(setup)
    assert response.status == 200
    directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=False)
    for index in (0,1):
        response = app.handle('GET', '/b5a/l2/r/'+rid+'/source-tasks/buyer-cite/'+str(index), headers(sid)).response
        assert response.status == 403 and b'buyer-task-card' not in response.body


def test_version_change_during_render_cannot_publish_stale_cards(setup, monkeypatch):
    from integration.l2.support import login, pins
    issuer, directory, ledger, app, _, rid = setup
    sid = login(issuer,directory,'reviewer-demo')
    original = workbench.render
    def revise(*args):
        body = original(*args)
        report = ledger.read(sid,rid)
        item = report.document['blueprint'][0]
        ledger.revise(sid,rid,**pins(report),changes={item['id']:item['change']+'（受控版本变更）'})
        return body
    monkeypatch.setattr(workbench,'render',revise)
    response = app.handle('GET','/b5a/l2/r/'+rid+'/source-tasks',headers(sid)).response
    assert response.status == 403 and b'buyer-task-card' not in response.body
    assert ledger.read(sid,rid).version['version'] == 2


def test_both_source_card_routes_keep_original_tenant_and_reader_checks(setup):
    for subject in ('other-tenant','recipient-a'):
        for index in (0,1):
            _, response = request(setup, subject, suffix='/buyer-cite/'+str(index))
            assert response.status == 403 and b's2-original-citation' not in response.body


def test_same_pack_other_product_cannot_be_spliced_into_cards(setup):
    binding = setup[-2]
    other = next(snapshot['snapshot_ref'] for snapshot in binding.pack.document['snapshots']
                 if snapshot['url'].endswith('/v25'))
    binding.buyer_pins = replace(binding.buyer_pins, subject_snapshot_ref=other)
    _, response = request(setup)
    assert response.status == 403


def test_ui_preserves_accepted_unknown_applicability_and_blocked_states():
    from tests.s2_contract.buyer_candidate_cases import selection
    from tests.s2_contract.p1_industrial_cases import evaluate
    from tests.s2_contract.batch2_fixtures import fixture, DIRECTORY
    from vrae.reporting.s2_candidate import build_candidate
    for state in ('UNKNOWN','NOT_APPLICABLE','ACCESS_BLOCKED'):
        pack = (fixture(overrides={'/products/p40':(DIRECTORY/'pump.html').read_bytes()}) if state=='UNKNOWN'
                else fixture(statuses={'/products/p40':403}) if state=='ACCESS_BLOCKED' else fixture())
        projection = evaluate(pack, 'pump-only' if state=='NOT_APPLICABLE' else 'industrial')
        held = selection(pack, projection, model='V25' if state=='NOT_APPLICABLE' else 'P40', blocked=state=='ACCESS_BLOCKED')
        dto = build_candidate(pack,projection,held=held)
        verify_candidate(dto,pack,projection,held=held,expected_candidate_ref=dto['candidate_ref'])
        card = next(card for card in dto['cards'] if card['result']==state)
        text = buyer_cards.render_card(card,0,'/same-report')
        assert 'data-result="'+state+'"' in text and 'FAIL_WITH_EVIDENCE' not in text
        if state=='ACCESS_BLOCKED':
            assert 'buyer-card-source' not in text and '没有材料原文字节' in text
