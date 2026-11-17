"""Same authenticated console/ledger authority; no fake S2 rule execution."""
from dataclasses import replace
import copy
import re

import pytest

from apps.operator_console.l2_buyer_views import reading, render
from apps.operator_console.l2_http import DeepConsole
from integration.l2.support import create, login, REPORT, pins
from integration.l2.native_component import source
from vrae.l2.ledger import Ledger
from vrae.l2.report import DeepReport, encoded, L2Denied, TASKS


def test_five_dimensions_and_original_sixteen_are_separate_from_industry(tmp_path):
    issuer, directory, ledger, app = create(tmp_path)
    sid = login(issuer, directory, 'reviewer-demo')
    view = ledger.read(sid, REPORT)
    before = view.payload
    m = reading(view)
    assert [x['task'] for x in m['dimensions']] == list(TASKS)
    assert sum(len(x['generic_rules']) for x in m['dimensions']) == 16
    assert m['whole_site_denominator'] is None
    assert len(m['language_candidates']) >= 1
    assert all(x['reason'] == 'HUMAN_REVIEW_REQUIRED' and x['result'] == 'UNKNOWN'
               for x in m['language_candidates'])
    html = render(view, directory.people['reviewer-demo'])
    assert re.findall(r'data-task="([^"]+)"', html) == list(TASKS)
    assert html.count('data-rule=') == 16
    assert '没有SEO评分' in html and '分母 UNKNOWN' in html
    assert 'Document coming soon' in html
    assert not ledger.history(sid, REPORT)[1] and view.payload == before
    assert m['display_hash'] == view.display_hash


@pytest.mark.parametrize('subject', [None, 'other-tenant', 'recipient-a'])
def test_new_route_preserves_signed_identity_tenant_and_directed_access(subject, tmp_path):
    issuer, directory, ledger, app = create(tmp_path)
    headers = {} if subject is None else {
        'Cookie': 'b5a_l2_session=' + login(issuer, directory, subject)}
    response = app.deep.handle('GET', '/b5a/l2/r/'+REPORT+'/buyer-tasks', headers, b'').response
    assert response.status == 403
    assert b'l2-buyer-dimension' not in response.body


def test_live_route_read_only_version_revision_and_revocation(tmp_path):
    issuer, directory, ledger, app = create(tmp_path)
    sid = login(issuer, directory, 'reviewer-demo')
    headers = {'Cookie': 'b5a_l2_session=' + sid}
    target = '/b5a/l2/r/'+REPORT+'/buyer-tasks'
    first = ledger.read(sid, REPORT)
    assert app.deep.handle('GET', target, headers, b'').response.status == 200
    assert not ledger.history(sid, REPORT)[1]
    second = ledger.revise(sid, REPORT, **pins(first), changes={'bp-rfq': '受控修订：先确认型号与询价资料。'})
    response = app.deep.handle('GET', target, headers, b'').response
    assert second.display_hash.encode() in response.body
    assert first.display_hash.encode() not in response.body
    assert b'data-report-version="l2-pump-maker.v2"' in response.body
    assert app.deep.handle('POST', target, headers, b'').response.status == 403
    assert not ledger.history(sid, REPORT)[1]
    directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=False)
    assert app.deep.handle('GET', target, headers, b'').response.status == 403


def test_native_original_findings_all_map_and_fifth_dimension_stays_unknown(tmp_path):
    issuer, directory, _, _ = create(tmp_path/'base')
    native = source()
    rid = native.read().version['report_id']
    for key, person in list(directory.people.items()):
        directory.people[key] = replace(person, report_ids=(rid,))
    ledger = Ledger(tmp_path/'native.sqlite', native, directory)
    deep = DeepConsole(directory, {rid: ledger})
    sid = login(issuer, directory, 'reviewer-demo')
    view = ledger.read(sid, rid)
    m = reading(view)
    assert sum(len(x['findings']) for x in m['dimensions']) == len(view.document['findings'])
    assert len(m['sources']) == len(view.document['snapshots'])
    assert not m['dimensions'][-1]['findings']  # No manufactured fifth-dimension assessment.
    assert any(f['native_result'] == 'NOT_APPLICABLE' for x in m['dimensions'] for f in x['findings'])
    res = deep.handle('GET', '/b5a/l2/r/'+rid+'/buyer-tasks', {'Cookie': 'b5a_l2_session='+sid}, b'').response
    assert res.status == 200
    assert 'NOT_APPLICABLE' in res.body.decode() and '18 bar' in res.body.decode()
    assert view.payload == native.read().payload and not ledger.history(sid, rid)[1]


