"""Bounded HTML link inventory; observed links are hypotheses, not a site audit."""
from html.parser import HTMLParser
import codecs
from urllib.parse import urljoin, urlsplit

from .errors import CollectionError
from .policy import SourceAccess

ROLES = ("HOME", "CATALOG", "CATEGORY", "PRODUCT", "APPLICATION", "ABOUT", "CONTACT", "OTHER")


def page_role(url: str) -> str:
    segments = [s.lower() for s in urlsplit(url).path.split("/") if s]
    if not segments:
        return "HOME"
    if any(s in ("contact", "contact-us", "rfq", "inquiry") for s in segments):
        return "CONTACT"
    if any(s in ("about", "about-us", "company", "factory") for s in segments):
        return "ABOUT"
    if any(s in ("applications", "application", "solutions", "solution") for s in segments):
        return "APPLICATION"
    if any(s in ("category", "categories") for s in segments):
        return "CATEGORY"
    if any(s in ("product", "products") for s in segments):
        return "CATALOG" if segments[-1] in ("product", "products") else "PRODUCT"
    if "catalog" in segments:
        return "CATALOG"
    return "OTHER"


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.overflow = False
        self.has_html = False

    def handle_starttag(self, tag, attrs):
        if tag in ("html", "body", "title", "a", "p", "div", "main"):
            self.has_html = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                if len(self.links) < 256:
                    self.links.append(href)
                else:
                    self.overflow = True


def inventory(body: bytes, base_url: str, access: SourceAccess) -> tuple[list[dict], bool]:
    parser = _Links()
    truncated = len(body) > 131_072
    try:
        decoder = codecs.getincrementaldecoder("utf-8-sig")(errors="strict")
        text = decoder.decode(body[:131_072], final=not truncated)
    except UnicodeError as exc:
        raise CollectionError("CONTENT_ENCODING_INVALID") from exc
    if not text.strip():
        raise CollectionError("EVIDENCE_INSUFFICIENT")
    parser.feed(text)
    if not parser.has_html:
        raise CollectionError("EVIDENCE_INSUFFICIENT")
    found = {}
    for href in parser.links:
        try:
            if len(href) > 2048 or any(ord(c) <= 32 or ord(c) >= 127 for c in href):
                continue
            if "\\" in href or "%" in href or any(
                    p in (".", "..") for p in urlsplit(href).path.split("/")):
                continue
            url = access.check(urljoin(base_url, href))
        except CollectionError:
            continue
        if urlsplit(url).path.lower().endswith((".pdf", ".zip", ".jpg", ".png", ".exe")):
            continue
        found[url] = {"url": url, "role": page_role(url), "discovered_from": base_url}
    return sorted(found.values(), key=lambda x: (ROLES.index(x["role"]), x["url"])), parser.overflow or truncated


def select_next(items: list[dict], attempted: set[str], covered: set[str]) -> dict | None:
    candidates = [x for x in items if x["url"] not in attempted]
    candidates.sort(key=lambda x: (x["role"] in covered, ROLES.index(x["role"]), x["url"]))
    return candidates[0] if candidates else None
