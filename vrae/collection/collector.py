"""Bounded collection entry point; never emits Observation/Finding or diagnostic success."""
import re
from urllib.parse import urlsplit, urlunsplit

from .discovery import inventory, page_role, select_next
from .errors import CollectionError
from .fetcher import SafeFetcher
from .limits import Budget, HostLeases, Limits
from .manifest import page_record, seal, sha256
from .policy import SourceAccess
from .robots import RobotsRules


class Collector:
    def __init__(self, fetcher: SafeFetcher):
        self.fetcher = fetcher

    async def capture(self, run_id: str, access: SourceAccess, *, limits: Limits | None = None,
                      budget: Budget | None = None, retain_raw_html: bool = False):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,127}", run_id):
            raise CollectionError("INPUT_INVALID")
        budget = budget or Budget(limits or Limits(), access)
        if budget.access is not access:
            raise CollectionError("INPUT_INVALID")
        if budget.run_id is not None and budget.run_id != run_id:
            raise CollectionError("INPUT_INVALID")
        budget.run_id = run_id
        pages: list[dict] = []
        objects: dict[str, bytes] = {}
        items: list[dict] = []
        errors: list[dict] = []
        robots: dict = {"url": None, "status": None, "sha256": None, "trace": []}
        truncated = False
        with HostLeases.claim(str(access.host)):
            try:
                parts = urlsplit(access.start_url)
                robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
                # Scope must explicitly permit /robots.txt; never broaden SourcePolicy here.
                robots["url"] = robots_url
                robots_response, trace = await self.fetcher.fetch(robots_url, "GET", budget, max_bytes=65_536)
                robots.update(status=robots_response.status, sha256=sha256(robots_response.body), trace=trace)
                rules = RobotsRules(robots_response)
                budget.interval = max(budget.interval, rules.delay)
                budget.next_request = max(budget.next_request, budget.clock() + rules.delay)
                attempted: set[str] = set()
                covered: set[str] = set()
                items = [{"url": access.start_url, "role": page_role(access.start_url),
                          "discovered_from": access.start_url}]
                cap = min(budget.limits.max_pages, 5 if access.audit["audit_mode"] == "L0" else 8)
                while budget.pages < cap:
                    candidate = select_next(items, attempted, covered)
                    if candidate is None:
                        break
                    url, role = candidate["url"], candidate["role"]
                    budget.page()
                    attempted.add(url)
                    response, trace = None, []
                    error = None
                    try:
                        def allowed(target):
                            # Robots are origin-specific; defer protocol upgrades to another run.
                            if urlsplit(target).scheme != parts.scheme:
                                raise CollectionError("REDIRECT_BLOCKED")
                            rules.check(target)
                        response, trace = await self.fetcher.fetch(url, "GET", budget, allow_url=allowed)
                        if response.status in (401, 403, 429, 503):
                            raise CollectionError("ACCESS_BLOCKED")
                        if response.status != 200:
                            raise CollectionError("HTTP_ERROR")
                        if response.headers.get("content-type", "").split(";")[0].strip().lower() not in (
                                "text/html", "application/xhtml+xml"):
                            raise CollectionError("CONTENT_TYPE_INVALID")
                        lowered = response.body[:32768].lower()
                        if any(mark in lowered for mark in (
                                b"cf-chl-", b"verify you are human", b"captcha", b"access denied")):
                            raise CollectionError("ACCESS_BLOCKED")
                        discovered, overflow = inventory(response.body, response.url, access)
                        budget.check()
                        truncated |= overflow
                        known = {x["url"] for x in items}
                        for item in discovered:
                            if item["url"] not in known:
                                if len(items) >= 256:
                                    truncated = True
                                    break
                                items.append(item)
                                known.add(item["url"])
                        attempted.add(response.url)
                        covered.add(role)
                    except CollectionError as exc:
                        error = exc
                        trace = exc.trace or trace
                    page, saved = page_record(access, run_id, url, role, response=response,
                        trace=trace, error=error, retain_raw=retain_raw_html)
                    pages.append(page)
                    objects.update(saved)
                    if error and error.code in ("CANCELLED", "TIMEOUT", "POLICY_REVOKED",
                            "POLICY_EXPIRED", "SOURCE_NOT_ALLOWED", "LIMIT_EXCEEDED", "ACCESS_BLOCKED"):
                        break
            except CollectionError as exc:
                errors.append(exc.document())
                if not pages:
                    page, _ = page_record(access, run_id, access.start_url,
                                         page_role(access.start_url), error=exc, trace=exc.trace)
                    pages.append(page)
            return seal(access, run_id, pages, objects, items, budget, robots, errors, truncated)
