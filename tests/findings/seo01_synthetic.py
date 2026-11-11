"""Offline industrial source facts, one broken contact href and a blocked RFQ."""
from tests.collection.test_pipeline import collect
from tests.findings.info01_synthetic import PRODUCT
from vrae.evidence import build_pack
from vrae.rules import execute

BUILDER = 'ra2c2-1.0.0'
EVALUATOR = 'ra2b4-1.0.0'
HEAD = (b'<head>\n<title>SV industrial valves &amp; components</title>\n'
        b'<link rel="canonical" href="/">\n'
        b'<meta name="description" content="Synthetic industrial valve catalog">\n</head>')
HOME = b'<html>\n' + HEAD + b'\n<body><nav><a href="/category/valves">Valves</a></nav></body></html>'


def diagnostic_input(*, home=HOME, retained=True, contact_status=404, home_status=200, robots=None):
    routes = {
        'https://example.org/': (home_status, {'content-type': 'text/html'}, home),
        'https://example.org/category/valves': (200, {'content-type': 'text/html'},
            b'<html><a href="/products/sv-40">SV-40</a></html>'),
        'https://example.org/products/sv-40': (200, {'content-type': 'text/html'}, PRODUCT),
        'https://example.org/contact': (contact_status, {'content-type': 'text/html'},
            b'<html>Contact endpoint response</html>'),
        'https://example.org/rfq': (403, {'content-type': 'text/html'}, b'blocked'),
    }
    if robots is not None:
        routes['https://example.org/robots.txt'] = (200, {'content-type': 'text/plain'}, robots)
    source, transport = collect(routes, retain_raw_html=retained)
    assert all(call[1] == 'GET' for call in transport.calls)
    pack = build_pack([source])
    return pack, execute(pack, expected_pack_ref=pack.ref, evaluator_version=EVALUATOR)


def pins(pack, execution):
    return dict(expected_pack_ref=pack.ref, expected_execution_ref=execution['execution_ref'],
                expected_evaluator_version=EVALUATOR, expected_builder_version=BUILDER)
