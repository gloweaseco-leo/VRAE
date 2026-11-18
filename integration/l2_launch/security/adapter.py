"""Additive fences around the ORIGINAL Collector, not an L2 authorization bridge.

All pins below are trusted worker configuration, never request/HTML/model input.
There is intentionally no live-enabling parameter, credential or network factory.
"""
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.http_transport import FetchResponse, PinnedTransport
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess, canonical_url
from vrae.collection.resolver import DNSResolver, public_addresses

STATUS = 'R1A_OFFLINE_SECURITY_CANDIDATE_LIVE_GATE_PENDING'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class TaskPins:
    tenant_id: str
    request_id: str
    run_id: str
    policy_id: str
    policy_version: int
    policy_sha256: str


@dataclass(frozen=True)
class OfflinePermit:
    """Extra restriction, not legal permission or the pending C2 contract."""
    origin: str
    exact_paths: tuple[str, ...]
    not_before: datetime
    expires_at: datetime
    retain_raw_html: bool = False


class FencedAccess(SourceAccess):
    def __init__(self, original, *, held, permit):
        if type(original) is not SourceAccess or type(held) is not TaskPins or type(permit) is not OfflinePermit:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        self.held, self.permit = held, permit
        if (any(type(getattr(held, k)) is not str for k in ('tenant_id', 'request_id', 'run_id', 'policy_id', 'policy_sha256'))
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,127}', held.run_id)
                or not re.fullmatch(r'[0-9a-f]{64}', held.policy_sha256)
                or type(held.policy_version) is not int or held.policy_version < 1 or type(permit.exact_paths) is not tuple
                or not 1 <= len(permit.exact_paths) <= 16 or len(set(permit.exact_paths)) != len(permit.exact_paths)
                or type(permit.retain_raw_html) is not bool
                or any(type(t) is not datetime or t.utcoffset() is None for t in (permit.not_before, permit.expires_at))
                or permit.not_before >= permit.expires_at):
            raise CollectionError('SOURCE_NOT_ALLOWED')
        # HTTPS-only candidate. Existing HTTP support is not broadened or removed.
        origin = canonical_url(permit.origin)
        if origin != permit.origin + '/' or urlsplit(origin).scheme != 'https':
            raise CollectionError('SOURCE_NOT_ALLOWED')
        for path in permit.exact_paths:
            if type(path) is not str or not path.startswith('/') or canonical_url(permit.origin + path) != permit.origin + path:
                raise CollectionError('SOURCE_NOT_ALLOWED')
        if '/robots.txt' not in permit.exact_paths:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        super().__init__(original.audit, original.provider, terms_reference=original.terms_reference, now=original.now)

    def check(self, url):
        result = super().check(url)
        held, permit = self.held, self.permit
        if (self.audit['tenant_id'] != held.tenant_id or self.audit['request_id'] != held.request_id
                or self.audit['source_policy_ref'] != held.policy_id
                or self.audit['source_policy_version'] != held.policy_version
                or fingerprint(self.provider()) != held.policy_sha256
                or not permit.not_before <= self.now() < permit.expires_at):
            raise CollectionError('SOURCE_NOT_ALLOWED')
        parts = urlsplit(result)
        if parts.scheme + '://' + parts.netloc != permit.origin or parts.path not in permit.exact_paths:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        return result


class RecheckingResolver:
    def __init__(self, resolver):
        self.resolver = resolver
        self.last = None
        self.checks = []

    async def resolve(self, host):
        addresses = public_addresses(list(await self.resolver.resolve(host)))
        self.last = (host, addresses)
        self.checks.append({'stage': 'HOP_DNS', 'host': host, 'addresses': addresses})
        return addresses

    async def before_connect(self, host, ip):
        if self.last is None or self.last[0] != host or self.last[1][0] != ip:
            raise CollectionError('SSRF_BLOCKED')
        current = public_addresses(list(await self.resolver.resolve(host)))
        # Conservative: even a public rotation of the complete A+AAAA set denies.
        # PinnedTransport then connects to the numeric IP, without hidden DNS.
        if set(current) != set(self.last[1]):
            raise CollectionError('SSRF_BLOCKED')
        self.checks.append({'stage': 'PRECONNECT_DNS', 'host': host, 'addresses': current})


