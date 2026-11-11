"""Conservative robots subset: deny any applicable Disallow, never expand via Allow.

Unknown syntax fails closed. No network-capable parser API is used. Terms permission
is a separate trusted SourceAccess prerequisite, not inferred from robots.
"""
import re
from fnmatch import fnmatchcase
from urllib.parse import urlsplit

from .errors import CollectionError
from .http_transport import FetchResponse


class RobotsRules:
    def __init__(self, response: FetchResponse):
        self.denials: list[str] = []
        self.delay = 0.0
        if response.status in (404, 410):
            return
        if response.status != 200 or response.headers.get("content-type", "").split(";")[0].lower() != "text/plain":
            raise CollectionError("ROBOTS_UNKNOWN")
        if len(response.body) > 65_536:
            raise CollectionError("LIMIT_EXCEEDED")
        try:
            text = response.body.decode("utf-8-sig", errors="strict")
        except UnicodeError as exc:
            raise CollectionError("ROBOTS_UNKNOWN") from exc
        agents: list[str] = []
        directives = False
        saw_agent = False
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if ":" not in line:
                raise CollectionError("ROBOTS_UNKNOWN")
            key, value = (x.strip() for x in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if directives:
                    agents = []
                    directives = False
                agents.append(value.lower())
                saw_agent = True
                continue
            if key == "sitemap":
                continue  # Never fetch sitemap automatically.
            if not agents:
                raise CollectionError("ROBOTS_UNKNOWN")
            directives = True
            applicable = any(a == "*" or a in "vrae-audit" for a in agents)
            if not applicable:
                continue
            if key in ("allow", "disallow"):
                if value and (not value.startswith("/") or len(value) > 2048
                        or "%" in value or any(ord(c) < 32 or ord(c) >= 127 for c in value)):
                    raise CollectionError("ROBOTS_UNKNOWN")
                if key == "disallow" and value:
                    self.denials.append(value)
            elif key == "crawl-delay":
                if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) or float(value) > 120:
                    raise CollectionError("ROBOTS_UNKNOWN")
                self.delay = max(self.delay, float(value))
            else:
                raise CollectionError("ROBOTS_UNKNOWN")
        if text.strip() and not saw_agent:
            raise CollectionError("ROBOTS_UNKNOWN")

    def check(self, url: str):
        path = urlsplit(url).path or "/"
        for rule in self.denials:
            # '*' matches any sequence, '$' end anchor. All matching denials win.
            end = rule.endswith("$")
            # Escape fnmatch-only metacharacters; its translation uses atomic groups
            # and avoids exponential backtracking on hostile repeated '*' patterns.
            pattern = (rule[:-1] if end else rule).replace("[", "[[]").replace("?", "[?]")
            if fnmatchcase(path, pattern + ("" if end else "*")):
                raise CollectionError("ROBOTS_DISALLOWED")
