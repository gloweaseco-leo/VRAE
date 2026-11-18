"""Bounded HTTP candidates. No native execution, fact admission or site inference."""
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit

from vrae.collection.discovery import page_role
from vrae.collection.manifest import document_hash
from vrae.collection.policy import canonical_url
from vrae.domain.contracts import validate_contract
from vrae.rules.execution import _metadata, _records

SOURCE_VERSION = 's2-static-http-1.0.0'
RULE_VERSION = 's2-static-1.0.0'
RULES = ('DISC-03', 'SEO-02', 'TECH-01')
LIMIT = ('Retained bounded HTTP source only. Path roles are lexical collector roles; '
         'no industry semantics, rendered visibility, crawler/indexing outcome, whole-site '
         'completeness, engineering fit, authentication or current authorization assertion. '
         'Missing, unsupported and metadata-only inputs remain UNKNOWN; no site defect.')
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
        'param', 'source', 'track', 'wbr'}
IGNORED = {'head', 'script', 'style', 'template', 'noscript', 'svg', 'math',
           'textarea', 'iframe', 'object'}


class StaticHTML(HTMLParser):
    """Conservative explicit body subset with UTF-8 byte intervals, never DOM geometry."""
    def __init__(self, raw):
        super().__init__(convert_charrefs=False)
        self.text = raw.decode('utf-8', errors='strict')
        self.lines = [0, *[m.end() for m in re.finditer('\n', self.text)]]
        self.stack: list[tuple[str, bool]] = []
        self.anchors: list[dict] = []
        self.texts: list[dict] = []
        self.active: dict | None = None
        self.ambiguous = False
        self.bodies = 0
        self.count = 0

    def char_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def span(self, start, end):
        return {'byte_start': len(self.text[:start].encode()),
                'byte_end': len(self.text[:end].encode()), 'quote': self.text[start:end],
                'offset_basis': 'ORIGINAL_UTF8_BYTES'}

    def eligible(self):
        return any(tag == 'body' for tag, _ in self.stack) and not any(x[1] for x in self.stack)

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > 512 or len(self.stack) > 64 or tag == 'base':
            self.ambiguous = True
        if tag == 'body':
            self.bodies += 1
        names = [k for k, _ in attrs]
        if len(names) != len(set(names)):
            self.ambiguous = True
        ignored = tag in IGNORED or any(k in ('hidden', 'inert') for k in names)
        if tag not in VOID:
            self.stack.append((tag, ignored))
        if tag == 'a' and self.eligible():
            if self.active is not None:
                self.ambiguous = True
            href = next((v for k, v in attrs if k == 'href'), None)
            self.active = {'start': self.char_offset(), 'href': href, 'has_text': False}

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag:
            self.ambiguous = True
            return
        if tag == 'a' and self.active is not None:
            end = re.match(r'</a\s*>', self.text[self.char_offset():], re.I)
            if end and self.active['has_text']:
                self.anchors.append({**self.span(self.active['start'], self.char_offset() + len(end[0])),
                                     'href': self.active['href']})
            self.active = None
        self.stack.pop()

    def handle_data(self, data):
        if not self.eligible() or not unescape(data).strip():
            return
        if self.active is not None:
            self.active['has_text'] = True
        elif len(self.texts) < 128:
            self.texts.append(self.span(self.char_offset(), self.char_offset() + len(data)))
        else:
            self.ambiguous = True

    def handle_entityref(self, name):
        # Entity-only labels are outside this deliberately narrow first subset.
        pass

    def unknown_decl(self, data):
        self.ambiguous = True

    def handle_comment(self, data):
        if self.text[self.char_offset():].startswith('<!['):
            self.ambiguous = True

    def finish(self):
        self.feed(self.text)
        self.close()
        if self.stack or self.active is not None or self.bodies != 1 or len(self.anchors) > 128:
            self.ambiguous = True


def _url(href, base):
    if (type(href) is not str or not href or len(href) > 2048
            or any(ord(c) <= 32 or ord(c) >= 127 for c in href)
            or any(c in href for c in ('\\', '%'))):
        return None
    try:
        parts = urlsplit(href)
        if parts.query or parts.fragment or href.startswith('#'):
            return None
        value = canonical_url(urljoin(base, href))
        if urlsplit(value).netloc != urlsplit(base).netloc:
            return None
        return value
    except ValueError:
        return None


def _evidence(pack, doc, record):
    snapshot = record[2]
    ev = next((e for e in doc['evidence'] if e['snapshot_ref'] == snapshot['snapshot_ref']
               and e['kind'] == 'HTTP_BODY' and e['status'] == 'OBSERVED'
               and e['blob_ref'] is not None), None)
    if ev is None:
        return None, None
    return ev, pack.resolve(ev['evidence_ref'], expected_pack_ref=pack.ref)['content']


def _cite(ev, span):
    return {key: ev[key] for key in ('evidence_ref', 'source_ref', 'snapshot_ref',
                                    'locator', 'content_sha256')} | span


def _row(doc, rule, result, reason, *, response=None, citations=None, target=None):
    citations = citations or []
    observation = {'schema_version': '1.0', 'tenant_id': doc['tenant_id'], 'run_id': doc['run_id'],
        'rule_id': rule, 'rule_version': RULE_VERSION, 'result': result,
        'kind': 'OBJECTIVE' if result == 'PASS' else 'UNKNOWN',
        'evidence_ids': sorted({c['evidence_ref'] for c in citations}) if result == 'PASS' else [],
        'statement': {
            'DISC-03': 'Check for a captured application-path anchor and captured product-path response.',
            'SEO-02': 'Check for captured product-path text and a static same-site HTTP anchor.',
            'TECH-01': 'Check exact recorded response status and redirect metadata; no live health claim.',
        }[rule] + ' Bounded candidate result: ' + result + '.', 'coverage_note': LIMIT}
    row = {'observation': observation, 'reason': reason, 'response': response,
           'citations': citations, 'target_response': target,
           'source_version': SOURCE_VERSION, 'admission': 'CANDIDATE_ONLY'}
    observation['observation_id'] = 'obs-' + document_hash(row)
    validate_contract('Observation', observation)
    return row


