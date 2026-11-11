"""Bounded public self-description text; never legal identity or a rule judgment."""
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit

from vrae.collection.discovery import page_role
from vrae.collection.manifest import document_hash
from vrae.collection.policy import canonical_url
from vrae.evidence import EvidenceError, EvidencePack

VERSION = 'ra2b5-trust-facts-1.0.0'
ROLES = {'HOME', 'ABOUT', 'CONTACT'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
        'param', 'source', 'track', 'wbr'}
NAME_LABELS = {'company name', 'organization name', 'legal name', 'brand name',
               '\u516c\u53f8\u540d\u79f0', '\u4f01\u4e1a\u540d\u79f0', '\u7ec4\u7ec7\u540d\u79f0',
               '\u6cd5\u5b9a\u540d\u79f0', '\u54c1\u724c\u540d\u79f0'}
ABOUT_LABELS = {'about us', 'about the company', 'company profile', 'company overview',
                '\u5173\u4e8e\u6211\u4eec', '\u516c\u53f8\u7b80\u4ecb', '\u4f01\u4e1a\u7b80\u4ecb'}
MAX_BYTES = 8_000_000


def _encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


class _Static(HTMLParser):
    """Balanced plain-text subset with original element slices and bounded depth."""
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.raw = raw.decode('utf-8', errors='strict')
        # HTMLParser increments line numbers only on LF, not CR/NEL/U+2028.
        self.line_starts = [0] + [m.end() for m in re.finditer('\n', self.raw)]
        self.stack: list[dict] = []
        self.nodes: list[dict] = []
        self.roots: list[dict] = []
        self.feed(self.raw)
        self.close()
        if self.stack:
            raise ValueError('UNCLOSED_HTML')

    def _source_offset(self):
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if len(self.nodes) >= 2048 or len(self.stack) >= 32:
            raise ValueError('HTML_BOUND')
        if tag in {'script', 'template', 'noscript', 'iframe', 'base', 'select', 'form', 'style'}:
            raise ValueError('DYNAMIC_OR_ALTERNATIVE_SCOPE')
        if (len({k for k, _ in attrs}) != len(attrs)
                or any(k in {'hidden', 'inert', 'style', 'aria-hidden'} for k, _ in attrs)):
            raise ValueError('ATTRIBUTES_OR_PRESENTATION_UNRESOLVED')
        parent = self.stack[-1] if self.stack else None
        parent_tag = parent['tag'] if parent else None
        if ((tag == 'tr' and parent_tag not in {'table', 'tbody', 'thead', 'tfoot'})
                or (tag in {'th', 'td'} and parent_tag != 'tr')
                or (tag in {'tbody', 'thead', 'tfoot'} and parent_tag != 'table')
                or (tag == 'table' and any(n['tag'] == 'table' for n in self.stack))):
            raise ValueError('TABLE_STRUCTURE_UNSUPPORTED')
        children = parent['children'] if parent else self.roots
        node = {'tag': tag, 'attrs': dict(attrs), 'children': [], 'parent': parent, 'text': '',
                'line': self.getpos()[0], 'column': self.getpos()[1],
                'start_tag': self.get_starttag_text(), 'offset': self._source_offset(),
                'path': (parent['path'] if parent else '') + f'/{tag}[{len(children) + 1}]'}
        children.append(node)
        self.nodes.append(node)
        if tag in VOID:
            node['end'] = self._source_offset() + len(node['start_tag'])
        else:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            raise ValueError('NONVOID_SELF_CLOSING')

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1]['tag'] != tag:
            raise ValueError('UNBALANCED_HTML')
        node = self.stack.pop()
        node['end'] = self.raw.index('>', self._source_offset()) + 1

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]['text'] += data


def _position(node):
    return {k: node[k] for k in ('path', 'line', 'column', 'start_tag')}


def _records(doc):
    result = []
    for source in doc['sources']:
        if source['kind'] != 'CaptureManifest':
            continue
        for index, page in enumerate(source['document']['pages']):
            locator = f'/pages/{index}'
            snap = next(s for s in doc['snapshots'] if s['source_ref'] == source['source_ref']
                        and s['locator'] == locator + '/snapshot')
            result.append({'source_ref': source['source_ref'], 'locator': locator,
                'snapshot_ref': snap['snapshot_ref'], 'url': snap['url'], 'final_url': snap['final_url'],
                'observed_at': snap['observed_at'], 'snapshot': snap,
                'http_status': page['http_status'], 'error': page['error'],
                'redirect_trace': page['redirect_trace'],
                'evidence_refs': sorted(e['evidence_ref'] for e in doc['evidence']
                                        if e['snapshot_ref'] == snap['snapshot_ref'])})
    return result


