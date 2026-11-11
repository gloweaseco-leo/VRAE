"""Internal per-hop transport primitive. Collector adds mandatory robots and evidence policy."""
from typing import Protocol
import ipaddress
from jsonschema import ValidationError

from .errors import CollectionError
from .http_transport import FetchResponse
from .limits import Budget
from .redirects import REDIRECT_STATUSES, redirect_target
from .resolver import public_addresses
from .contracts import validate_document


class Resolver(Protocol):
    async def resolve(self, host: str) -> tuple[str, ...]: ...


class Transport(Protocol):
    async def exchange(self, url: str, method: str, ip: str, budget: Budget,
                       max_bytes: int) -> FetchResponse: ...


class SafeFetcher:
    def __init__(self, resolver: Resolver, transport: Transport):
        self.resolver, self.transport = resolver, transport

    async def fetch(self, url: str, method: str, budget: Budget, *,
                    max_bytes: int | None = None, allow_url=None) -> tuple[FetchResponse, list[dict]]:
        if method not in ("GET", "HEAD"):
            raise CollectionError("METHOD_NOT_ALLOWED")
        url = budget.access.check(url)
        validate_document("SafeFetchRequest", {"schema_version": "1.0",
            "tenant_id": budget.access.audit["tenant_id"], "run_id": budget.run_id,
            "request_id": budget.access.audit["request_id"], "url": url, "method": method,
            "policy_id": budget.access.audit["source_policy_ref"],
            "policy_version": budget.access.audit["source_policy_version"]})
        trace: list[dict] = []
        visited: set[str] = set()
        current = url
        try:
            for hop in range(budget.limits.max_redirects + 1):
                current = budget.access.check(current)
                if current in visited:
                    raise CollectionError("REDIRECT_BLOCKED")
                visited.add(current)
                if allow_url is not None:
                    allow_url(current)
                await budget.before_request()
                async def exchange():
                    addresses = public_addresses(list(await self.resolver.resolve(
                        str(budget.access.host))))
                    budget.check()
                    budget.access.check(current)
                    # No retries/failover in RA-1A. Every attempted request consumes budget.
                    response = await self.transport.exchange(current, method, addresses[0], budget,
                        min(max_bytes or budget.limits.max_bytes, budget.limits.max_bytes))
                    # An injected adapter is not a trust boundary. Validate its claimed
                    # destination before emitting even one successful hop.
                    try:
                        if response.url != current or not isinstance(response.peer_ip, str):
                            raise ValueError("Transport destination mismatch")
                        peer = public_addresses([response.peer_ip])[0]
                        if ipaddress.ip_address(peer) != ipaddress.ip_address(addresses[0]):
                            raise ValueError("Transport peer mismatch")
                    except (AttributeError, TypeError, ValueError, CollectionError) as exc:
                        raise CollectionError("HTTP_PROTOCOL_ERROR") from exc
                    return response
                response = await budget.run(exchange(), budget.limits.request_seconds)
                try:
                    validate_document("FetchResponse", response.document())
                except (ValidationError, ValueError) as exc:
                    raise CollectionError("HTTP_PROTOCOL_ERROR") from exc
                trace.append({"url": current, "status": response.status,
                              "peer_ip": response.peer_ip, "location": None})
                if response.status not in REDIRECT_STATUSES:
                    validate_document("RedirectTrace", {"schema_version": "1.0", "hops": trace})
                    return response, trace
                if hop == budget.limits.max_redirects:
                    raise CollectionError("REDIRECT_LIMIT")
                current = redirect_target(current, response.headers.get("location", ""), budget.access)
                trace[-1]["location"] = current
            raise CollectionError("REDIRECT_LIMIT")
        except CollectionError as exc:
            exc.trace = trace
            raise