def project_static(pack):
    """Internal composition after scope/pin validation by evaluate_s2; no external IO."""
    doc = pack.document
    records = _records(doc)
    rows = []
    for record in records:
        _, page, snapshot, _ = record
        response = _metadata(record)
        ev, raw = _evidence(pack, doc, record)
        blocked = snapshot['status'] == 'ACCESS_BLOCKED'
        result = 'ACCESS_BLOCKED' if blocked else 'UNKNOWN'
        reason = 'SOURCE_ACCESS_BLOCKED' if blocked else 'RETAINED_OBSERVED_HTTP_REQUIRED'
        if not blocked and page['http_status'] is not None and page['http_status'] >= 400:
            reason = 'RECORDED_HTTP_ERROR_METADATA_ONLY'
        parsed = None
        if ev is not None and raw is not None and len(raw) <= 131072:
            try:
                parsed = StaticHTML(raw)
                parsed.finish()
            except (ValueError, UnicodeError, AssertionError):
                parsed = None
        tech_cites = []
        if ev is not None and parsed is not None and parsed.text and page['http_status'] == 200:
            tech_cites = [_cite(ev, parsed.span(0, min(256, len(parsed.text))))]
        rows.append(_row(doc, 'TECH-01', 'PASS' if tech_cites else result,
            'RETAINED_HTTP_200_RESPONSE' if tech_cites else reason,
            response=response, citations=tech_cites))
        # Lexical roles only; no inferred applicability or industry exclusion.
        if page['role'] not in ('APPLICATION', 'PRODUCT'):
            continue
        rule = 'DISC-03' if page['role'] == 'APPLICATION' else 'SEO-02'
        if blocked or parsed is None or parsed.ambiguous or page['http_status'] != 200:
            rows.append(_row(doc, rule, result, reason if blocked or ev is None else
                'UNSUPPORTED_OR_AMBIGUOUS_STATIC_HTML', response=response))
            continue
        anchors = [(a, _url(a['href'], snapshot['final_url'])) for a in parsed.anchors]
        if rule == 'SEO-02':
            anchors = [(a, url) for a, url in anchors if url is not None]
            if parsed.texts and anchors:
                rows.append(_row(doc, rule, 'PASS', 'SOURCE_TEXT_AND_HTTP_ANCHOR_PRESENT',
                    response=response, citations=[_cite(ev, parsed.texts[0]), _cite(ev, anchors[0][0])]))
            else:
                rows.append(_row(doc, rule, 'UNKNOWN', 'NO_SUPPORTED_TEXT_ANCHOR_PAIR', response=response))
            continue
        matched = False
        for anchor, url in anchors:
            if url is None or page_role(url) != 'PRODUCT':
                continue
            matched = True
            target = next((r for r in records if r[2]['url'] == url), None)
            target_meta = _metadata(target) if target else None
            target_ev, target_raw = _evidence(pack, doc, target) if target else (None, None)
            target_span = None
            if target_raw and len(target_raw) <= 131072:
                try:
                    target_text = target_raw.decode('utf-8', errors='strict')[:256]
                    target_span = {'byte_start': 0, 'byte_end': len(target_text.encode()),
                                   'quote': target_text, 'offset_basis': 'ORIGINAL_UTF8_BYTES'}
                except UnicodeError:
                    pass
            supported = (target is not None and target[1]['http_status'] == 200
                         and target_ev is not None and target_span is not None
                         and page_role(target[2]['final_url']) == 'PRODUCT')
            citations = [_cite(ev, anchor)]
            if supported:
                # The target's real evidence identity and digest bind response existence.
                citations.append(_cite(target_ev, target_span))
            state = ('PASS' if supported else 'ACCESS_BLOCKED' if target is not None
                     and target[2]['status'] == 'ACCESS_BLOCKED' else 'UNKNOWN')
            rows.append(_row(doc, rule, state,
                'CAPTURED_APPLICATION_TO_PRODUCT_PATH' if supported else 'TARGET_INCOMPLETE_OR_METADATA_ONLY',
                response=response, target=target_meta, citations=citations))
        if not matched:
            rows.append(_row(doc, rule, 'UNKNOWN', 'NO_SUPPORTED_APPLICATION_PRODUCT_ANCHOR', response=response))
    for rule in RULES:
        if not any(r['observation']['rule_id'] == rule for r in rows):
            rows.append(_row(doc, rule, 'UNKNOWN', 'REQUIRED_HTTP_ROLE_NOT_CAPTURED'))
    return {'source_version': SOURCE_VERSION, 'rule_version': RULE_VERSION,
            'authority': 'READ_ONLY_CANDIDATES_NOT_FINDINGS', 'rows': rows,
            'limitations': [LIMIT, 'NO_INDUSTRY_CONFIGURATION_NO_NOT_APPLICABLE',
                            'METADATA_HAS_SOURCE_POINTER_NOT_EVIDENCE_REF',
                            'NO_NEGATIVE_SITE_JUDGMENT_IN_THIS_VERSION']}
