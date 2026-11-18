"""Accepted C1/C2 projection plus original signed SSR, no full Worker claim."""
from integration.l2.support import create, login, REPORT
from vrae.l2.executive import project
from vrae.l2_ops.intake_panel import cost_books


def test_native_comparisons_do_not_become_website_obstacles(native_source):
    source, _ = native_source
    view = source.read()
    before = view.payload
    result = project(view)
    assert result['d1_count'] == 0 and result['top_obstacles'] == []
    assert result['blueprint_count'] == 7
    assert result['groups']['D3'] and result['groups']['D4']
    assert len(result['coverage']) == 5
    assert all(c['whole_site_denominator'] is None for c in result['coverage'])
    assert result['service_catalog_status'] == 'SERVICE_CATALOG_PENDING'
    assert result['service_catalog_version'] is None
    assert view.payload == before and project(view) == result


def test_summary_uses_original_current_signature_and_document_fallback(tmp_path):
    issuer, directory, ledger, app = create(tmp_path)
    sid = login(issuer, directory, 'reviewer-demo')
    root = '/b5a/l2/r/'+REPORT
    app.origin = 'http://127.0.0.1:41903'
    headers = {'Host': '127.0.0.1:41903', 'Cookie': 'b5a_l2_session='+sid}
    for suffix in ('/executive', '/executive-document'):
        page = app.handle('GET', root+suffix, headers)
        assert page.response.status == 200
        text = page.response.body.decode()
        assert 'HYPOTHESIS' in text and 'SERVICE_CATALOG_PENDING' in text
        assert 'UNKNOWN' in text and '源' in text
        assert '非正式人审' in text and 'harbor-pump.invalid' in text
        assert app.handle('GET', root+suffix, {}).response.status == 403
    directory.revoked_keys.add(directory.jwks['keys'][0]['kid'])
    assert app.handle('GET', root+'/executive', headers).response.status == 403


def test_four_books_never_price_missing_measurements_as_zero():
    books = cost_books({'activities': []})
    assert len(books) == 4
    assert all(b['amount_micros'] is None and b['cost_status'] == 'UNKNOWN' for b in books)
