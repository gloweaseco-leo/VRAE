"""Synthetic transport contract tests; real socket enforcement is in test_isolated.py."""
import asyncio
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.http_transport import FetchResponse
from vrae.collection.limits import Budget, Limits
from vrae.collection.manifest import document_hash
from vrae.collection.policy import SourceAccess
from .test_security import access, fixture, NOW


class FixedDNS:
    def __init__(self, answers=None):
        self.calls = 0
        self.answers = answers or [("93.184.216.20",)]

    async def resolve(self, host):
        result = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        return result


class SyntheticTransport:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    async def exchange(self, url, method, ip, budget, max_bytes):
        self.calls.append((url, method, ip))
        status, headers, body = self.routes.get(url, (200, {"content-type": "text/html"}, b"<html>Page</html>"))
        if len(body) > max_bytes:
            raise CollectionError("LIMIT_EXCEEDED")
        budget.consume(len(body))
        return FetchResponse(url, status, headers, body, ip)


def collect(routes=None, **kwargs):
    transport = SyntheticTransport(routes or {})
    transport.routes.setdefault("https://example.org/robots.txt",
        (200, {"content-type": "text/plain"}, b"User-agent: *\nDisallow:\n"))
    collector = Collector(SafeFetcher(FixedDNS(), transport))
    bundle = asyncio.run(collector.capture("run-synthetic", access(),
        limits=Limits(interval_seconds=0.01), **kwargs))
    return bundle, transport


@pytest.mark.parametrize("status,headers,body,code", [
    (403, {"content-type": "text/html"}, b"blocked", "ACCESS_BLOCKED"),
    (200, {"content-type": "text/html"}, b"<html>Verify you are human</html>", "ACCESS_BLOCKED"),
    (200, {"content-type": "application/pdf"}, b"%PDF", "CONTENT_TYPE_INVALID"),
    (200, {"content-type": "text/html"}, b"", "EVIDENCE_INSUFFICIENT"),
    (200, {"content-type": "text/html"}, b"\xff", "CONTENT_ENCODING_INVALID"),
])
def test_restricted_or_unknown_not_fetched(status, headers, body, code):
    bundle, _ = collect({"https://example.org/": (status, headers, body)})
    page = bundle.manifest["pages"][0]
    assert page["error"]["code"] == code
    assert page["snapshot"]["status"] != "FETCHED"
    assert page["evidence"] is None
    assert not bundle.objects


@pytest.mark.parametrize("robots", [b"User-agent: *\nDisallow: /\n",
    b"User-agent: *\nDisallow: /*\nAllow: /\n"])
def test_robots_denial_stops_before_page(robots):
    bundle, transport = collect({"https://example.org/robots.txt":
        (200, {"content-type": "text/plain"}, robots)})
    assert len(transport.calls) == 1
    assert bundle.manifest["pages"][0]["error"]["code"] == "ROBOTS_DISALLOWED"


def test_redirect_rebinding_checks_entire_new_answer():
    async def run():
        transport = SyntheticTransport({"https://example.org/":
            (302, {"location": "/next"}, b"")})
        fetcher = SafeFetcher(FixedDNS([("93.184.216.20",), ("127.0.0.1",)]), transport)
        with pytest.raises(CollectionError, match="SSRF_BLOCKED"):
            await fetcher.fetch("https://example.org/", "GET", Budget(Limits(interval_seconds=0.01), access()))
        assert len(transport.calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "CONNECT", "OPTIONS", "get"])
def test_non_readonly_method_has_zero_requests(method):
    async def run():
        transport = SyntheticTransport({})
        with pytest.raises(CollectionError, match="METHOD_NOT_ALLOWED"):
            await SafeFetcher(FixedDNS(), transport).fetch("https://example.org/", method, Budget(Limits(), access()))
        assert not transport.calls
    asyncio.run(run())


