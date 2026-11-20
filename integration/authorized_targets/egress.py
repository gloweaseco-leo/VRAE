"""Actual bounded transport for signed exact targets; no self-asserted live flag."""

from datetime import datetime
from contextlib import contextmanager
from copy import deepcopy
from urllib.parse import urlsplit
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
    @contextmanager
    def inventory_scope(self):
        if self.plan.get('path_scope') != 'PUBLIC_SAME_ORIGIN':
            yield self
            return
        # No network or await in this scope. Recheck current PG/signatures on
        # both sides, rather than per href; every actual fetch stays fenced.
        self.check(self.start_url)
        policy = deepcopy(self.provider())
        local = SourceAccess(self.audit, lambda: policy,
            terms_reference=self.terms_reference, now=self.now)
        owner = self

        class DiscoveryAccess:
            def check(self, url):
                return owner.public_path(local.check(url))

        try:
            yield DiscoveryAccess()
        finally:
            self.check(self.start_url)

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
        if self.plan.get("path_scope") == "PUBLIC_SAME_ORIGIN":
            result = SourceAccess.check(self, url)
            held, permit = self.held, self.permit
            if (fingerprint(self.audit) != self._audit_fingerprint
                    or self.audit['tenant_id'] != held.tenant_id
                    or self.audit['request_id'] != held.request_id
                    or self.audit['source_policy_ref'] != held.policy_id
                    or self.audit['source_policy_version'] != held.policy_version
                    or fingerprint(self.provider()) != held.policy_sha256
                    or not permit.not_before <= self.now() < permit.expires_at):
                raise AuthorityDenied()
            return self.public_path(result)
        return super().check(url)

    def public_path(self, result):
        parts = urlsplit(result)
        if parts.scheme + '://' + parts.netloc != self.permit.origin:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        segments = {p.lower().split('.')[0] for p in parts.path.split('/')}
        if segments & {'admin', 'login', 'logout', 'signin', 'signup', 'account',
                       'cart', 'checkout', 'wp-admin', 'wp-login', 'api', 'delete',
                       'remove', 'unsubscribe', 'subscribe', 'submit', 'cgi-bin'}:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        return result


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
