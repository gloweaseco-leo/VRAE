"""Adversarial adapter and resealed cross-object integrity regressions."""
import asyncio
from dataclasses import replace

import pytest

from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Budget, Limits
from vrae.collection.manifest import document_hash
from .test_pipeline import FixedDNS, SyntheticTransport, collect
from .test_security import access


@pytest.mark.parametrize("field,value", [
    ("url", "https://evil.test/"), ("url", "https://example.org/private"),
    ("url", "https://example.org:443/"), ("peer_ip", "93.184.216.21"),
    ("peer_ip", "127.0.0.1"), ("peer_ip", "169.254.169.254"),
    ("peer_ip", "::ffff:93.184.216.20"), ("peer_ip", "invalid"),
    ("peer_ip", ""), ("peer_ip", None),
])
def test_forged_transport_is_rejected_before_trace_or_evidence(field, value):
    class Forged(SyntheticTransport):
        async def exchange(self, url, method, ip, budget, max_bytes):
            response = await super().exchange(url, method, ip, budget, max_bytes)
            return replace(response, **{field: value})

    async def run():
        fetcher = SafeFetcher(FixedDNS(), Forged({}))
        with pytest.raises(CollectionError) as caught:
            await fetcher.fetch("https://example.org/", "GET", Budget(Limits(), access()))
        assert caught.value.trace == []
        bundle = await Collector(fetcher).capture("run-forged", access())
        assert all(p["snapshot"]["status"] != "FETCHED" and p["evidence"] is None
                   and not p["redirect_trace"] for p in bundle.manifest["pages"])
    asyncio.run(run())


def test_ipv6_transport_comparison_is_numeric():
    class Expanded(SyntheticTransport):
        async def exchange(self, url, method, ip, budget, max_bytes):
            return replace(await super().exchange(url, method, ip, budget, max_bytes),
                           peer_ip="2606:4700:4700:0000:0000:0000:0000:1111")
    async def run():
        response, trace = await SafeFetcher(FixedDNS([("2606:4700:4700::1111",)]),
            Expanded({})).fetch("https://example.org/", "GET", Budget(Limits(), access()))
        assert response.status == 200 and len(trace) == 1
    asyncio.run(run())


def test_missing_peer_attribute_is_structured_refusal():
    class MissingPeer(SyntheticTransport):
        async def exchange(self, url, method, ip, budget, max_bytes):
            class Incomplete:
                pass
            response = Incomplete()
            response.url = url
            return response
    async def run():
        with pytest.raises(CollectionError, match="HTTP_PROTOCOL_ERROR") as caught:
            await SafeFetcher(FixedDNS(), MissingPeer({})).fetch(
                "https://example.org/", "GET", Budget(Limits(), access()))
        assert caught.value.trace == []
    asyncio.run(run())


def test_forged_second_hop_keeps_only_previously_verified_hop():
    class ForgedSecond(SyntheticTransport):
        async def exchange(self, url, method, ip, budget, max_bytes):
            response = await super().exchange(url, method, ip, budget, max_bytes)
            return replace(response, peer_ip="93.184.216.21") if url.endswith("/next") else response
    async def run():
        transport = ForgedSecond({"https://example.org/": (302, {"location": "/next"}, b"")})
        with pytest.raises(CollectionError) as caught:
            await SafeFetcher(FixedDNS(), transport).fetch("https://example.org/", "GET",
                Budget(Limits(interval_seconds=0.01), access()))
        assert len(caught.value.trace) == 1
        assert caught.value.trace[0]["status"] == 302
    asyncio.run(run())


def test_default_no_raw_retention_does_not_mean_url_paths_are_anonymous():
    bundle, _ = collect({"https://example.org/": (200, {"content-type": "text/html"},
        b'<html><a href="/people/synthetic-alice">Person</a></html>')})
    assert not bundle.objects
    assert all(p["evidence"]["excerpt"] is None for p in bundle.manifest["pages"])
    assert any("synthetic-alice" in i["url"] for i in bundle.manifest["inventory"])


def test_shared_content_address_is_valid_for_distinct_page_evidence():
    bundle, _ = collect({"https://example.org/": (200, {"content-type": "text/html"},
        b'<html><a href="/about">About</a><a href="/contact">Contact</a></html>')},
        retain_raw_html=True)
    assert bundle.manifest["pages"][1]["snapshot"]["private_object_ref"] == \
        bundle.manifest["pages"][2]["snapshot"]["private_object_ref"]
    bundle.verify()


@pytest.mark.parametrize("change", [
    "coverage_added", "coverage_missing", "complement", "inventory_missing",
    "inventory_role", "inventory_origin", "inventory_duplicate", "snapshot_duplicate",
    "evidence_duplicate", "trace_start", "trace_link", "trace_status", "trace_terminal",
    "robots_start",
])
def test_resealed_manifest_cannot_hide_cross_object_contradictions(change):
    bundle, _ = collect({
        "https://example.org/": (302, {"location": "/home"}, b""),
        "https://example.org/home": (200, {"content-type": "text/html"},
                                      b'<html><a href="/about">About</a></html>'),
    })
    doc = bundle.manifest
    page = doc["pages"][0]
    if change == "coverage_added":
        doc["coverage"]["observed_roles"].append("PRODUCT")
    elif change == "coverage_missing":
        doc["coverage"]["observed_roles"] = []
    elif change == "complement":
        doc["coverage"]["unverified_roles"] = []
    elif change == "inventory_missing":
        doc["inventory"] = []
    elif change == "inventory_role":
        doc["inventory"][0]["role"] = "PRODUCT"
    elif change == "inventory_origin":
        doc["inventory"][1]["discovered_from"] = "https://example.org/never-fetched"
    elif change == "inventory_duplicate":
        doc["inventory"].append(doc["inventory"][0].copy())
    elif change == "snapshot_duplicate":
        doc["pages"][1]["snapshot"]["snapshot_id"] = page["snapshot"]["snapshot_id"]
    elif change == "evidence_duplicate":
        doc["pages"][1]["evidence"]["evidence_id"] = page["evidence"]["evidence_id"]
    elif change == "trace_start":
        page["redirect_trace"][0]["url"] = "https://example.org/wrong"
    elif change == "trace_link":
        page["redirect_trace"][0]["location"] = "https://example.org/wrong"
    elif change == "trace_status":
        page["redirect_trace"][0]["status"] = 200
    elif change == "trace_terminal":
        page["redirect_trace"][-1]["location"] = "https://example.org/wrong"
    else:
        doc["robots"]["trace"][0]["url"] = "https://example.org/wrong"
    doc["manifest_sha256"] = document_hash({k:v for k,v in doc.items() if k != "manifest_sha256"})
    with pytest.raises(CollectionError, match="EVIDENCE_INTEGRITY"):
        bundle.verify()