def test_only_original_quote_is_scanned_not_chinese_ui_or_inferred_semantics(tmp_path):
    issuer, directory, ledger, _ = create(tmp_path)
    view = ledger.read(login(issuer, directory, 'reviewer-demo'), REPORT)
    d = copy.deepcopy(view.document)
    for ev in d['evidence']:
        ev['quote'] = '18 bar'
    # Presentation-only negative fixture, never inserted into the real ledger.
    altered = DeepReport(encoded(d), view.source_digest)
    assert reading(altered)['language_candidates'] == []
    d['evidence'][0]['quote'] = '<script>alert(1)</script> 中文占位'
    altered = DeepReport(encoded(d), view.source_digest)
    html = render(altered, directory.people['reviewer-demo'])
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert 'HUMAN_REVIEW_REQUIRED' in html


def test_original_source_cannot_be_reassigned_across_tenant_run():
    view = source().read()
    d = view.document
    d['native_context']['run_id'] = 'another-run'
    with pytest.raises(L2Denied):
        reading(DeepReport(encoded(d), view.source_digest))


def test_real_blocked_source_metadata_does_not_become_language_or_cta_failure(tmp_path):
    from integration.industry_l2.fixture import evidence_pack
    from vrae.industry.l2_v1 import diagnose, load
    from vrae.l2.native import NativeSource
    pack, _, transport = evidence_pack(statuses={'/contact': 403})
    industry = load(tenant_id=pack.document['tenant_id'])
    diagnosis = diagnose(pack, expected_pack_ref=pack.ref, expected_industry_ref=industry['industry_ref'])
    held = replace(source().held, native_pack_ref=pack.ref, industry_ref=industry['industry_ref'],
                   diagnosis_ref=diagnosis['diagnosis_ref'])
    native = NativeSource(pack, diagnosis, held=held)
    _, directory, _, _ = create(tmp_path)
    view = native.read()
    html = render(view, directory.people['reviewer-demo'])
    assert 'ACCESS_BLOCKED' in html
    assert '/contact' in html
    assert all(method == 'GET' for method, _ in transport.requests)
    assert all(r['result'] == 'UNKNOWN' for r in reading(view)['language_candidates'])
    for code in ('INFO-03', 'CTA-01', 'CTA-03', 'TECH-02'):
        block = html.split('data-rule="'+code+'"')[1].split('</li>')[0]
        assert 'UNKNOWN' in block and 'FAIL_WITH_EVIDENCE' not in block


def test_expired_reviewer_and_mid_render_revocation_cannot_read_new_view(tmp_path, monkeypatch):
    import time
    import apps.operator_console.l2_buyer_views as ui
    clock = [time.time()]
    issuer, directory, _, app = create(tmp_path, clock=lambda: clock[0])
    sid = login(issuer, directory, 'reviewer-demo')
    target = '/b5a/l2/r/'+REPORT+'/buyer-tasks'
    headers = {'Cookie': 'b5a_l2_session='+sid}
    actual = ui.render
    def revoked(*args):
        result = actual(*args)
        directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=False)
        return result
    monkeypatch.setattr(ui, 'render', revoked)
    response = app.deep.handle('GET', target, headers, b'').response
    assert response.status == 403 and b'l2-buyer-dimension' not in response.body
    directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=True)
    monkeypatch.setattr(ui, 'render', actual)
    clock[0] += 301
    assert app.deep.handle('GET', target, headers, b'').response.status == 403
