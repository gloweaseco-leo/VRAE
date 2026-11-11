"""Offline source evidence and independent raw-line checks, never live collection."""
from copy import deepcopy
import asyncio
import json
from pathlib import Path

import pytest

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError, EvidencePack, build_pack
from vrae.rules.product_facts import extract, verify_facts

FIXTURES = Path(__file__).parents[1] / 'fixtures/sites'


def product_pack(name='valve', *, markup=None, retained=True, max_pages=3, blocked=None,
                 status=200):
    body = markup if markup is not None else (FIXTURES / f'product-info-{name}.html').read_bytes()
    url = 'https://example.org/products/sv-40'
    routes = {'https://example.org/': (200, {'content-type': 'text/html'},
              b'<html><body><a href="/products/sv-40">SV-40</a></body></html>'),
              url: (status, {'content-type': 'text/html'}, body),
              'https://example.org/robots.txt': (200, {'content-type': 'text/plain'},
              b'User-agent: *\nDisallow:\n')}
    if blocked == 'waf':
        routes[url] = (200, {'content-type': 'text/html'}, b'<html>Verify you are human</html>')
    elif blocked == 'robots':
        routes['https://example.org/robots.txt'] = (200, {'content-type': 'text/plain'},
            b'User-agent: *\nDisallow: /products/\n')
    transport = SyntheticTransport(routes)
    collector = Collector(SafeFetcher(FixedDNS(), transport))
    bundle = asyncio.run(collector.capture('run-product-info', access(),
        limits=Limits(max_pages=max_pages, interval_seconds=0.01), retain_raw_html=retained))
    assert all(call[1] == 'GET' for call in transport.calls)
    return build_pack([bundle])


def run(pack):
    return extract(pack, expected_pack_ref=pack.ref)


def test_independent_raw_line_review_and_replay():
    pack = product_pack()
    result = run(pack)
    page = result['pages'][0]
    assert page['status'] == 'EXTRACTED'
    assert page['name']['text'] == 'SV-40 flanged isolation valve'
    assert [(f['label']['text'], f['value']['text']) for f in page['fields']] == [
        ('Body material', 'Stainless steel 316L'), ('Nominal pressure', 'PN 40 (4.0 MPa)'),
        ('Nominal diameter', 'DN 50')]
    pressure = page['fields'][1]
    assert pressure['label']['element']['line'] == 10
    assert pressure['value']['element']['column'] == 29
    for citation in [page['name']] + [f[k] for f in page['fields'] for k in ('label', 'value')]:
        resolved = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
        raw = resolved['content'].decode('utf-8')
        element = citation['element']
        line = raw.splitlines()[element['line'] - 1][element['column']:]
        assert line.startswith(element['start_tag'] + citation['text'] + '</')
        assert citation['content_sha256'] == resolved['evidence']['content_sha256']
        assert citation['snapshot_ref'] == resolved['snapshot']['snapshot_ref']
    assert not result['info01_enabled'] and result['info01_result'] == 'UNKNOWN'
    assert result == run(pack)
    verify_facts(result, pack, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('fixture,reason', [('empty', 'EMPTY_STATIC_VALUE'),
    ('conflict', 'DUPLICATE_LABEL'), ('no-parameters', None), ('variant', None)])
def test_gaps_are_not_defects(fixture, reason):
    page = run(product_pack(fixture))['pages'][0]
    assert page['status'] == 'UNKNOWN'
    if reason:
        assert any(f['reason'] == reason for f in page['fields'])


@pytest.mark.parametrize('kwargs,status', [({'retained': False}, 'UNKNOWN'),
    ({'max_pages': 1}, None), ({'blocked': 'waf'}, 'ACCESS_BLOCKED'),
    ({'status': 403}, 'ACCESS_BLOCKED'), ({'status': 500}, 'UNKNOWN'),
    ({'blocked': 'robots'}, 'ACCESS_BLOCKED')])
def test_capture_gaps(kwargs, status):
    result = run(product_pack(**kwargs))
    assert (result['pages'][0]['status'] if result['pages'] else None) == status
    assert result['info01_result'] == 'UNKNOWN'


@pytest.mark.parametrize('raw', [b'<html><h1>X</h1><table><tr><th>Size</th><td>50',
    b'<html><h1>X</h1><h1>Y</h1></html>',
    b'<html><h1>X</h1><script>render()</script></html>',
    b'<html><div hidden><h1>X</h1></div></html>',
    b'<html><h1>X</h1><table><tr><td>Size</td><td>50</td></tr></table></html>',
    b'<html><h1>X</h1><dl><dt>Size</dt><dd>50</dd></dl></html>'])
def test_unsupported_markup(raw):
    pack = product_pack(markup=raw)
    assert run(pack)['pages'][0]['status'] == 'UNKNOWN'


@pytest.mark.parametrize('pin', [None, '', 'ep-' + '0' * 64])
def test_untrusted_pin(pin):
    with pytest.raises(EvidenceError):
        extract(product_pack(), expected_pack_ref=pin)


@pytest.mark.parametrize('mutation', ['tenant_id', 'run_id', 'blob', 'duplicate'])
def test_tampered_pack(mutation):
    pack = product_pack()
    doc, blobs = pack.document, dict(pack.objects)
    if mutation == 'blob':
        blobs[next(iter(blobs))] = b'fabricated'
    elif mutation == 'duplicate':
        doc['snapshots'].append(deepcopy(doc['snapshots'][0]))
    else:
        doc[mutation] = 'other-scope'
    forged = EvidencePack(json.dumps(doc).encode(), tuple(sorted(blobs.items())))
    with pytest.raises(EvidenceError):
        extract(forged, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('mutation', ['text', 'position', 'evidence', 'scope', 'enabled'])
def test_resealed_output_rejected(mutation):
    pack = product_pack()
    output = run(pack)
    citation = output['pages'][0]['fields'][0]['value']
    if mutation == 'text':
        citation['text'] = 'Gold'
    elif mutation == 'position':
        citation['element']['column'] = 0
    elif mutation == 'evidence':
        citation['evidence_ref'] = 'ev-' + '0' * 64
    elif mutation == 'scope':
        output['tenant_id'] = 'other-tenant'
    else:
        output['info01_enabled'] = True
    output['facts_ref'] = 'pf-' + document_hash({k: v for k, v in output.items() if k != 'facts_ref'})
    with pytest.raises(EvidenceError):
        verify_facts(output, pack, expected_pack_ref=pack.ref)


def test_old_pack_pin_rejects_other_valid_pack():
    old, new = product_pack(), product_pack('empty')
    with pytest.raises(EvidenceError):
        extract(new, expected_pack_ref=old.ref)


def test_utf8_entities_and_exact_whitespace_are_retained():
    pack = product_pack(markup=('<html><h1>阀门 &amp; valve</h1><table><tbody>'
        '<tr><th> 材质 </th><td> 316L &amp; PTFE </td></tr>'
        '</tbody></table></html>').encode('utf-8'))
    row = run(pack)['pages'][0]
    assert row['status'] == 'EXTRACTED'
    assert row['name']['text'] == '阀门 & valve'
    assert row['fields'][0]['value']['text'] == ' 316L & PTFE '


def test_extraction_does_not_enable_or_change_existing_rules():
    from vrae.rules import execute
    pack = product_pack()
    before = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b1-1.0.0')
    run(pack)
    assert execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b1-1.0.0') == before
    info = next(r for r in before['executions'] if r['rule_id'] == 'INFO-01')
    assert not info['enabled'] and info['observations'][0]['observation']['result'] == 'UNKNOWN'
