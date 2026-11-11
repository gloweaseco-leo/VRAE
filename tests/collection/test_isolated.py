"""Real DNS, TCP and TLS in --network none + deny-by-default kernel firewall.

These tests never run on the host or a routable Docker network. The entrypoint sets
only loopback aliases, then permanently drops capabilities before pytest starts.
"""
import asyncio
from contextlib import asynccontextmanager
import os
import json
from pathlib import Path
import ssl
import time

import dns.message
import dns.rdatatype
import dns.rrset
import pytest

from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.http_transport import PinnedTransport
from vrae.collection.limits import Budget, Limits
from vrae.collection.policy import SourceAccess
from vrae.collection.resolver import DNSResolver
from .test_security import fixture, NOW

pytestmark = pytest.mark.skipif(os.environ.get("VRAE_ISOLATED_LAB") != "1",
    reason="Requires disposable --network none firewall lab; never run on host")


def lab_access(path="/", host="factory.test"):
    request, policy = fixture("AuditRequest"), fixture("SourcePolicy")
    request["site_url"] = "https://" + host + path
    policy["permitted_hosts"] = [host]
    return SourceAccess(request, lambda: policy, terms_reference="synthetic-terms", now=lambda: NOW)


class DNS(asyncio.DatagramProtocol):
    def __init__(self, answer):
        self.answer = answer
        self.queries = []

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, address):
        query = dns.message.from_wire(data)
        question = query.question[0]
        self.queries.append((str(question.name), question.rdtype))
        response = dns.message.make_response(query)
        values = self.answer(question.rdtype, len(self.queries))
        if values:
            response.answer.append(dns.rrset.from_text(question.name, 0, "IN", question.rdtype, *values))
        self.transport.sendto(response.to_wire(), address)


@asynccontextmanager
async def lab(handler=None, answer=None):
    assert set(os.listdir("/sys/class/net")) == {"lo"}
    assert os.geteuid() == 65532
    status = Path("/proc/self/status").read_text()
    assert "CapEff:\t0000000000000000" in status
    assert "NoNewPrivs:\t1" in status
    requests, sni, bait = [], [], []
    tasks = set()
    async def serve(reader, writer):
        tasks.add(asyncio.current_task())
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            requests.append(request)
            target = request.split(b" ")[1]
            if handler is not None:
                await handler(target, writer)
            else:
                body = (b"User-agent: *\nDisallow:\n" if target == b"/robots.txt" else
                        b'<html><a href="/products">Catalog</a><a href="/contact">Contact</a></html>')
                mime = b"text/plain" if target == b"/robots.txt" else b"text/html"
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: " + mime +
                             b"\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError, ssl.SSLError):
            pass
        finally:
            writer.transport.abort()
            tasks.discard(asyncio.current_task())
    async def trap(reader, writer):
        bait.append(writer.get_extra_info("sockname"))
        writer.transport.abort()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("/tmp/lab/cert.pem", "/tmp/lab/key.pem")
    context.set_servername_callback(lambda sock, name, ctx: sni.append(name))
    dns_protocol = DNS(answer or (lambda kind, count: ["93.184.216.20"] if kind == dns.rdatatype.A else []))
    dns_transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: dns_protocol, local_addr=("93.184.216.53", 53))
    servers = []
    try:
        servers.append(await asyncio.start_server(serve, "93.184.216.20", 443, ssl=context))
        servers.append(await asyncio.start_server(serve, "93.184.216.20", 80))
        for address in ("127.0.0.1", "169.254.169.254", "10.77.0.2", "93.184.216.21", "::1"):
            servers.append(await asyncio.start_server(trap, address, 80))
        yield requests, sni, bait, dns_protocol
    finally:
        dns_transport.close()
        for server in servers:
            server.close()
            await server.wait_closed()
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*list(tasks), return_exceptions=True)
        print("NETWORK_EVIDENCE " + json.dumps({
            "test": os.environ.get("PYTEST_CURRENT_TEST"),
            "http_request_lines": [r.split(b"\r\n", 1)[0].decode("ascii") for r in requests],
            "sni": sni, "bait_connections": len(bait),
            "dns_queries": dns_protocol.queries, "uid": os.geteuid(),
            "interfaces": os.listdir("/sys/class/net"), "external_routes": False,
        }, sort_keys=True), flush=True)


def fetcher(trust=True):
    return SafeFetcher(DNSResolver(["93.184.216.53"]),
                       PinnedTransport(cafile="/tmp/lab/cert.pem" if trust else None))


def test_real_dns_tls_peer_host_and_evidence(monkeypatch):
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(key, "http://127.0.0.1:80")
    async def run():
        async with lab() as (requests, sni, bait, dns_server):
            bundle = await Collector(fetcher()).capture("run-isolated", lab_access(),
                limits=Limits(interval_seconds=0.01), retain_raw_html=True)
            bundle.verify()
            assert len(bundle.manifest["pages"]) == 3
            assert all(p["snapshot"]["status"] == "FETCHED" for p in bundle.manifest["pages"])
            assert set(sni) == {"factory.test"}
            assert all(b"Host: factory.test" in r for r in requests)
            assert all(b"Authorization:" not in r and b"Cookie:" not in r for r in requests)
            assert {kind for _, kind in dns_server.queries} == {dns.rdatatype.A, dns.rdatatype.AAAA}
            assert all(p["redirect_trace"][0]["peer_ip"] == "93.184.216.20" for p in bundle.manifest["pages"])
            assert not bait
    asyncio.run(run())


