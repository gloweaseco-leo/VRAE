"""Versioned roles and bounded closed elements from already retained sources."""
from urllib.parse import urljoin, urlsplit

from vrae.collection.discovery import contact_label, page_role
from vrae.collection.policy import canonical_url
from .universal_static import ancestors, cite, parse, usable


def role(url):
    parts = [s.lower().split('.')[0].replace('_', '-') for s in urlsplit(url).path.split('/')]
    if any(s in ('contact', 'contacts', 'contact-us', 'contactus', 'rfq', 'inquiry') for s in parts):
        return 'CONTACT'
    if any(s in ('about', 'aboutus', 'about-us', 'company', 'company-profile', 'factory') for s in parts):
        return 'ABOUT'
    return page_role(url)


def closed_anchor(node):
    # A malformed nested anchor invalidates that subtree, not unrelated links.
    return (node['tag'] == 'a' and usable(node)
        and not any(a['tag'] == 'a' for a in ancestors(node))
        and not any(c['tag'] == 'a' for c in descendants(node)))


def descendants(node):
    for child in node['children']:
        yield child
        yield from descendants(child)


def document(raw, *, strip_bom=True):
    if len(raw) > 131072:
        raise ValueError('STATIC_LINK_BOUND')
    parser = parse(raw.removeprefix(b'\xef\xbb\xbf') if strip_bom else raw)
    if any(n['tag'] == 'base' and 'href' in n['attrs'] for n in parser.nodes):
        raise ValueError('STATIC_BASE_SCOPE_UNSUPPORTED')
    return parser


def contact_targets(raw, base_url):
    try:
        parser = document(raw)
    except (ValueError, UnicodeError):
        return set()
    result = set()
    for node in parser.nodes:
        if not closed_anchor(node) or not contact_label(node['text']):
            continue
        href = node['attrs'].get('href') or ''
        if (not href or len(href) > 2048 or '\\' in href or '%' in href
                or any(ord(c) <= 32 or ord(c) >= 127 for c in href)):
            continue
        try:
            target = canonical_url(urljoin(base_url, href))
        except ValueError:
            continue
        p, base = urlsplit(target), urlsplit(base_url)
        if p.scheme == 'https' and p.netloc == base.netloc and not p.query and not p.fragment:
            result.add(target)
    return result


def citation(parser, node, evidence, snapshot):
    return {**cite(parser, node), **{k: evidence[k] for k in (
        'evidence_ref', 'source_ref', 'snapshot_ref', 'locator', 'content_sha256')},
        **{k: snapshot[k] for k in ('url', 'final_url', 'observed_at')}}
