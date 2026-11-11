"""Fixed industrial source declarations; contact success and failure stay distinct."""
import asyncio

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from tests.findings.info01_synthetic import PRODUCT as PRIOR_PRODUCT
from tests.findings.seo01_synthetic import HEAD
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.evidence import build_pack
from vrae.rules import execute

BUILDER = 'ra2c3-1.0.0'
EVALUATOR = 'ra2b6-1.0.0'
DECLARATION = (b'<table><tr><th>Company name</th><td>SV Industrial Valve Works</td></tr></table>\n'
    b'<section><h2>Company profile</h2><p>We self-describe as a supplier of industrial valve components.</p></section>\n'
    b'<a href="mailto:sales@valves.example">Email sales</a>')
HOME = b'<html>\n' + HEAD + b'\n<body>\n' + DECLARATION + b'\n<nav><a href="/category/valves">Valves</a></nav></body></html>'
CONTACT = (b'<html><body>\n' + DECLARATION + b'\n<a href="/contact">Contact page</a>\n'
           b'<address>100 Synthetic Way</address>\n</body></html>')
PRODUCT = PRIOR_PRODUCT.replace(b'<a href="/rfq">RFQ</a>', b'')


def diagnostic_input(*, home=HOME, contact=CONTACT, contact_status=200, home_status=200,
                     retained=True, max_pages=5, robots=None, about=None):
    if about is not None:
        home = home.replace(b'</nav>', b'<a href="/about">About</a></nav>')
    routes = {
        'https://example.org/': (home_status, {'content-type': 'text/html'}, home),
        'https://example.org/category/valves': (200, {'content-type': 'text/html'},
            b'<html><a href="/products/sv-40">SV-40</a></html>'),
        'https://example.org/products/sv-40': (200, {'content-type': 'text/html'}, PRODUCT),
        'https://example.org/contact': (contact_status, {'content-type': 'text/html'}, contact),
        'https://example.org/robots.txt': (200, {'content-type': 'text/plain'},
            robots if robots is not None else b'User-agent: *\nDisallow:\n'),
        'https://example.org/about': (200, {'content-type': 'text/html'}, about or b'<html></html>'),
    }
    transport = SyntheticTransport(routes)
    source = asyncio.run(Collector(SafeFetcher(FixedDNS(), transport)).capture(
        'run-ra2c3-synthetic', access(), limits=Limits(max_pages=max_pages, interval_seconds=0.01),
        retain_raw_html=retained))
    assert all(call[1] == 'GET' for call in transport.calls)
    pack = build_pack([source])
    return pack, execute(pack, expected_pack_ref=pack.ref, evaluator_version=EVALUATOR)


def pins(pack, execution):
    return dict(expected_pack_ref=pack.ref, expected_execution_ref=execution['execution_ref'],
                expected_evaluator_version=EVALUATOR, expected_builder_version=BUILDER)
