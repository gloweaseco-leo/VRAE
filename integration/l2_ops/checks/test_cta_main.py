"""Original native task ports with pinned CTA references; not a Worker/PG proof."""
from contextlib import contextmanager
from dataclasses import replace

import pytest

from integration.l2.support import pins
from integration.l2_ops.checks.test_s2_acceptance_sources import ready
from integration.l2_ops.checks.test_native_tasks import runtime  # noqa: F401
from integration.l2_ops.checks.test_native_report import reviewed  # noqa: F401
from vrae.l2_ops.sources import OperationsDenied


def test_main_cta_preserves_existing_S2_S4_and_original_report(runtime):  # noqa: F811
    app, manager, _, headers, rid, _ = ready(runtime)
    business = app.native_business
    intake = business.intake
    ledger = app.deep.ledgers[rid]
    sid = app.deep.sid(headers)
    before = ledger.read(sid, rid)
    root = '/b5a/l2/r/'+rid
    for scenario, width in [('clean',390), ('hidden',390), ('covered',375), ('overflow',320)]:
        base = root+'/source-tasks/cta/'+scenario+'/'+str(width)
        reply = app.handle('GET', base, headers).response
        assert reply.status == 200 and b'cta-buyer-obstacle' in reply.body and b'cta-rebuild-advice' in reply.body
        assert reply.body.count(b'data-target=') == 2
        image = app.handle('GET', base+'/image', headers).response
        assert image.status == 200 and image.content_type == 'image/png'
    page = app.handle('GET', root+'/source-tasks', headers).response
    assert page.body.count(b'data-key="buyer-task-card"') == 2 and b'cta-review-candidates' in page.body
    assert business is app.native_business and app.native_tasks is manager and business.intake is intake
    assert ledger.read(sid, rid).payload == before.payload
    assert app.handle('GET',root+'/executive',headers).response.status == 200
    assert business.route(root+'/brief/retry') == rid


@pytest.mark.parametrize('negative', ['unsigned','post','other_tenant','revoked','expired','version','task','receipt'])
def test_main_cta_details_and_PNG_keep_original_boundaries(runtime, monkeypatch, negative):  # noqa: F811
    app, manager, _, headers, rid, _ = ready(runtime)
    ledger = app.deep.ledgers[rid]
    sid = app.deep.sid(headers)
    method = 'GET'
    if negative == 'unsigned':
        headers = {k:v for k,v in headers.items() if k != 'Cookie'}
    elif negative == 'post':
        method = 'POST'
    elif negative in ('other_tenant','revoked'):
        person = manager.directory.people['runtime-reviewer']
        manager.directory.people['runtime-reviewer'] = replace(person, **({'tenant_id':'tenant-other'} if negative=='other_tenant' else {'active':False}))
    elif negative == 'expired':
        original_clock = manager.directory.clock
        monkeypatch.setattr(manager.directory,'clock',lambda:original_clock()+7200)
    elif negative == 'version':
        report = ledger.read(sid, rid)
        ledger.revise(sid,rid,**pins(report),changes={report.document['blueprint'][0]['id']:'按原接口显式修订；旧CTA引用不自动继承新版本。'})
    elif negative == 'receipt':
        app.native_business.source_views[rid].binding.cta.expected = '0'*64
    elif negative == 'task':
        @contextmanager
        def denied():
            raise OperationsDenied('ORIGINAL_TASK_DENIED')
            yield
        monkeypatch.setattr(manager,'access',denied)
    for suffix in ('','/image'):
        reply = app.handle(method,'/b5a/l2/r/'+rid+'/source-tasks/cta/covered/375'+suffix,headers).response
        assert reply.status == 403 and reply.content_type != 'image/png' and b'cta-source-detail' not in reply.body
