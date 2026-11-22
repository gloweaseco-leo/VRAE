"""Bounded HTML link inventory; observed links are hypotheses, not a site audit."""
from html.parser import HTMLParser
import codecs
import re
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


def representative_role(url):
    """New capture selection only; legacy rule role/replay stays unchanged."""
    segments = [s.lower().split('.')[0].replace('_', '-') for s in urlsplit(url).path.split('/')]
    if any(s in ('contact', 'contact-us', 'contactus', 'rfq', 'inquiry') for s in segments):
        return 'CONTACT'
    if any(s in ('about', 'about-us', 'aboutus', 'company', 'factory') for s in segments):
        return 'ABOUT'
    return page_role(url)


def contact_label(text):
    label = ' '.join(text.split()).casefold()
    return label in ('contact', 'contacts', 'contact us', 'contactus', 'contact us now', 'inquiry', 'inquire',
                     'send inquiry', 'send an inquiry', 'rfq', 'request a quote',
                     'request quotation', 'get in touch')


class _ContactLinks(HTMLParser):
    """Closed labeled anchors only; bounded, no hidden/script/form text."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []
        self.anchor: dict | None = None
        self.hrefs: list[str] = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > 8192 or len(self.stack) >= 64:
            raise ValueError('CONTACT_HTML_BOUND')
        values = dict(attrs)
        if tag == 'base' and 'href' in values:
            raise ValueError('CONTACT_BASE_SCOPE_UNSUPPORTED')
        excluded = (len(values) != len(attrs) or tag in
            ('script', 'style', 'template', 'noscript', 'iframe', 'form', 'svg')
            or any(k in values for k in ('hidden', 'inert'))
            or values.get('aria-hidden') == 'true'
            or bool(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',
                              values.get('style') or '', re.I))
            or bool(self.stack and self.stack[-1][1]))
        if tag == 'a':
            if self.anchor is not None:
                raise ValueError('NESTED_CONTACT_ANCHOR')
            self.anchor = {'href': values.get('href'), 'text': '', 'excluded': excluded}
        elif self.anchor is not None and excluded:
            self.anchor['excluded'] = True
        if tag not in ('meta', 'link', 'br', 'hr', 'img', 'input', 'wbr', 'area',
                       'col', 'embed', 'param', 'source', 'track'):
            self.stack.append((tag, excluded))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor['text'] += data
            if len(self.anchor['text']) > 256:
                self.anchor['excluded'] = True

    def handle_endtag(self, tag):
        index = next((i for i in range(len(self.stack)-1, -1, -1)
                      if self.stack[i][0] == tag), None)
        if tag == 'a' and self.anchor is not None:
            a = self.anchor
            if (index is not None and not a['excluded'] and contact_label(a['text'])
                    and a['href'] and len(self.hrefs) < 256):
                self.hrefs.append(a['href'])
            self.anchor = None
        if index is not None:
            del self.stack[index:]


def labelled_contact_targets(raw, base_url):
    """Hints only: the Collector must intersect with its policy-checked inventory."""
    if len(raw) > 131072:
        return set()
    parser = _ContactLinks()
    try:
        parser.feed(raw.decode('utf-8-sig', errors='strict'))
        parser.close()
    except (ValueError, UnicodeError):
        return set()
    targets = set()
    for href in parser.hrefs:
        if len(href) > 2048 or any(ord(c) <= 32 or ord(c) >= 127 for c in href) or '\\' in href or '%' in href:
            continue
        target = urlsplit(urljoin(base_url, href))
        if (target.scheme == 'https' and target.netloc == urlsplit(base_url).netloc
                and not target.username and not target.password and not target.query and not target.fragment):
            targets.add(target.geturl())
    return targets


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


def inventory(body: bytes, base_url: str, access: SourceAccess, *, labelled_contacts=False) -> tuple[list[dict], bool]:
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
    if labelled_contacts:
        # Normalize standard relative Contact links first, then run the SAME
        # current policy/DNS scope checks below on the resulting absolute URL.
        parser.links = sorted(labelled_contact_targets(body, base_url)) + parser.links
    with access.inventory_scope() as discovery_access:
        return _inventory_links(parser, base_url, discovery_access, truncated)


def _inventory_links(parser, base_url, access, truncated):
    found: dict[str, dict] = {}
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
        if url not in found and len(found) >= 256:
            truncated = True
            continue
        found[url] = {"url": url, "role": page_role(url), "discovered_from": base_url}
    return sorted(found.values(), key=lambda x: (ROLES.index(x["role"]), x["url"])), parser.overflow or truncated


def _category_key(url):
    parts = [segment.lower() for segment in urlsplit(url).path.split('/') if segment]
    if len(parts) < 2 or parts[-1] in ('product', 'products', 'category', 'categories'):
        return ''
    return parts[-2]


def _select_l2(items, attempted, *, application_required=False):
    """Opt-in six-role order. Callers keep the page cap; this function does not raise it."""
    chosen = [item for item in items if item['url'] in attempted and item['role'] == 'PRODUCT']
    categories = {_category_key(item['url']) for item in chosen}
    categories.discard('')

    def rank(item):
        role = item['role']
        if role == 'HOME':
            slot = 0
        elif role in ('CATEGORY', 'CATALOG'):
            slot = 1
        elif role == 'PRODUCT':
            category = _category_key(item['url'])
            if category and category not in categories and len(categories) == 0:
                slot = 2
            elif category and category not in categories and len(categories) == 1:
                slot = 3
            else:
                slot = 8
        elif role == 'CONTACT':
            slot = 5 if application_required else 4
        elif role == 'APPLICATION' and application_required:
            slot = 4
        elif role == 'ABOUT':
            slot = 6 if application_required else 5
        else:
            slot = 9
        return slot, item['url']

    candidates = [item for item in items if item['url'] not in attempted]
    candidates.sort(key=rank)
    return candidates[0] if candidates else None


def select_next(items: list[dict], attempted: set[str], covered: set[str], *, representative=False,
                contact_targets=frozenset(), sampling=None, application_required=False) -> dict | None:
    if sampling == 'l2-stage-v1':
        return _select_l2(items, attempted, application_required=application_required)
    candidates = [x for x in items if x["url"] not in attempted]
    roles = ('HOME', 'CATALOG', 'CATEGORY', 'PRODUCT', 'CONTACT', 'ABOUT', 'APPLICATION', 'OTHER') if representative else ROLES
    def key(item):
        role = ('CONTACT' if representative and item['url'] in contact_targets else
                representative_role(item['url']) if representative else item['role'])
        return role in covered, roles.index(role), item['url']
    candidates.sort(key=key)
    return candidates[0] if candidates else None
