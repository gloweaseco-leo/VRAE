"""Bounded explicit A+AAAA lookup. The full answer is checked before any connection."""
import asyncio
import ipaddress

import dns.asyncresolver
import dns.exception
import dns.resolver

from .errors import CollectionError

_TRANSITION = tuple(ipaddress.ip_network(n) for n in (
    "64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "2001::/23"))
_SPECIAL_V4 = tuple(ipaddress.ip_network(n) for n in ("192.0.0.0/24", "192.88.99.0/24"))


def public_addresses(values: list[str]) -> tuple[str, ...]:
    if not values or len(values) > 32:
        raise CollectionError("DNS_FAILED")
    result = []
    for value in values:
        try:
            if "%" in value:
                raise ValueError("zone ID")
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise CollectionError("SSRF_BLOCKED") from exc
        if (not address.is_global or address.is_multicast or address.is_reserved
                or address.is_unspecified or address.is_loopback or address.is_link_local
                or (isinstance(address, ipaddress.IPv4Address) and any(address in n for n in _SPECIAL_V4))
                or (isinstance(address, ipaddress.IPv6Address) and (
                    address.ipv4_mapped is not None or any(address in n for n in _TRANSITION)))):
            raise CollectionError("SSRF_BLOCKED")
        if str(address) not in result:
            result.append(str(address))
    return tuple(result)


class DNSResolver:
    def __init__(self, nameservers: list[str]):
        if not nameservers:
            raise ValueError("Explicit infrastructure resolver required")
        for server in nameservers:
            ipaddress.ip_address(server)
        self.resolver = dns.asyncresolver.Resolver(configure=False)
        self.resolver.nameservers = nameservers
        self.resolver.cache = None

    async def resolve(self, host: str) -> tuple[str, ...]:
        values: list[str] = []
        try:
            async with asyncio.timeout(5):
                for kind in ("A", "AAAA"):
                    answer = await self.resolver.resolve(host + ".", kind, search=False,
                                                         lifetime=2.5, raise_on_no_answer=False)
                    values.extend(str(record) for record in answer)
        except (dns.exception.DNSException, TimeoutError, OSError) as exc:
            raise CollectionError("DNS_FAILED") from exc
        return public_addresses(values)
