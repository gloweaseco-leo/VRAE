"""Synthetic bounded adaptive collection; never contacts a customer or model."""
import asyncio
from copy import deepcopy

import pytest

from vrae.collection.adaptive import Investigation, proposals
from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Budget, Limits
from vrae.collection.manifest import CaptureBundle, document_hash
from .test_pipeline import FixedDNS, SyntheticTransport
from .test_security import access

ORIGIN = 'https://example.org'
PRODUCT = b'''<html><body><main><h1>Wheel W100</h1>
<a href="/help/specs">Technical data</a><a href="/help/use">Application guide</a>
</main></body></html>'''


def collect(*, adaptive=True, cap=6, product=PRODUCT, blocked=False):
    paths = ['/products', '/products/wheel', '/contact', '/about', '/aa-noise']
    home = b'<html><body><nav>'+b''.join(f'<a href="{p}">Page</a>'.encode() for p in paths)+b'</nav></body></html>'
    routes = {'/':home, '/products':home, '/contact':b'<html><main>Contact</main></html>',
        '/about':b'<html><main><a href="/help/proof">Certificate</a></main></html>',
        '/products/wheel':product, '/aa-noise':b'<html><main>Other</main></html>',
        '/help/specs':b'<html><main>Retained technical material<a href="/products/deeper">Technical data</a></main></html>',
        '/help/use':b'<html><main>Application information</main></html>',
        '/help/proof':b'<html><main>Supplier stated proof</main></html>'}
    responses = {ORIGIN+p:(200, {'content-type':'text/html'}, body) for p,body in routes.items()}
    robots = b'User-agent: *\nDisallow: /help/specs\n' if blocked else b'User-agent: *\nDisallow:\n'
    responses[ORIGIN+'/robots.txt'] = (200, {'content-type':'text/plain'}, robots)
    transport = SyntheticTransport(responses)
    bundle = asyncio.run(Collector(SafeFetcher(FixedDNS(),transport)).capture('run-adaptive',access(),
        limits=Limits(max_pages=cap, interval_seconds=.01), retain_raw_html=True,
        representative_pages=True, labelled_contacts=True, adaptive_investigation=adaptive))
    return bundle, transport


def test_spare_page_replaces_noise_after_baseline_and_records_original_link():
    bundle, transport = collect()
    pages = bundle.manifest['pages']
    assert [p['snapshot']['url'] for p in pages[:5]] == [ORIGIN+p for p in
        ('/', '/products', '/products/wheel', '/contact', '/about')]
    assert pages[5]['snapshot']['url'] == ORIGIN+'/help/specs'
    decision = bundle.manifest['adaptive_investigation']['decisions'][0]
    assert decision['source_page_index'] == 2 and decision['target_page_index'] == 5
    assert decision['purpose'] == 'TECHNICAL_MATERIAL'
    assert PRODUCT[decision['byte_start']:decision['byte_end']] == b'<a href="/help/specs">Technical data</a>'
    assert len(transport.calls) == 7
    bundle.verify()


def test_opt_out_preserves_original_manifest_and_selection():
    bundle, _ = collect(adaptive=False)
    assert 'adaptive_investigation' not in bundle.manifest
    assert bundle.manifest['pages'][5]['snapshot']['url'] == ORIGIN+'/aa-noise'


def test_max_two_unique_purposes_no_recursive_follow_or_page_budget_increase():
    bundle, transport = collect(cap=8)
    decisions = bundle.manifest['adaptive_investigation']['decisions']
    assert [d['purpose'] for d in decisions] == ['TECHNICAL_MATERIAL','APPLICATION_CONTEXT']
    assert len(bundle.manifest['pages']) == 8
    assert not any('/products/deeper' in url for url, *_ in transport.calls)
    assert any(i['url'].endswith('/products/deeper') for i in bundle.manifest['inventory'])


def test_existing_structured_fields_and_application_do_not_trigger_product_gaps():
    html = PRODUCT.replace(b'<h1>Wheel W100</h1>',b'<h1>Wheel W100</h1><table><tr><th>Usage</th><td>Grinding</td></tr></table>')
    result = proposals(html,ORIGIN+'/products/wheel',2,{ORIGIN+'/help/specs',ORIGIN+'/help/use'})
    assert result == []
    bundle, _ = collect(product=html)
    assert bundle.manifest['adaptive_investigation']['decisions'][0]['purpose'] == 'PROOF_CONTEXT'


