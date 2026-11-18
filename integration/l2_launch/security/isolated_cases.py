"""Real sockets only in the owned network-none/kernel-deny namespace."""
import asyncio
import os

import pytest

from tests.collection.test_isolated import lab, lab_access
from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.limits import Budget, Limits

from .adapter import isolated_fetcher
from .fixtures import permit, pins

pytestmark = pytest.mark.skipif(os.environ.get('R1A_ISOLATED_LAB') != '1', reason='OWNED_NETWORK_NONE_LAB_ONLY')


def components(host='factory.test'):
    original = lab_access(host=host)
    return isolated_fetcher(original, held=pins(original),
        permit=permit('https://'+host, ('/', '/robots.txt', '/products', '/contact')),
        nameservers=['93.184.216.53'], cafile='/tmp/lab/cert.pem')


def test_original_tls_collection_plus_connection_recheck_ignores_proxy_and_cookie(monkeypatch):
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy'):
        monkeypatch.setenv(key, 'http://127.0.0.1:8080')
    async def run():
        async with lab() as (requests, sni, bait, dns):
            access, fetcher = components()
            bundle = await Collector(fetcher).capture(access.held.run_id, access,
                limits=Limits(interval_seconds=0.01), retain_raw_html=True)
            bundle.verify()
            assert len(bundle.manifest['pages']) == 3 and len(requests) == 4
            assert all(b'Cookie:' not in r and b'Authorization:' not in r and b'POST ' not in r for r in requests)
            assert set(sni) == {'factory.test'} and not bait
            assert len(dns.queries) == 16  # A+AAAA twice, for all four requests.
            assert all(p['redirect_trace'][0]['peer_ip'] == '93.184.216.20' for p in bundle.manifest['pages'])
    asyncio.run(run())


def test_dns_change_after_hop_resolution_is_denied_before_any_http():
    def answer(kind, count):
        return (['93.184.216.20'] if count == 1 else ['169.254.169.254']) if kind == 1 else []
    async def run():
        async with lab(answer=answer) as (requests, _, bait, _):
            access, fetcher = components()
            budget = Budget(Limits(), access)
            budget.run_id = access.held.run_id
            with pytest.raises(CollectionError, match='SSRF_BLOCKED'):
                await fetcher.fetch(access.start_url, 'GET', budget)
            assert not requests and not bait
    asyncio.run(run())


def test_wrong_certificate_name_is_denied_through_the_new_fence():
    async def run():
        async with lab() as (requests, _, bait, _):
            access, fetcher = components('wrong.test')
            budget = Budget(Limits(), access)
            budget.run_id = access.held.run_id
            with pytest.raises(CollectionError, match='TLS_FAILED'):
                await fetcher.fetch(access.start_url, 'GET', budget)
            assert not requests and not bait
    asyncio.run(run())


def test_set_cookie_on_redirect_never_becomes_a_cookie_request():
    async def handler(target, writer):
        response = (b'HTTP/1.1 302 Found\r\nLocation: /products\r\n' if target == b'/' else b'HTTP/1.1 200 OK\r\n')
        writer.write(response+b'Set-Cookie: session=synthetic; Path=/\r\nContent-Length: 0\r\n\r\n')
        await writer.drain()
    async def run():
        async with lab(handler=handler) as (requests, _, bait, _):
            access, fetcher = components()
            budget = Budget(Limits(interval_seconds=0.01), access)
            budget.run_id = access.held.run_id
            result, trace = await fetcher.fetch(access.start_url, 'GET', budget)
            assert result.status == 200 and len(trace) == 2 and len(requests) == 2 and not bait
            assert all(b'Cookie:' not in r and b'Authorization:' not in r for r in requests)
    asyncio.run(run())


@pytest.mark.parametrize('address,port', [('10.77.0.2', 8080), ('169.254.169.254', 8080),
                                        ('127.0.0.1', 8080), ('::1', 8080)])
def test_kernel_alone_blocks_simulated_api_and_metadata_even_with_application_bypassed(address, port):
    async def run():
        entered = []
        async def trap(reader, writer):
            entered.append(True)
            writer.transport.abort()
        async with lab():
            server = await asyncio.start_server(trap, address, port)
            try:
                with pytest.raises((TimeoutError, OSError)):
                    async with asyncio.timeout(0.2):
                        _, writer = await asyncio.open_connection(address, port)
                        writer.transport.abort()
                assert not entered
                print('R1A_KERNEL_DENIAL', address, port, 'accepted=0', flush=True)
            finally:
                server.close()
                await server.wait_closed()
    asyncio.run(run())
