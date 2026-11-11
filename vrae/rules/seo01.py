"""Positive-only original head tags; never indexing, ranking or SEO-health proof."""
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit

from vrae.collection.manifest import document_hash
from vrae.collection.policy import canonical_url
from vrae.domain.contracts import validate_contract
from .execution import _metadata, _records, _row

COVERAGE = ('One retained captured HOME-request static HTML head only; tag presence is not '
    'rendered state, SEO quality, canonical target availability, crawler access, actual indexing, '
    'Google canonical selection, ranking, multilingual correctness or whole-site completeness. '
    'Missing/ambiguous tags are UNKNOWN, never a defect.')


class HeadSignals(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.lines = [0, *[m.end() for m in re.finditer('\n', text)]]
        self.head = False
        self.heads = 0
        self.closed = False
        self.body = False
        self.ignored: list[str] = []
        self.active_title: dict | None = None
        self.titles: list[dict] = []
        self.canonicals: list[dict] = []
        self.descriptions: list[dict] = []
        self.issues: list[str] = []
        self.count = 0
        self.context: list[str] = []

    def char_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def unknown_decl(self, data):
        self.issues.append('UNSUPPORTED_MARKED_SECTION')

    def handle_comment(self, data):
        # Python versions differ: a malformed marked section may be a bogus comment.
        if self.text[self.char_offset():].startswith('<!['):
            self.issues.append('UNSUPPORTED_MARKED_SECTION')

    def element(self, tag, raw, start=None):
        line, column = self.getpos()
        return {'tag': tag, 'line': line, 'column': column,
            'character_start': self.char_offset() if start is None else start,
            'character_end': (self.char_offset() if start is None else start) + len(raw),
            'offset_basis': 'UTF8_SIG_DECODED_CHARACTER_RANGE', 'raw_element': raw}

    def handle_starttag(self, tag, attrs):
        if self.ignored:
            if tag in ('script', 'style', 'template', 'noscript'):
                self.ignored.append(tag)
            return
        if self.active_title is not None:
            self.issues.append('UNSUPPORTED_TITLE_MARKUP')
        if tag in ('script', 'style', 'template', 'noscript'):
            self.ignored.append(tag)
            return
        if tag == 'head' and self.context not in ([], ['html']):
            self.issues.append('HEAD_IN_UNSUPPORTED_PARENT')
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.context.append(tag)
        if tag == 'base':
            self.issues.append('BASE_URL_UNSUPPORTED')
        if tag == 'head':
            self.heads += 1
            if self.head or self.closed or self.body:
                self.issues.append('AMBIGUOUS_HEAD_STRUCTURE')
            self.head = True
            return
        if tag == 'body':
            self.body = True
            if self.head:
                self.issues.append('HEAD_NOT_CLOSED_BEFORE_BODY')
                self.head = False
        if not self.head:
            return
        if tag not in ('title', 'link', 'meta', 'base'):
            self.issues.append('UNSUPPORTED_HEAD_ELEMENT')
        self.count += 1
        if self.count > 128:
            self.issues.append('HEAD_ELEMENT_BOUND')
            return
        raw = self.get_starttag_text()
        if tag == 'base':
            self.issues.append('BASE_URL_UNSUPPORTED')
        elif tag == 'title':
            self.active_title = {'element': self.element(tag, raw), 'start_tag': raw}
        elif tag == 'link':
            rels = [value for key, value in attrs if key == 'rel']
            if any('canonical' in (value or '').lower().split() for value in rels):
                hrefs = [value for key, value in attrs if key == 'href']
                self.canonicals.append({'element': self.element(tag, raw),
                    'attributes': [{'name': k, 'value': v} for k, v in attrs],
                    'href': hrefs[0] if len(hrefs) == 1 else None,
                    'attributes_unambiguous': len(rels) == 1 and len(hrefs) == 1})
        elif tag == 'meta':
            names = [value for key, value in attrs if key == 'name']
            if any((value or '').lower() == 'description' for value in names):
                values = [value for key, value in attrs if key == 'content']
                self.descriptions.append({'element': self.element(tag, raw),
                    'value': values[0] if len(values) == 1 else None,
                    'attributes_unambiguous': len(names) == 1 and len(values) == 1})

    def handle_endtag(self, tag):
        if self.ignored:
            if tag == self.ignored[-1]:
                self.ignored.pop()
            return
        if self.head and tag not in ('title', 'head'):
            self.issues.append('UNSUPPORTED_HEAD_END')
        if tag in self.context:
            self.context = self.context[:len(self.context) - 1 - self.context[::-1].index(tag)]
        if tag == 'title' and self.active_title is not None:
            title = self.active_title
            start = title['element']['character_start']
            end = self.char_offset()
            closing = re.match(r'</title\s*>', self.text[end:], re.IGNORECASE)
            if closing is None:
                self.issues.append('UNSUPPORTED_TITLE_END')
            else:
                inner = self.text[start + len(title['start_tag']):end]
                if '<' in inner or '>' in inner:
                    self.issues.append('UNSUPPORTED_TITLE_MARKUP')
                element = {**title['element'], 'character_end': end + len(closing[0]),
                           'raw_element': self.text[start:end + len(closing[0])]}
                self.titles.append({'element': element, 'raw_inner': inner, 'text': unescape(inner)})
            self.active_title = None
        elif tag == 'head':
            if not self.head or self.active_title is not None:
                self.issues.append('AMBIGUOUS_HEAD_END')
            self.head, self.closed = False, True

    def finish(self):
        if self.heads != 1 or not self.closed or self.head or self.active_title is not None or self.ignored:
            self.issues.append('INCOMPLETE_OR_UNSUPPORTED_HEAD')


def _unknown(reason):
    return {'status': 'UNKNOWN', 'reason': reason, 'value': None, 'candidates': []}


def _signals(text, final_url):
    parser = HeadSignals(text)
    parser.feed(text)
    parser.close()
    parser.finish()
    title = {'status': 'UNKNOWN', 'reason': 'MISSING_EMPTY_OR_MULTIPLE_TITLE',
             'value': None, 'candidates': parser.titles}
    if len(parser.titles) == 1:
        value = parser.titles[0]['text']
        if value.strip() and len(value) <= 512 and not any(ord(c) < 32 and c not in '\r\n\t' for c in value):
            title.update(status='OBSERVED', reason='SINGLE_NONEMPTY_SOURCE_TITLE', value=value)
    canonical = {'status': 'UNKNOWN', 'reason': 'MISSING_EMPTY_MULTIPLE_OR_UNSUPPORTED_CANONICAL',
                 'value': None, 'candidates': parser.canonicals}
    if len(parser.canonicals) == 1:
        candidate = parser.canonicals[0]
        href = candidate['href']
        if candidate['attributes_unambiguous'] and href and len(href) <= 2048:
            try:
                if '\\' in href or any(ord(c) <= 32 or ord(c) >= 127 for c in href):
                    raise ValueError('UNSUPPORTED_HREF')
                resolved = urljoin(final_url, href)
                parts, source = urlsplit(resolved), urlsplit(final_url)
                normalized = canonical_url(resolved)
                if parts.query or parts.fragment or parts.hostname != source.hostname or parts.scheme != source.scheme:
                    raise ValueError('CANONICAL_OUTSIDE_BOUNDED_SITE')
                canonical.update(status='OBSERVED', reason='SINGLE_SAME_SITE_SOURCE_CANONICAL', value=normalized)
            except ValueError:
                canonical['reason'] = 'CANONICAL_NORMALIZATION_OR_SITE_BOUNDARY_UNSUPPORTED'
    description = {'status': 'UNKNOWN', 'reason': 'MISSING_EMPTY_OR_AMBIGUOUS_DESCRIPTION',
                   'value': None, 'candidates': parser.descriptions}
    if len(parser.descriptions) == 1:
        candidate = parser.descriptions[0]
        value = candidate['value']
        if candidate['attributes_unambiguous'] and value and value.strip() and len(value) <= 512:
            description.update(status='OBSERVED', reason='SINGLE_SOURCE_META_DESCRIPTION', value=value)
    if parser.issues:
        for signal in (title, canonical, description):
            signal.update(status='UNKNOWN', value=None, reason='HEAD_PARSE_AMBIGUOUS_OR_UNSUPPORTED')
    return {'title': title, 'canonical': canonical, 'description': description,
            'parse_issues': sorted(set(parser.issues)),
            'robots': _unknown('NO_RESOLVABLE_ROBOTS_BODY_EVIDENCE'),
            'sitemap': _unknown('NO_CAPTURED_RESOLVABLE_SITEMAP_EVIDENCE')}


def evaluate_seo01(pack, doc, rule, *, expected_pack_ref):
    rows = []

    def emit(result, reason, source=None, signals=None, citations=None):
        statement = {
            'PASS': 'This captured HOME-request static HTML has one nonempty title and one same-site canonical href; source tag presence only.',
            'UNKNOWN': 'Insufficient unambiguous retained static head evidence for the bounded title/canonical check.',
            'ACCESS_BLOCKED': 'Access to this captured source was blocked; no SEO defect is asserted.',
        }[result]
        row = _row(doc, rule, result, reason, source=source, citations=citations,
                   statement=statement, coverage_note=COVERAGE)
        row['seo_signals'] = signals or {key: _unknown(reason) for key in
                                        ('title', 'canonical', 'description', 'robots', 'sitemap')}
        del row['observation']['observation_id']
        row['observation']['observation_id'] = 'obs-' + document_hash(row)
        validate_contract('Observation', row['observation'])
        rows.append(row)

    for record in _records(doc):
        _, page, snapshot, _ = record
        if page['role'] != 'HOME':
            continue
        source = _metadata(record)
        if snapshot['status'] == 'ACCESS_BLOCKED':
            emit('ACCESS_BLOCKED', 'SOURCE_ACCESS_BLOCKED', source)
            continue
        evidence = next((e for e in doc['evidence'] if e['snapshot_ref'] == snapshot['snapshot_ref']
            and e['kind'] == 'HTTP_BODY' and e['status'] == 'OBSERVED' and e['blob_ref'] is not None), None)
        if evidence is None:
            emit('UNKNOWN', 'RETAINED_OBSERVED_HTTP_HTML_REQUIRED', source)
            continue
        raw = pack.resolve(evidence['evidence_ref'], expected_pack_ref=expected_pack_ref)['content']
        try:
            if raw is None or len(raw) > 131072:
                raise ValueError('HTML_BOUND')
            signals = _signals(raw.decode('utf-8-sig', errors='strict'), snapshot['final_url'])
        except (ValueError, UnicodeError, AssertionError):
            emit('UNKNOWN', 'UNSUPPORTED_OR_OVERSIZE_HEAD_SOURCE', source)
            continue
        citations = []
        for key in ('title', 'canonical', 'description'):
            for candidate in signals[key]['candidates']:
                citations.append({'evidence_ref': evidence['evidence_ref'], 'source_ref': evidence['source_ref'],
                    'snapshot_ref': snapshot['snapshot_ref'], 'locator': evidence['locator'],
                    'url': snapshot['url'], 'final_url': snapshot['final_url'],
                    'observed_at': snapshot['observed_at'], 'content_sha256': evidence['content_sha256'],
                    'fact_role': key.upper(), **candidate})
        complete = not signals['parse_issues'] and all(signals[key]['status'] == 'OBSERVED' for key in ('title', 'canonical'))
        emit('PASS' if complete else 'UNKNOWN', 'BOUNDED_TITLE_CANONICAL_PRESENT' if complete
             else 'PARTIAL_MISSING_AMBIGUOUS_OR_UNSUPPORTED_HEAD_SIGNALS', source, signals, citations)
    if not rows:
        emit('UNKNOWN', 'HTTP_HOME_SOURCE_NOT_CAPTURED')
    return rows
