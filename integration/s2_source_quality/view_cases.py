"""Original signed C2 context and version checks remain the sole read authority."""
import json
from copy import deepcopy
from dataclasses import replace

import pytest

from integration.l2.support import login
from integration.s2_buyer_workbench.test_workbench import headers
from vrae.rules.s2.source_quality import evaluate_source_quality

from . import workbench
from .fixture import application, prepared


@pytest.fixture(scope='module')
def setup(tmp_path_factory):
    return application(tmp_path_factory.mktemp('quality-c2'))


def request(s, subject='reviewer-demo', suffix='', method='GET'):
    issuer, directory, _, app, _, _, rid = s
    sid = login(issuer, directory, subject)
    return sid, app.handle(method, '/b5a/l2/r/'+rid+'/source-quality'+suffix, headers(sid)).response


def test_existing_five_dimension_template_and_source_bytes_are_readable(setup):
    sid, response = request(setup)
    assert response.status == 200
    text = response.body.decode()
    assert text.count('data-task=') == 5 and 'INFO-03' in text and 'TECH-02' in text
    assert '采购影响假设' in text and 'Rebuild候选' in text and 'UNKNOWN' in text and 'NOT_EVALUABLE' in text
    assert 'alt属性' in text and 'HTTP 200' in text and 'NPSH' in text
    before = setup[2].source.read().payload
    _, citation = request(setup, suffix='/cite/0/0')
    assert citation.status == 200 and '&lt;html' in citation.body.decode()
    assert setup[2].read(sid, setup[-1]).payload == before


@pytest.mark.parametrize('subject', ['other-tenant', 'recipient-a'])
def test_original_tenant_and_unclaimed_reader_deny(setup, subject):
    _, response = request(setup, subject=subject)
    assert response.status == 403 and b'quality-clue' not in response.body


def test_unsigned_post_or_forged_row_does_not_return_data(setup):
    app, rid = setup[3], setup[-1]
    assert app.handle('GET', '/b5a/l2/r/'+rid+'/source-quality', headers()).response.status == 403
    assert request(setup, method='POST')[1].status == 403
    assert request(setup, suffix='/cite/99/999')[1].status == 403


def test_rehashed_payload_or_source_metadata_is_never_rendered(setup):
    component = setup[3].native_business
    old = component.payload
    bad = deepcopy(json.loads(old))
    bad['rows'][0]['selection']['model'] = 'forged'
    component.payload = json.dumps(bad).encode()
    try:
        assert request(setup)[1].status == 403
    finally:
        component.payload = old


def test_revocation_during_view_blocks_output(setup, monkeypatch):
    directory = setup[1]
    original = directory.people['reviewer-demo']
    renderer = workbench.render
    def revoked(*args):
        text = renderer(*args)
        directory.people['reviewer-demo'] = replace(original, active=False)
        return text
    monkeypatch.setattr(workbench, 'render', revoked)
    try:
        assert request(setup)[1].status == 403
    finally:
        directory.people['reviewer-demo'] = original


def test_source_entry_extension_does_not_replace_original_report_or_review(setup):
    issuer, directory, ledger, app, _, _, rid = setup
    sid = login(issuer, directory, 'reviewer-demo')
    response = app.handle('GET', '/b5a/l2/r/'+rid+'/source-tasks', headers(sid)).response
    assert response.status == 200 and b'quality-entry' in response.body
    assert app.deep.ledgers[rid] is ledger and app.native_tasks is None


def test_hostile_alt_text_is_escaped_and_not_executed_or_promoted():
    pack, parent, held = prepared('hostile')
    value = evaluate_source_quality(pack, parent, held=held)
    html = workbench.render(value, '/controlled')
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert value['shareable'] is False and value['is_report'] is False
