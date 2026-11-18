"""Synthetic saved sources, unchanged Collector and in-memory HTTP transport."""
import asyncio
from pathlib import Path

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.evidence import build_pack

DIRECTORY = Path(__file__).parents[1] / 'fixtures/industry/l2-industrial-v1'


def table(kind, fields):
    return ('<html><body><h1>Offline source declaration</h1><table>'
            '<tr><th>Record type</th><td>' + kind + '</td></tr>' + ''.join(
                '<tr><th>' + k + '</th><td>' + v + '</td></tr>' for k, v in fields.items())
            + '</table></body></html>').encode()


def identity(*, name='Demo Meridian', address='10 Demo Road', entity='DEMO-001',
             namespace='source-declared-registration', email='buyer@example.org'):
    return table('Supplier identity', {'Entity identifier': entity,
        'Identifier namespace': namespace, 'Company name': name,
        'Postal address': address, 'Contact email': email, 'Contact telephone': '+1-555-0100'})


def fixture(*, overrides=None, statuses=None, retain=True):
    products = {}
    for path, file in (('/products/p40', 'pump.html'), ('/products/v25', 'valve.html')):
        products[path] = (DIRECTORY / file).read_bytes().replace(b'</table>',
            b'<tr><th>Data revision</th><td>R1</td></tr>'
            b'<tr><th>Specification conditions</th><td>Water at 20 degC; source-listed nominal values</td></tr></table>')
    proof = (DIRECTORY / 'proof.html').read_bytes().replace(b'</table>',
        b'<tr><th>Proof type</th><td>certificate</td></tr></table>')
    routes = {'/robots.txt': b'User-agent: *\nDisallow:\n',
        '/': b'<html><body><nav><a href="/products">Products</a><a href="/about">About</a><a href="/contact">Contact</a></nav></body></html>',
        '/products': b'<html><body><h1>Catalog</h1><a href="/products/p40">P40</a><a href="/products/v25">V25</a><a href="/products/proof">Proof</a></body></html>',
        **products, '/products/proof': proof, '/about': identity(), '/contact': identity()}
    routes.update(overrides or {})
    statuses = statuses or {}
    responses = {'https://example.org' + path: (statuses.get(path, 200),
        {'content-type': 'text/plain' if path == '/robots.txt' else 'text/html'}, body)
        for path, body in routes.items()}
    collector = Collector(SafeFetcher(FixedDNS(), SyntheticTransport(responses)))
    bundle = asyncio.run(collector.capture('run-synthetic', access(),
        limits=Limits(max_pages=8, interval_seconds=0.01), retain_raw_html=retain))
    return build_pack([bundle])
