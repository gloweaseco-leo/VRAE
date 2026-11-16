"""Ordinary multipage HTML through the unchanged Collector; no sockets/DNS.

URLs are identifiers in an explicitly synthetic local archive. The transport
has no network fallback, cookies, POST, browser or production mode.
"""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit

from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.http_transport import FetchResponse
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess
from vrae.evidence import build_pack

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "tests/fixtures/industry/l2-industrial-v1"
NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


class RecordedResolver:
    async def resolve(self, host):
        if host != "example.org":
            raise CollectionError("SOURCE_NOT_ALLOWED")
        return ("93.184.216.20",)


class RecordedTransport:
    def __init__(self, overrides=None, statuses=None):
        routes = json.loads((DIRECTORY / "routes.json").read_text(encoding="utf-8"))
        self.routes = {path: (DIRECTORY / name).read_bytes() for path, name in routes.items()}
        self.routes.update(overrides or {})
        self.statuses = statuses or {}
        self.requests = []

    async def exchange(self, url, method, ip, budget, max_bytes):
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "example.org" or method != "GET" or parts.path not in self.routes:
            raise CollectionError("SOURCE_NOT_ALLOWED")
        self.requests.append((method, url))
        raw = self.routes[parts.path]
        if len(raw) > max_bytes:
            raise CollectionError("LIMIT_EXCEEDED")
        return FetchResponse(url, self.statuses.get(parts.path, 200),
                             {"content-type": "text/plain" if parts.path == "/robots.txt" else "text/html"}, raw, ip)


def capture(*, overrides=None, statuses=None, retain=True, max_pages=8):
    cases = json.loads((ROOT / "tests/fixtures/contracts/valid.json").read_text(encoding="utf-8"))
    request, policy = [deepcopy(next(c["data"] for c in cases if c["schema"] == name))
                       for name in ("AuditRequest", "SourcePolicy")]
    # L2 is analytic depth, not a new access permission. Native collection keeps
    # its existing L1 read-only eight-page budget/profile; no policy expansion.
    request.update(audit_mode="L1", request_id="req-industrial-l2", audit_id="audit-industrial-l2")
    access = SourceAccess(request, lambda: policy, terms_reference="synthetic-offline-industrial-fixture-v1", now=lambda: NOW)
    transport = RecordedTransport(overrides, statuses)
    collector = Collector(SafeFetcher(RecordedResolver(), transport))
    bundle = asyncio.run(collector.capture("run-industrial-l2", access, limits=Limits(max_pages=max_pages, interval_seconds=0.01), retain_raw_html=retain))
    return bundle, transport


def evidence_pack(**kwargs):
    bundle, transport = capture(**kwargs)
    return build_pack([bundle]), bundle, transport
