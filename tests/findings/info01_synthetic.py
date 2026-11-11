"""Fixed transport only: positive source text and a separate broken contact href."""
from tests.collection.test_pipeline import collect
from vrae.evidence import build_pack
from vrae.rules import execute

BUILDER = 'ra2c1-1.0.0'
EVALUATOR = 'ra2b3-1.0.0'
PRODUCT = b'''<html>
<main>
<h1>SV-40 flanged isolation valve</h1>
<table>
<tr><th>Body material</th><td>Stainless steel 316L</td></tr>
<tr><th>Nominal pressure</th><td>PN 40 (4.0 MPa)</td></tr>
<tr><th>Nominal diameter</th><td>DN 50</td></tr>
</table>
<a href="/contact">Contact</a><a href="/rfq">RFQ</a>
</main></html>'''


def diagnostic_input():
    routes = {
        'https://example.org/': (200, {'content-type': 'text/html'},
            b'<html><nav><a href="/category/valves">Valves</a></nav></html>'),
        'https://example.org/category/valves': (200, {'content-type': 'text/html'},
            b'<html><a href="/products/sv-40">SV-40</a></html>'),
        'https://example.org/products/sv-40': (200, {'content-type': 'text/html'}, PRODUCT),
        'https://example.org/contact': (404, {'content-type': 'text/html'}, b'<html>404</html>'),
        'https://example.org/rfq': (403, {'content-type': 'text/html'}, b'blocked'),
    }
    bundle, transport = collect(routes, retain_raw_html=True)
    assert all(call[1] == 'GET' for call in transport.calls)
    pack = build_pack([bundle])
    return pack, execute(pack, expected_pack_ref=pack.ref, evaluator_version=EVALUATOR)
