"""Industrial parts fixtures through the existing offline synthetic collector."""
import asyncio

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.evidence import build_pack


def site(status=200, *, retained=True, linked=True, markup=None, target=True):
    body = markup if markup is not None else (
        b'<html><body><nav><a href="/category/valves">Industrial valves</a></nav></body></html>'
        if linked else b'<html><body>Industrial parts</body></html>')
    routes = {'https://example.org/': (200, {'content-type': 'text/html'}, body),
              'https://example.org/category/valves':
                  (status, {'content-type': 'text/html'}, b'<html>Valve catalog</html>')}
    routes['https://example.org/robots.txt'] = (
        200, {'content-type': 'text/plain'}, b'User-agent: *\nDisallow:\n')
    collector = Collector(SafeFetcher(FixedDNS(), SyntheticTransport(routes)))
    source = asyncio.run(collector.capture('run-synthetic', access(),
        limits=Limits(max_pages=5 if target else 1, interval_seconds=0.01),
        retain_raw_html=retained))
    return build_pack([source])