class ConnectionFence:
    def __init__(self, resolver, transport):
        if type(transport) is not RecordedTransport:
            if type(transport) is not PinnedTransport:
                raise CollectionError('SOURCE_NOT_ALLOWED')
            require_isolation()
        self.resolver, self.transport = resolver, transport

    async def exchange(self, url, method, ip, budget, max_bytes):
        if method not in ('GET', 'HEAD'):
            raise CollectionError('METHOD_NOT_ALLOWED')
        budget.check()
        budget.access.check(url)
        if budget.run_id != budget.access.held.run_id:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        await self.resolver.before_connect(str(budget.access.host), ip)
        budget.check()
        budget.access.check(url)
        return await self.transport.exchange(url, method, ip, budget, max_bytes)


class RecordedResolver:
    """Test data only: no DNS library/socket fallback."""
    def __init__(self, answers=(('93.184.216.20',),)):
        self.answers, self.calls = tuple(answers), 0

    async def resolve(self, host):
        if not self.answers:
            raise CollectionError('DNS_FAILED')
        answer = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        return answer


class RecordedTransport:
    """Exact saved responses, never a network miss fallback."""
    def __init__(self, routes, *, peer='93.184.216.20', error=None):
        self.routes, self.peer, self.error = dict(routes), peer, error
        self.calls = []

    async def exchange(self, url, method, ip, budget, max_bytes):
        self.calls.append((url, method, ip))
        if self.error:
            raise CollectionError(self.error)
        if url not in self.routes:
            raise CollectionError('NETWORK_ERROR')
        status, headers, body = self.routes[url]
        if len(body) > max_bytes:
            raise CollectionError('LIMIT_EXCEEDED')
        budget.consume(len(body))
        return FetchResponse(url, status, headers, b'' if method == 'HEAD' else body, self.peer)


class OfflineWorker:
    def __init__(self, access, *, held, permit, resolver, transport, limits=None):
        if type(resolver) is not RecordedResolver or type(transport) is not RecordedTransport:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        self.access = FencedAccess(access, held=held, permit=permit)
        self.resolver = RecheckingResolver(resolver)
        self.fetcher = SafeFetcher(self.resolver, ConnectionFence(self.resolver, transport))
        self.limits = limits or Limits()

    async def capture(self, run_id):
        if run_id != self.access.held.run_id:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        self.access.check(self.access.start_url)
        return await Collector(self.fetcher).capture(run_id, self.access, limits=self.limits,
            retain_raw_html=self.access.permit.retain_raw_html)


def require_isolation():
    if os.name != 'posix' or os.environ.get('R1A_ISOLATED_LAB') != '1':
        raise CollectionError('SOURCE_NOT_ALLOWED')
    state = Path('/proc/self/status').read_text()
    if (set(os.listdir('/sys/class/net')) != {'lo'} or getattr(os, 'geteuid', lambda: -1)() != 65532
            or 'CapEff:\t0000000000000000' not in state or 'NoNewPrivs:\t1' not in state):
        raise CollectionError('SOURCE_NOT_ALLOWED')


def isolated_fetcher(access, *, held, permit, nameservers, cafile):
    """Lab only; parent also inspects Docker NetworkMode=none. No live capability."""
    require_isolation()
    if nameservers != ['93.184.216.53'] or cafile != '/tmp/lab/cert.pem':
        raise CollectionError('SOURCE_NOT_ALLOWED')
    fenced = FencedAccess(access, held=held, permit=permit)
    resolver = RecheckingResolver(DNSResolver(nameservers))
    return fenced, SafeFetcher(resolver, ConnectionFence(resolver, PinnedTransport(cafile=cafile)))


def capture_live(*args, **kwargs):
    raise PermissionError('LIVE_CAPTURE_DISABLED')
