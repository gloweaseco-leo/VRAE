"""Deny cases first. No test in this module opens a socket."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from vrae.collection.errors import CollectionError
from vrae.collection.policy import SourceAccess, canonical_url
from vrae.collection.resolver import public_addresses
from vrae.collection.redirects import redirect_target
from vrae.collection.limits import Limits, Budget, HostLeases

CASES = json.loads((Path(__file__).parents[1] / "fixtures/contracts/valid.json").read_text())
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


def fixture(name):
    return deepcopy(next(c["data"] for c in CASES if c["schema"] == name))


def access():
    request, policy = fixture("AuditRequest"), fixture("SourcePolicy")
    return SourceAccess(request, lambda: policy, terms_reference="terms-synthetic", now=lambda: NOW)


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.0.1", "169.254.169.254",
    "0.0.0.0", "100.64.0.1", "224.0.0.1", "240.0.0.1", "192.0.2.1",
    "::", "::1", "fe80::1", "fc00::1", "ff02::1", "2001:db8::1",
    "::ffff:8.8.8.8", "fe80::1%eth0", "64:ff9b::808:808", "2002:0808:0808::1",
    "192.0.0.9", "192.88.99.1", "2001:30::1",
])
def test_nonpublic_or_transition_ip_is_refused(ip):
    with pytest.raises(CollectionError):
        public_addresses([ip])


def test_mixed_dns_fails_whole_answer():
    with pytest.raises(CollectionError):
        public_addresses(["93.184.216.20", "10.0.0.1"])


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://127.0.0.1/", "http://169.254.169.254/",
    "https://user:secret@example.org/", "https://example.org:444/",
    "https://example.org/a/%252e%252e/private", "https://example.org/a/../private",
    "https://example.org/a//b", "https://example.org/a%2fb", "https://example.org/a%00b",
    "https://example.org/path?token=secret", "https://evil.example/", "https://example.org/./",
])
def test_unsafe_url_before_network(url):
    with pytest.raises(CollectionError):
        access().check(url)


@pytest.mark.parametrize("target", ["http://example.org/", "https://evil.example/",
    "http://127.0.0.1/", "//169.254.169.254/", "/products/%2e%2e/private"])
def test_redirect_cannot_escape(target):
    with pytest.raises(CollectionError):
        redirect_target("https://example.org/", target, access())


def test_revocation_reloaded():
    p = fixture("SourcePolicy")
    a = SourceAccess(fixture("AuditRequest"), lambda: p, terms_reference="terms-test", now=lambda: NOW)
    p["revoked_at"] = "2026-11-10T00:00:00Z"
    with pytest.raises(CollectionError, match="POLICY_REVOKED"):
        a.check("https://example.org/")


def test_budget_cancel_and_deadline():
    async def scenario():
        budget = Budget(Limits(task_seconds=0.05), access())
        with pytest.raises(CollectionError, match="TIMEOUT"):
            await budget.run(asyncio.sleep(5))
        budget = Budget(Limits(), access())
        budget.cancel()
        with pytest.raises(CollectionError, match="CANCELLED"):
            budget.check()
    asyncio.run(scenario())


def test_same_host_task_is_exclusive():
    with HostLeases.claim("example.org"):
        with pytest.raises(CollectionError, match="HOST_BUSY"):
            with HostLeases.claim("example.org"):
                pass


def test_canonical_url_has_single_identity():
    assert canonical_url("https://EXAMPLE.org:443/products#section") == "https://example.org/products"