def _contact(href, base):
    """Return a supported literal endpoint; no request, deliverability or ownership check."""
    if not href or len(href) > 2048:
        raise ValueError('HREF_UNSUPPORTED')
    if href.startswith('mailto:'):
        if not re.fullmatch(r'mailto:[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+', href):
            raise ValueError('MAILTO_UNSUPPORTED')
        return href, 'MAILTO_LITERAL'
    if href.startswith('tel:'):
        if not re.fullmatch(r'tel:\+?[0-9][0-9().-]{2,30}', href):
            raise ValueError('TEL_UNSUPPORTED')
        return href, 'TEL_LITERAL'
    if any(ord(c) <= 32 or ord(c) >= 127 for c in href):
        raise ValueError('HREF_UNSUPPORTED')
    url = canonical_url(urljoin(base, href))
    if page_role(url) != 'CONTACT':
        return None, None
    if urlsplit(url).netloc != urlsplit(base).netloc or urlsplit(url).scheme != urlsplit(base).scheme:
        raise ValueError('CROSS_ORIGIN_CONTACT')
    return url, 'SAME_ORIGIN_CONTACT_PATH'


def _page_facts(raw, ev, source, records):
    if len(raw) > 131072:
        raise ValueError('HTML_BOUND')
    parser = _Static(raw)
    facts: list[dict] = []
    organizations = [n for n in parser.nodes if n['attrs'].get('itemtype') in (
        'https://schema.org/Organization', 'http://schema.org/Organization')
        and 'itemscope' in n['attrs']]
    if len(organizations) > 1:
        raise ValueError('MULTIPLE_ORGANIZATION_SCOPES')

    def cite(node):
        return {'text': node['text'], 'raw_element': parser.raw[node['offset']:node['end']],
            'element': _position(node),
            **{k: ev[k] for k in ('evidence_ref', 'source_ref', 'snapshot_ref', 'locator', 'content_sha256')},
            **{k: source[k] for k in ('url', 'final_url', 'observed_at')}}

    def add(kind, node, **extra):
        if node['children'] or not node['text'].strip():
            raise ValueError('PLAIN_NONEMPTY_TEXT_REQUIRED')
        if len(facts) >= 128:
            raise ValueError('FACT_BOUND')
        facts.append({'kind': kind, 'citation': cite(node), **extra})

    for node in parser.nodes:
        attrs, tag = node['attrs'], node['tag']
        if attrs.get('itemprop') == 'name':
            ancestors = []
            parent = node['parent']
            while parent:
                ancestors.append(parent)
                parent = parent['parent']
            scopes = [p for p in ancestors if 'itemscope' in p['attrs']]
            if not scopes or all(scopes[0] is not org for org in organizations):
                raise ValueError('NAME_SCOPE_UNRESOLVED')
            add('DECLARED_NAME', node, basis='ORGANIZATION_SCOPE_NAME_TEXT',
                scope_element=_position(scopes[0]), label_citation=None)
        if tag == 'tr' and node['children'] and node['children'][0]['tag'] == 'th':
            cells = node['children']
            label = cells[0]
            if label['text'].strip().casefold() in NAME_LABELS:
                if (len(cells) != 2 or cells[1]['tag'] != 'td' or label['children']
                        or not node['parent'] or node['parent']['tag'] not in {'table', 'tbody', 'thead'}):
                    raise ValueError('NAME_LABEL_STRUCTURE_UNSUPPORTED')
                add('DECLARED_NAME', cells[1], basis='EXPLICIT_TABLE_LABEL', label_citation=cite(label))
        if tag == 'section':
            children = node['children']
            heading = children[0] if children and children[0]['tag'] in {'h1', 'h2', 'h3'} else None
            if heading and heading['text'].strip().casefold() in ABOUT_LABELS:
                if heading['children']:
                    raise ValueError('ABOUT_HEADING_UNSUPPORTED')
                for child in children[1:]:
                    if child['tag'] == 'p':
                        add('SELF_DESCRIPTION', child, label_citation=cite(heading))
        if tag == 'address':
            add('ADDRESS_TEXT', node, basis='ADDRESS_ELEMENT_NOT_VERIFIED_CONTACT_OWNERSHIP')
        if tag == 'a' and 'href' in attrs:
            endpoint, kind = _contact(attrs['href'], source['final_url'])
            if endpoint:
                targets = [r for r in records if r['url'] == endpoint] if kind == 'SAME_ORIGIN_CONTACT_PATH' else []
                add('STATIC_CONTACT_LINK', node, raw_href=attrs['href'], endpoint=endpoint,
                    endpoint_kind=kind, target_responses=targets,
                    target_scope='CAPTURED_RESPONSE_METADATA_ONLY' if targets else 'TARGET_NOT_CAPTURED',
                    limit='STATIC_LINK_ONLY_NOT_REACHABILITY_DELIVERABILITY_OR_OWNERSHIP')
    return facts