def test_discovery_role_coverage_beats_link_order_and_retention_is_opt_in():
    body = (b'<html><a href="/news/1">News</a><a href="/news/2">News</a>'
            b'<a href="/contact">person@example.org</a><a href="/about">About</a>'
            b'<a href="/applications">Apps</a><a href="/products">Products</a>'
            b'<a href="/category/valves">Category</a><a href="/product/valve">Part</a>'
            b'<a href="/">Loop</a><a href="http://127.0.0.1">Bad</a></html>')
    bundle, transport = collect({"https://example.org/": (200, {"content-type": "text/html"}, body)})
    assert len(bundle.manifest["pages"]) == 8
    assert bundle.manifest["pages"][1]["role"] == "CATALOG"
    assert set(bundle.manifest["coverage"]["observed_roles"]) >= {
        "HOME", "CATALOG", "CATEGORY", "PRODUCT", "APPLICATION", "ABOUT", "CONTACT"}
    assert len({c[0] for c in transport.calls}) == len(transport.calls)
    assert not bundle.objects
    assert "person@example.org" not in str(bundle.manifest)
    assert bundle.manifest["pages"][0]["snapshot"]["sha256"] == hashlib.sha256(body).hexdigest()
    bundle.verify()


def test_retained_content_and_manifest_tamper_are_detected():
    bundle, _ = collect(retain_raw_html=True)
    key = next(iter(bundle.objects))
    bundle.objects[key] = b"modified"
    with pytest.raises(CollectionError, match="EVIDENCE_INTEGRITY"):
        bundle.verify()
    bundle, _ = collect()
    bundle.manifest["pages"][0]["snapshot"]["run_id"] = "other-run"
    # Even recomputing the container digest cannot hide inconsistent tenant/run links.
    bundle.manifest["manifest_sha256"] = document_hash({k: v for k, v in bundle.manifest.items()
                                                       if k != "manifest_sha256"})
    with pytest.raises(CollectionError):
        bundle.verify()


def test_revocation_during_pending_io_stops_promptly():
    async def run():
        policy = fixture("SourcePolicy")
        a = SourceAccess(fixture("AuditRequest"), lambda: policy, terms_reference="terms-test", now=lambda: NOW)
        budget = Budget(Limits(), a)
        async def revoke():
            await asyncio.sleep(0.02)
            policy["revoked_at"] = NOW.isoformat()
            await asyncio.sleep(10)
        with pytest.raises(CollectionError, match="POLICY_REVOKED"):
            await budget.run(revoke())
    asyncio.run(run())


@pytest.mark.parametrize("field,value", [("max_pages", 9), ("max_bytes", 1_500_001),
    ("max_redirects", 6), ("task_seconds", 121), ("max_pages", True), ("request_seconds", float("nan"))])
def test_limits_cannot_expand_hard_caps(field, value):
    with pytest.raises(ValueError):
        replace(Limits(), **{field: value})


@pytest.mark.parametrize("name", ["factory", "spa", "blocked", "cms", "catalog"])
def test_fictional_site_fixtures_never_emit_diagnostic_success(name):
    body = (Path(__file__).parents[1] / "fixtures/sites" / (name + ".html")).read_bytes()
    bundle, _ = collect({"https://example.org/": (200, {"content-type":"text/html"}, body)})
    bundle.verify()
    assert "findings" not in bundle.manifest
    assert "AUDIT_SUCCESS" not in str(bundle.manifest)
    if name == "blocked":
        assert bundle.manifest["pages"][0]["snapshot"]["status"] == "ACCESS_BLOCKED"
    if name == "spa":
        assert len(bundle.manifest["pages"]) == 1
        assert "PRODUCT" in bundle.manifest["coverage"]["unverified_roles"]


def test_encoded_robots_disallow_cannot_be_ignored():
    bundle, transport = collect({"https://example.org/robots.txt":
        (200, {"content-type":"text/plain"}, b"User-agent: *\nDisallow: /%70rivate\n")})
    assert len(transport.calls) == 1
    assert bundle.manifest["pages"][0]["snapshot"]["status"] != "FETCHED"


def test_budget_rate_and_max_requests_are_enforced():
    async def run():
        import time
        budget = Budget(Limits(max_requests=2, interval_seconds=0.04), access())
        start = time.monotonic()
        await budget.before_request()
        await budget.before_request()
        assert time.monotonic() - start >= 0.035
        with pytest.raises(CollectionError, match="LIMIT_EXCEEDED"):
            await budget.before_request()
    asyncio.run(run())