@pytest.mark.parametrize('html', [
    PRODUCT.replace(b'<main>', b'<nav>').replace(b'</main>', b'</nav>'),
    PRODUCT.replace(b'<main>', b'<main hidden>'),
    PRODUCT.replace(b'<main>', b'<main><base href="https://evil.org/">'),
    PRODUCT.replace(b'<h1>Wheel W100</h1>', b'<h1>A</h1><h1>B</h1>'),
    b'X'*131073,
], ids=['nav','hidden','base','ambiguous','oversize'])
def test_unsupported_or_hidden_source_is_not_a_gap(html):
    assert proposals(html,ORIGIN+'/products/wheel',2,{ORIGIN+'/help/specs',ORIGIN+'/help/use'}) == []


def test_targets_must_be_in_checked_inventory_and_same_origin_https_html():
    assert proposals(PRODUCT,ORIGIN+'/products/wheel',2,set()) == []
    for href in ['https://evil.org/specs','http://example.org/specs','/specs?token=x','/specs#secret','javascript:fetch(1)']:
        html = PRODUCT.replace(b'/help/specs', href.encode())
        assert not any(p['purpose']=='TECHNICAL_MATERIAL' for p in proposals(html,
            ORIGIN+'/products/wheel',2,{href}))


def test_robots_denial_stays_recorded_without_dispatching_denied_page():
    bundle, transport = collect(blocked=True)
    assert not any(url==ORIGIN+'/help/specs' for url,*_ in transport.calls)
    assert bundle.manifest['pages'][5]['snapshot']['status'] == 'ACCESS_BLOCKED'
    assert bundle.manifest['pages'][5]['error']['code'] == 'ROBOTS_DISALLOWED'
    assert len(bundle.manifest['pages']) == 6


def test_no_spare_page_and_time_gate_never_expand_budget():
    bundle, _ = collect(cap=5)
    assert not bundle.manifest['adaptive_investigation']['decisions']
    investigation = Investigation()
    investigation.observe(PRODUCT,ORIGIN+'/products/wheel',0,{ORIGIN+'/help/specs'})
    def clock():
        return 0
    budget = Budget(Limits(task_seconds=1,interval_seconds=.01),access(),clock=clock)
    candidate = {'url':ORIGIN+'/help/specs','role':'OTHER'}
    assert investigation.choose([candidate],candidate,set(),{'PRODUCT'},budget,1,set()) is None
    assert investigation.last_gate == 'TIME_BUDGET_RESERVED'


def test_revocation_between_selection_and_attempt_keeps_prior_evidence(monkeypatch):
    original = Investigation.choose
    def revoked(self, *args, **kwargs):
        selected = original(self, *args, **kwargs)
        if selected:
            args[4].access.provider = lambda: None
        return selected
    monkeypatch.setattr(Investigation,'choose',revoked)
    bundle, transport = collect()
    assert len(bundle.manifest['pages']) == 5
    assert bundle.manifest['errors'][0]['code'] == 'POLICY_REQUIRED'
    assert not bundle.manifest['adaptive_investigation']['decisions']
    assert not any(url==ORIGIN+'/help/specs' for url,*_ in transport.calls)
    bundle.verify()


@pytest.mark.parametrize('mutate', [lambda d:d.update(source_sha256='0'*64),
    lambda d:d.update(trigger='NO_APPLICATION_FIELD_RECORDED'),
    lambda d:d.update(source_page_index=5),lambda d:d.update(byte_end=1),
    lambda d:d.update(target_url=ORIGIN+'/aa-noise')])
def test_resealed_manifest_rejects_changed_adaptive_source_relationship(mutate):
    bundle, _ = collect()
    doc = deepcopy(bundle.manifest)
    mutate(doc['adaptive_investigation']['decisions'][0])
    del doc['manifest_sha256']
    doc['manifest_sha256'] = document_hash(doc)
    with pytest.raises((CollectionError,ValueError)):
        CaptureBundle(doc,bundle.objects).verify()