def _extract(pack, expected_pack_ref):
    if not isinstance(expected_pack_ref, str) or not re.fullmatch(r'ep-[0-9a-f]{64}', expected_pack_ref):
        raise ValueError('PIN_REQUIRED')
    pack.verify(expected_ref=expected_pack_ref)
    doc = pack.document
    records = _records(doc)
    pages = []
    for source in records:
        if page_role(source['url']) not in ROLES:
            continue
        row = {'source_page': source, 'status': 'UNKNOWN', 'reason': 'RAW_COMPLETE_STATIC_HTML_REQUIRED',
               'facts': [], 'evidence_ids': [], 'entity_scope_ambiguous': False}
        pages.append(row)
        snap = source['snapshot']
        if snap['status'] == 'ACCESS_BLOCKED':
            row.update(status='ACCESS_BLOCKED', reason='CAPTURE_ACCESS_BLOCKED')
            continue
        if (snap['status'] != 'OBSERVED' or not source['final_url']
                or page_role(source['final_url']) not in ROLES or source['http_status'] != 200):
            continue
        ev = next((e for e in doc['evidence'] if e['snapshot_ref'] == snap['snapshot_ref']
                   and e['kind'] == 'HTTP_BODY' and e['status'] == 'OBSERVED' and e['blob_ref']), None)
        if ev is None:
            continue
        raw = pack.resolve(ev['evidence_ref'], expected_pack_ref=expected_pack_ref)['content']
        try:
            facts = _page_facts(raw, ev, source, records)
        except (ValueError, UnicodeError) as exc:
            row['reason'] = 'HTML_OR_ENTITY_SCOPE_UNSUPPORTED_OR_AMBIGUOUS'
            row['entity_scope_ambiguous'] = str(exc) in {
                'MULTIPLE_ORGANIZATION_SCOPES', 'NAME_SCOPE_UNRESOLVED'}
            continue
        row['facts'] = facts
        if facts:
            row.update(status='EXTRACTED', reason='CAPTURED_SELF_DECLARED_SOURCE_TEXT_ONLY',
                       evidence_ids=[ev['evidence_ref']])
        else:
            row['reason'] = 'NO_SUPPORTED_STRUCTURED_TEXT'
    names = {f['citation']['text'].strip().casefold() for p in pages for f in p['facts']
             if f['kind'] == 'DECLARED_NAME'}
    ambiguous = len(names) > 1 or any(p['entity_scope_ambiguous'] for p in pages)
    if ambiguous:
        for row in pages:
            if row['status'] == 'EXTRACTED':
                row.update(status='UNKNOWN', reason='MULTIPLE_DECLARED_NAMES_UNRESOLVED', evidence_ids=[])
    links = any(f['kind'] == 'STATIC_CONTACT_LINK' for p in pages if p['status'] == 'EXTRACTED'
                for f in p['facts'])
    status = ('EXTRACTED' if len(names) == 1 and links and not ambiguous else
              'ACCESS_BLOCKED' if pages and all(p['status'] == 'ACCESS_BLOCKED' for p in pages) else 'UNKNOWN')
    output = {'extractor_version': VERSION, 'expected_pack_ref': expected_pack_ref,
        **{k: doc[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')},
        'status': status, 'pages': pages, 'coverage': doc['coverage'],
        'unvisited_candidates': [c for c in doc['coverage'] if c['status'] == 'NOT_VISITED'
                                 and c['url'] and page_role(c['url']) in ROLES],
        'trust01_enabled': False, 'trust01_result': 'UNKNOWN',
        'limitations': ['SELF_DECLARED_SOURCE_TEXT_NOT_LEGAL_ENTITY_AUTHENTICATION',
            'NO_FACTORY_CERTIFICATE_EXPORT_CAPACITY_OR_CONTACT_OWNERSHIP_VERIFICATION',
            'STATIC_LINK_NOT_REACHABILITY_OR_VALID_INQUIRY', 'NO_RENDERED_VISIBILITY_OR_COMPLETENESS',
            'MISSING_AMBIGUOUS_OR_BLOCKED_INFORMATION_IS_NOT_A_WEBSITE_OR_COMPANY_DEFECT',
            'URL_ROLES_AND_EXACT_SUPPORTED_LABELS_ONLY_NO_NLP_OR_DOMAIN_IDENTITY_INFERENCE',
            'OFFLINE_SYNTHETIC_CONSISTENCY_NOT_SIGNATURE_OR_CURRENT_AUTHORIZATION']}
    output['facts_ref'] = 'tf-' + document_hash(output)
    if len(_encode(output)) > MAX_BYTES:
        raise ValueError('OUTPUT_BOUND')
    return output


def extract(pack: EvidencePack, *, expected_pack_ref: str) -> dict:
    """Use a separately trusted caller pin; return detached deterministic source facts."""
    try:
        return _extract(pack, expected_pack_ref)
    except Exception as exc:
        raise EvidenceError('TRUST_FACTS_INTEGRITY') from exc


def verify_facts(output: dict, pack: EvidencePack, *, expected_pack_ref: str) -> None:
    """Replay every field from original retained bytes; a fresh outer hash is insufficient."""
    try:
        raw = _encode(output)
        if len(raw) > MAX_BYTES or raw != _encode(extract(pack, expected_pack_ref=expected_pack_ref)):
            raise ValueError('MISMATCH')
    except Exception as exc:
        raise EvidenceError('TRUST_FACTS_INTEGRITY') from exc
