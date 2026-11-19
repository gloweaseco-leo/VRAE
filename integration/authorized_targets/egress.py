"""Actual bounded transport for signed exact targets; no self-asserted live flag."""

from datetime import datetime
from integration.l2_launch.security.adapter import (
    FencedAccess,
    RecheckingResolver,
    TaskPins,
    OfflinePermit,
    fingerprint,
)
from integration.authorized_targets.source_authority import (
    authorization,
    deployment,
    root_document,
    DEPLOYMENT,
    AuthorityDenied,
)
from vrae.collection.errors import CollectionError
from vrae.collection.policy import SourceAccess
from vrae.collection.resolver import public_addresses
from integration.authorized_targets.dns_transport import DNSResolver
from vrae.collection.http_transport import PinnedTransport
from vrae.collection.fetcher import SafeFetcher


class ScopedResolver:
    def __init__(self, nameservers, allowed, *, tcp=False):
        self.resolver = DNSResolver(nameservers,tcp=tcp)
        self.allowed = set(public_addresses(allowed))

    async def resolve(self, host):
        answer = await self.resolver.resolve(host)
        if not set(answer) <= self.allowed:
            raise CollectionError("SSRF_BLOCKED")
        return answer


class CurrentAccess(FencedAccess):
    def __init__(self, original, held, permit, current, plan):
        self.current, self.plan = current, plan
        self.envelope = None
        super().__init__(original, held=held, permit=permit)

    def check(self, url):
        current = self.current()
        envelope = current["source_authorization"]
        authorization(envelope, self.plan, plan_sha256=current["plan_sha256"])
        if self.envelope is not None and self.envelope != envelope:
            raise AuthorityDenied()
        self.envelope = envelope
        return super().check(url)


class ConnectionFence:
    def __init__(self, resolver, transport, access, permit):
        self.resolver, self.transport, self.access, self.permit = (
            resolver,
            transport,
            access,
            permit,
        )

    async def exchange(self, url, method, ip, budget, max_bytes):
        if method not in ("GET", "HEAD"):
            raise CollectionError("METHOD_NOT_ALLOWED")
        budget.check()
        self.access.check(url)
        deployment(root_document(DEPLOYMENT), self.access.envelope, self.access.plan)
        if budget.run_id != self.access.held.run_id:
            raise AuthorityDenied()
        await self.resolver.before_connect(str(self.access.host), ip)
        budget.check()
        self.access.check(url)
        return await self.transport.exchange(url, method, ip, budget, max_bytes)


def components(audit, policy_provider, plan, run_id, workload, current):
    if current is None or workload.get("kind") != "AUTHORIZED_EGRESS_V2":
        raise AuthorityDenied()
    loaded = current()
    grant = authorization(loaded["source_authorization"], plan, plan_sha256=loaded["plan_sha256"])
    deploy = deployment(root_document(DEPLOYMENT), loaded["source_authorization"], plan)
    policy = policy_provider()
    source = SourceAccess(audit, policy_provider, terms_reference=plan["terms_reference"])
    held = TaskPins(
        audit["tenant_id"],
        audit["request_id"],
        run_id,
        policy["policy_id"],
        policy["policy_version"],
        fingerprint(policy),
    )
    permit = OfflinePermit(
        plan["origin"],
        tuple(plan["exact_paths"]),
        datetime.fromisoformat(grant["not_before"]),
        min(
            datetime.fromisoformat(grant["expires_at"]),
            datetime.fromisoformat(workload["deadline"]),
        ),
        plan["retain_raw_html"],
    )
    access = CurrentAccess(source, held, permit, current, plan)
    resolver = RecheckingResolver(ScopedResolver(deploy["nameservers"], grant["destination_ips"],tcp=deploy.get("dns_transport","UDP")=="TCP"))
    transport = PinnedTransport(cafile=deploy["cafile"])
    return access, SafeFetcher(resolver, ConnectionFence(resolver, transport, access, deploy))
