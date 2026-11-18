from dataclasses import replace
import json

import pytest

from integration.l2.support import login, pins
from vrae.collection.manifest import document_hash
from .fixture import application, source_binding
from . import workbench


@pytest.fixture
def setup(tmp_path):
    return application(tmp_path)


def request(setup, subject='reviewer-demo', *, suffix='', method='GET'):
    issuer, directory, _, app, _, rid = setup
    sid = login(issuer, directory, subject)
    reply = app.handle(method, '/b5a/l2/r/'+rid+'/source-tasks'+suffix,
                       headers(sid))
    return sid, reply.response


def headers(sid=''):
    return {'Host':'127.0.0.1:9876', 'Origin':'http://127.0.0.1:9876',
            **({'Cookie':'b5a_l2_session='+sid} if sid else {})}


def test_native_five_dimensions_and_original_report_remain_distinct(setup):
    _, _, ledger, _, binding, _ = setup
    sid, response = request(setup)
    original = ledger.read(sid, setup[-1])
    assert response.status == 200
    text = response.body.decode()
    assert text.count('data-task=') == 5
    assert 'P40' in text and 'V25' in text and 'INFO-02' in text and 'TRUST-03' in text
    assert 'UNKNOWN' in text and '下一步' in text and '原版本逐项 Controlled 审阅' in text
    assert '正式人审' in text and 'source-tasks/cite/' in text
    assert ledger.source.read().payload == original.payload
    assert all(row['admission'] == 'READ_ONLY_CANDIDATE_NOT_FINDING_OR_GUARD_FACT'
               for row in json.loads(binding.payload)['industrial_projection']['rows'])


@pytest.mark.parametrize('subject', ['other-tenant', 'recipient-a', 'recipient-b'])
def test_original_tenant_and_unclaimed_reader_access_still_deny(setup, subject):
    _, response = request(setup, subject)
    assert response.status == 403 and b's2-source-workbench' not in response.body


def test_unsigned_and_post_cannot_fetch_candidates(setup):
    _, _, _, app, _, rid = setup
    response = app.handle('GET', '/b5a/l2/r/'+rid+'/source-tasks', headers()).response
    assert response.status == 403
    _, response = request(setup, method='POST')
    assert response.status == 403


def test_original_expiry_and_revocation_still_apply(tmp_path):
    clock = [1800000000.0]
    setup = application(tmp_path, clock=lambda: clock[0])
    _, directory, _, app, _, rid = setup
    sid, response = request(setup)
    assert response.status == 200
    directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=False)
    response = app.handle('GET', '/b5a/l2/r/'+rid+'/source-tasks', headers(sid)).response
    assert response.status == 403
    directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=True)
    clock[0] += 7200
    response = app.handle('GET', '/b5a/l2/r/'+rid+'/source-tasks', headers(sid)).response
    assert response.status == 403


def test_citation_replays_original_utf8_without_active_html(setup):
    _, response = request(setup, suffix='/cite/0')
    assert response.status == 200
    text = response.body.decode()
    assert 's2-original-citation' in text and '原始 UTF-8 字节' in text
    assert '&lt;th&gt;' in text and '<table>' not in text
    _, response = request(setup, suffix='/cite/999')
    assert response.status == 403


def test_static_citation_uses_original_snapshot_url_and_time(setup):
    binding = setup[-2]
    rows = workbench.candidate_rows(json.loads(binding.payload))
    index = next(i for i,row in enumerate(rows) if row['observation']['rule_id'] in ('DISC-03','SEO-02','TECH-01') and row['citations'])
    _, response = request(setup, suffix='/cite/'+str(index))
    assert response.status == 200 and b'https://example.org' in response.body


def test_source_configuration_applicability_is_presented_without_changing_report():
    binding = source_binding('pump-only')
    report = binding.source.read()
    projection = binding.read(report)
    assert any(row['model']=='V25' and row['observation']['result']=='NOT_APPLICABLE'
               for row in projection['industrial_projection']['rows'])
    html = workbench.render(report, projection, '/original-report')
    assert '此项不适用（按固定行业配置）' in html
    assert binding.source.read().payload == report.payload


def test_candidate_self_rehash_or_replaced_quote_is_rejected(setup):
    binding = setup[-2]
    original = binding.payload
    data = json.loads(original)
    data['industrial_projection']['rows'][0]['observation']['result'] = 'FAIL_WITH_EVIDENCE'
    data['projection_ref'] = 's2p-'+document_hash({k:v for k,v in data.items() if k != 'projection_ref'})
    binding.payload = json.dumps(data).encode()
    _, response = request(setup)
    assert response.status == 403
    binding.payload = original
    _, response = request(setup)
    assert response.status == 200


def test_revocation_during_render_blocks_output(setup, monkeypatch):
    directory = setup[1]
    original = workbench.render

    def revoke(*args):
        body = original(*args)
        directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=False)
        return body
    monkeypatch.setattr(workbench, 'render', revoke)
    _, response = request(setup)
    assert response.status == 403 and b's2-source-workbench' not in response.body


def test_existing_native_authority_cannot_be_replaced(setup):
    app, binding = setup[3], setup[-2]
    with pytest.raises(ValueError):
        workbench.install(app, binding)


def test_original_controlled_review_still_uses_only_original_items(setup):
    issuer, directory, ledger, app, _, rid = setup
    sid, _ = request(setup)
    report = ledger.read(sid, rid)
    keys = {row['id'] for row in report.document['findings']+report.document['blueprint']}
    receipt = ledger.review(sid, rid, **pins(report), action='REQUEST_CHANGES',
                            reason='受控演练：补核工况与供应商声明；非正式人审。',
                            items={key:'ACK' for key in keys}, attest=True)
    assert receipt['formal_human_review'] is False
    response = app.handle('GET', '/b5a/l2/r/'+rid+'/source-tasks', headers(sid)).response
    assert response.status == 200
    assert ledger.read(sid, rid).display_hash == report.display_hash
