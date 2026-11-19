"""Signed service TCP selection around the unchanged original DNS validation.

Only wire transport is specialized. Original complete A+AAAA/public-address
validation, timeout, no cache and preconnect rechecking remain authoritative.
"""
import dns.asyncresolver
from vrae.collection.resolver import DNSResolver as OriginalDNSResolver


class _TCPQueries(dns.asyncresolver.Resolver):
    async def resolve(self, *args, **kwargs):
        if "tcp" in kwargs:
            raise ValueError("SERVICE_TRANSPORT_OVERRIDE_REFUSED")
        return await super().resolve(*args, tcp=True, **kwargs)


class DNSResolver(OriginalDNSResolver):
    def __init__(self, nameservers: list[str], *, tcp: bool = False):
        if type(tcp) is not bool:
            raise ValueError("Explicit DNS transport required")
        super().__init__(nameservers)
        if tcp:
            resolver = _TCPQueries(configure=False)
            resolver.nameservers = nameservers
            resolver.cache = None
            self.resolver = resolver