def test_l0_page_cap_remains_five_even_when_eight_requested():
    async def run():
        request, policy = fixture("AuditRequest"), fixture("SourcePolicy")
        request["audit_mode"] = "L0"
        a = SourceAccess(request, lambda: policy, terms_reference="terms-test", now=lambda: NOW)
        budget = Budget(Limits(), a)
        for _ in range(5):
            budget.page()
        with pytest.raises(CollectionError):
            budget.page()
    asyncio.run(run())


def test_scope_does_not_implicitly_expand_for_robots():
    async def run():
        request, policy = fixture("AuditRequest"), fixture("SourcePolicy")
        request["site_url"] = "https://example.org/products"
        policy["scope_paths"] = ["/products"]
        a = SourceAccess(request, lambda: policy, terms_reference="terms-test", now=lambda: NOW)
        transport = SyntheticTransport({})
        bundle = await Collector(SafeFetcher(FixedDNS(), transport)).capture("run-test", a)
        assert not transport.calls
        assert bundle.manifest["errors"][0]["code"] == "SOURCE_NOT_ALLOWED"
    asyncio.run(run())


def test_invalid_http_status_is_structured_refusal():
    async def run():
        transport = SyntheticTransport({"https://example.org/": (999, {}, b"")})
        with pytest.raises(CollectionError, match="HTTP_PROTOCOL_ERROR"):
            await SafeFetcher(FixedDNS(), transport).fetch("https://example.org/", "GET", Budget(Limits(), access()))
    asyncio.run(run())


@pytest.mark.parametrize("loop", [True, False])
def test_redirect_loop_and_hop_cap_stop_requests(loop):
    async def run():
        routes = {"https://example.org/": (302, {"location": "/" if loop else "/hop1"}, b"")}
        for i in range(1, 8):
            routes[f"https://example.org/hop{i}"] = (302, {"location": f"/hop{i+1}"}, b"")
        transport = SyntheticTransport(routes)
        with pytest.raises(CollectionError, match="REDIRECT_BLOCKED|REDIRECT_LIMIT"):
            await SafeFetcher(FixedDNS(), transport).fetch("https://example.org/", "GET",
                Budget(Limits(interval_seconds=0.01), access()))
        assert len(transport.calls) == (1 if loop else 6)
    asyncio.run(run())


def test_total_bytes_include_unsuccessful_responses():
    budget = Budget(Limits(max_total_bytes=10), access())
    budget.consume(10)
    with pytest.raises(CollectionError, match="LIMIT_EXCEEDED"):
        budget.consume(1)


def test_redirect_path_scope_is_checked():
    from vrae.collection.redirects import redirect_target
    request, policy = fixture("AuditRequest"), fixture("SourcePolicy")
    request["site_url"] = "https://example.org/products"
    policy["scope_paths"] = ["/products", "/robots.txt"]
    a = SourceAccess(request, lambda: policy, terms_reference="terms-test", now=lambda: NOW)
    with pytest.raises(CollectionError, match="SOURCE_NOT_ALLOWED"):
        redirect_target(request["site_url"], "/private", a)


@pytest.mark.parametrize("change", ["policy", "missing_evidence", "http_status", "retained_flag"])
def test_manifest_resealed_inconsistent_metadata_is_refused(change):
    bundle, _ = collect()
    page = bundle.manifest["pages"][0]
    if change == "policy":
        page["snapshot"]["policy_version"] += 1
    elif change == "missing_evidence":
        page["evidence"] = None
    elif change == "http_status":
        page["http_status"] = 403
    else:
        page["raw_retained"] = True
    bundle.manifest["manifest_sha256"] = document_hash({k:v for k,v in bundle.manifest.items()
                                                       if k != "manifest_sha256"})
    with pytest.raises(CollectionError, match="EVIDENCE_INTEGRITY"):
        bundle.verify()


def test_extraction_is_bounded_and_reports_uninspected_tail():
    body = b"<html><body>" + b"x" * 140_000 + b'<a href="/contact">Contact</a></body></html>'
    bundle, _ = collect({"https://example.org/": (200, {"content-type":"text/html"}, body)})
    assert bundle.manifest["coverage"]["inventory_truncated"] is True
    assert "CONTACT" in bundle.manifest["coverage"]["unverified_roles"]
    assert bundle.manifest["pages"][0]["snapshot"]["sha256"] == hashlib.sha256(body).hexdigest()
