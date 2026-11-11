"""One verified broken contact path, positive steps and a separately blocked RFQ."""
from tests.collection.test_pipeline import collect
from vrae.evidence import build_pack
from vrae.rules import execute


def diagnostic_input():
    source, _ = collect({
        'https://example.org/': (200, {'content-type': 'text/html'},
            b'<html><nav><a href="/category/valves">Industrial valves</a></nav></html>'),
        'https://example.org/category/valves': (200, {'content-type': 'text/html'},
            b'<html><a href="/products/valve-v1">Valve V1</a></html>'),
        'https://example.org/products/valve-v1': (200, {'content-type': 'text/html'},
            b'<html><h1>Valve V1</h1><a href="/contact">Contact</a><a href="/rfq">RFQ</a></html>'),
        'https://example.org/contact': (404, {'content-type': 'text/html'}, b'<html>404</html>'),
        'https://example.org/rfq': (403, {'content-type': 'text/html'}, b'blocked'),
    }, retain_raw_html=True)
    pack = build_pack([source])
    return pack, execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b1-1.0.0')