@pytest.mark.parametrize("ip", ["127.0.0.1", "169.254.169.254", "10.77.0.2", "93.184.216.21", "::1"])
def test_kernel_blocks_direct_socket_bypassing_application(ip):
    async def run():
        async with lab() as (_, _, bait, _):
            with pytest.raises((TimeoutError, OSError)):
                async with asyncio.timeout(0.15):
                    _, writer = await asyncio.open_connection(ip, 80)
                    writer.close()
            assert not bait
    asyncio.run(run())


@pytest.mark.parametrize("host,trust", [("factory.test", False), ("wrong.test", True)])
def test_tls_untrusted_or_wrong_hostname_has_no_http(host, trust):
    async def run():
        async with lab() as (requests, _, _, _):
            a = lab_access(host=host)
            with pytest.raises(CollectionError, match="TLS_FAILED"):
                await fetcher(trust).fetch(a.start_url, "GET", Budget(Limits(), a))
            assert not requests
    asyncio.run(run())


@pytest.mark.parametrize("location", ["http://127.0.0.1/", "http://169.254.169.254/",
    "https://other.test/", "http://factory.test/", "/a/%252e%252e/private"])
def test_real_redirect_denied_before_second_connection(location):
    async def handler(target, writer):
        writer.write(b"HTTP/1.1 302 Found\r\nLocation: " + location.encode() + b"\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
    async def run():
        async with lab(handler) as (requests, _, bait, _):
            a = lab_access()
            with pytest.raises(CollectionError):
                await fetcher().fetch(a.start_url, "GET", Budget(Limits(interval_seconds=0.01), a))
            assert len(requests) == 1 and not bait
    asyncio.run(run())


def test_real_dns_rebinding_on_redirect_is_blocked():
    async def handler(target, writer):
        writer.write(b"HTTP/1.1 302 Found\r\nLocation: /next\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
    def answer(kind, count):
        return (["93.184.216.20"] if count == 1 else ["127.0.0.1"]) if kind == dns.rdatatype.A else []
    async def run():
        async with lab(handler, answer) as (requests, _, bait, _):
            a = lab_access()
            with pytest.raises(CollectionError, match="SSRF_BLOCKED"):
                await fetcher().fetch(a.start_url, "GET", Budget(Limits(interval_seconds=0.01), a))
            assert len(requests) == 1 and not bait
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["chunked", "no-length", "huge-length", "slow-headers", "slow-chunk"])
def test_real_unbounded_response_stops(mode):
    async def handler(target, writer):
        if mode == "huge-length":
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 99999999\r\n\r\n")
        elif mode == "slow-headers":
            for _ in range(100):
                writer.write(b"H")
                await writer.drain()
                await asyncio.sleep(0.03)
        else:
            writer.write(b"HTTP/1.1 200 OK\r\n" +
                (b"Transfer-Encoding: chunked\r\n" if mode != "no-length" else b"") + b"\r\n")
            for _ in range(100):
                writer.write(b"1\r\nx\r\n" if mode == "slow-chunk" else
                             b"40\r\n" + b"x" * 64 + b"\r\n" if mode == "chunked" else b"x" * 64)
                await writer.drain()
                if mode == "slow-chunk":
                    await asyncio.sleep(0.03)
        await writer.drain()
    async def run():
        async with lab(handler):
            a = lab_access()
            start = time.monotonic()
            with pytest.raises(CollectionError, match="LIMIT_EXCEEDED|TIMEOUT"):
                await fetcher().fetch(a.start_url, "GET", Budget(Limits(max_bytes=128,
                    request_seconds=0.2, task_seconds=0.3), a))
            assert time.monotonic() - start < 1.0
    asyncio.run(run())


@pytest.mark.parametrize("values,kind", [(["93.184.216.20", "10.77.0.2"], "A"),
    (["::1"], "AAAA"), (["::ffff:93.184.216.20"], "AAAA")])
def test_real_dns_mixed_or_ipv6_denial_has_zero_http(values, kind):
    def answer(qtype, count):
        if qtype == dns.rdatatype.from_text(kind):
            return values
        return ["93.184.216.20"] if qtype == dns.rdatatype.A else []
    async def run():
        async with lab(answer=answer) as (requests, _, bait, _):
            a = lab_access()
            with pytest.raises(CollectionError, match="SSRF_BLOCKED"):
                await fetcher().fetch(a.start_url, "GET", Budget(Limits(), a))
            assert not requests and not bait
    asyncio.run(run())


def test_real_cancel_during_stream_closes_socket():
    async def handler(target, writer):
        writer.write(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
        await writer.drain()
        await asyncio.sleep(10)
    async def run():
        async with lab(handler):
            a = lab_access()
            budget = Budget(Limits(), a)
            async def cancel():
                await asyncio.sleep(0.08)
                budget.cancel()
            task = asyncio.create_task(cancel())
            start = time.monotonic()
            with pytest.raises(CollectionError, match="CANCELLED"):
                await fetcher().fetch(a.start_url, "GET", budget)
            await task
            assert time.monotonic() - start < 0.5
    asyncio.run(run())


def test_real_head_has_no_body_and_no_hidden_resolution():
    async def handler(target, writer):
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n")
        await writer.drain()
    async def run():
        async with lab(handler) as (requests, _, _, dns_server):
            a = lab_access()
            response, _ = await fetcher().fetch(a.start_url, "HEAD", Budget(Limits(), a))
            assert response.body == b"" and response.peer_ip == "93.184.216.20"
            assert requests[0].startswith(b"HEAD / HTTP/1.1")
            assert len(dns_server.queries) == 2
    asyncio.run(run())
