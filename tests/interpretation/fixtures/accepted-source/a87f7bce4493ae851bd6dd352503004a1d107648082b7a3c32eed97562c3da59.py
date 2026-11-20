"""Offline static source text facts only. No Observation or enabled INFO-01 rule."""
from html.parser import HTMLParser
import json
import re

from vrae.collection.discovery import page_role
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError, EvidencePack

VERSION = 'ra2b2-product-facts-1.0.0'
VOID = {'meta', 'link', 'br', 'hr', 'img', 'input', 'wbr', 'area', 'col', 'embed',
        'param', 'source', 'track'}


class _Static(HTMLParser):
    """Strict balanced subset; plain-text h1 and table row th/td cells only."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[dict] = []
        self.roots: list[dict] = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > 2048 or len(self.stack) > 32:
            raise ValueError('HTML_BOUND')
        # Scripts, alternative content and controls prevent unambiguous static scope.
        if tag in {'script', 'template', 'noscript', 'select', 'form', 'iframe', 'base'}:
            raise ValueError('DYNAMIC_OR_ALTERNATIVE_SCOPE')
        parent = self.stack[-1]['tag'] if self.stack else None
        if ((tag == 'tr' and parent not in {'table', 'tbody', 'thead', 'tfoot'})
                or (tag in {'td', 'th'} and parent != 'tr')
                or (tag in {'tbody', 'thead', 'tfoot'} and parent != 'table')
                or (tag == 'table' and any(n['tag'] == 'table' for n in self.stack))):
            raise ValueError('UNSUPPORTED_TABLE_STRUCTURE')
        children = self.stack[-1]['children'] if self.stack else self.roots
        node = {'tag': tag, 'children': [], 'text': '', 'line': self.getpos()[0],
                'column': self.getpos()[1], 'ordinal': len(children) + 1,
                'start_tag': self.get_starttag_text()}
        children.append(node)
        if any(k in {'hidden', 'inert', 'style', 'aria-hidden'} for k, _ in attrs):
            raise ValueError('PRESENTATION_UNRESOLVED')
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1]['tag'] != tag:
            raise ValueError('UNBALANCED_HTML')
        self.stack.pop()

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]['text'] += data


def _parse(raw):
    if len(raw) > 131072:
        raise ValueError('HTML_BOUND')
    parser = _Static()
    parser.feed(raw.decode('utf-8', errors='strict'))
    parser.close()
    if parser.stack:
        raise ValueError('UNCLOSED_HTML')
    nodes = []

    def walk(children, path):
        for node in children:
            node['path'] = path + '/' + node['tag'] + '[' + str(node['ordinal']) + ']'
            nodes.append(node)
            walk(node['children'], node['path'])

    walk(parser.roots, '')
    names = [n for n in nodes if n['tag'] == 'h1']
    rows = [n for n in nodes if n['tag'] == 'tr']
    if len(rows) > 128:
        raise ValueError('FIELD_BOUND')
    if len(names) != 1 or names[0]['children'] or not names[0]['text'].strip():
        raise ValueError('NAME_AMBIGUOUS_OR_MISSING')
    fields = []
    for row in rows:
        cells = row['children']
        if (len(cells) != 2 or [c['tag'] for c in cells] != ['th', 'td']
                or any(c['children'] for c in cells) or '/table[' not in row['path']):
            raise ValueError('UNSUPPORTED_TABLE_STRUCTURE')
        fields.append((cells[0], cells[1]))
    return names[0], fields


def extract(pack: EvidencePack, *, expected_pack_ref: str) -> dict:
    """Caller must obtain its trusted pin separately; pack content is not authorization."""
    if not isinstance(expected_pack_ref, str) or not re.fullmatch(r'ep-[0-9a-f]{64}', expected_pack_ref):
        raise EvidenceError('PRODUCT_FACTS_INTEGRITY')
    pack.verify(expected_ref=expected_pack_ref)
    doc = pack.document
    pages = []
    for snap in doc['snapshots']:
        if snap['capture_mode'] != 'HTTP' or page_role(snap['url']) != 'PRODUCT':
            continue
        row = {'snapshot': snap, 'status': 'UNKNOWN', 'reason': 'RAW_HTML_REQUIRED',
               'name': None, 'fields': []}
        pages.append(row)
        if snap['status'] == 'ACCESS_BLOCKED':
            row.update(status='ACCESS_BLOCKED', reason='CAPTURE_ACCESS_BLOCKED')
            continue
        if snap['status'] != 'OBSERVED' or not snap['final_url'] or page_role(snap['final_url']) != 'PRODUCT':
            continue
        ev = next((e for e in doc['evidence'] if e['snapshot_ref'] == snap['snapshot_ref']
                   and e['kind'] == 'HTTP_BODY' and e['status'] == 'OBSERVED' and e['blob_ref']), None)
        if ev is None:
            continue
        raw = pack.resolve(ev['evidence_ref'], expected_pack_ref=expected_pack_ref)['content']
        try:
            name, fields = _parse(raw)
        except (ValueError, UnicodeError):
            row['reason'] = 'HTML_UNSUPPORTED_OR_AMBIGUOUS'
            continue

        def cite(node):
            return {'text': node['text'], 'element': {k: node[k] for k in
                    ('path', 'line', 'column', 'start_tag')},
                    **{k: ev[k] for k in ('evidence_ref', 'source_ref', 'snapshot_ref',
                                         'locator', 'content_sha256')},
                    'url': snap['url'], 'final_url': snap['final_url'],
                    'observed_at': snap['observed_at']}

        row['name'] = cite(name)
        labels = [label['text'].strip().casefold() for label, _ in fields]
        for label, value in fields:
            key = label['text'].strip().casefold()
            reason = ('EMPTY_LABEL' if not key else 'DUPLICATE_LABEL' if labels.count(key) > 1
                      else 'EMPTY_STATIC_VALUE' if not value['text'].strip() else 'STATIC_TEXT_RETAINED')
            row['fields'].append({'label': cite(label), 'value': cite(value),
                                  'status': 'EXTRACTED' if reason == 'STATIC_TEXT_RETAINED' else 'UNKNOWN',
                                  'reason': reason})
        row['status'] = ('EXTRACTED' if fields and all(f['status'] == 'EXTRACTED'
                         for f in row['fields']) else 'UNKNOWN')
        row['reason'] = 'STATIC_TEXT_RETAINED' if row['status'] == 'EXTRACTED' else 'FIELDS_MISSING_OR_AMBIGUOUS'
    output = {'extractor_version': VERSION, 'expected_pack_ref': expected_pack_ref,
              'tenant_id': doc['tenant_id'], 'run_id': doc['run_id'], 'pages': pages,
              'coverage': doc['coverage'], 'info01_enabled': False, 'info01_result': 'UNKNOWN',
              'limitations': ['URL_ROLE_HEURISTIC_ONLY', 'SOURCE_TEXT_NOT_RENDERED_VISIBILITY',
                              'NO_SKU_AUTHENTICITY_FIT_COMPLETENESS_OR_BUSINESS_CLAIM',
                              'NO_SAFE_INFO01_FAIL_WITHOUT_APPLICABILITY_AND_DYNAMIC_SCOPE',
                              'OFFLINE_SYNTHETIC_ONLY_NO_CURRENT_AUTHORIZATION']}
    output['facts_ref'] = 'pf-' + document_hash(output)
    return output


def verify_facts(output: dict, pack: EvidencePack, *, expected_pack_ref: str) -> None:
    """Replay the complete result, including text and positions, against the trusted pack."""
    try:
        if json.dumps(output, sort_keys=True, allow_nan=False) != json.dumps(
                extract(pack, expected_pack_ref=expected_pack_ref), sort_keys=True):
            raise ValueError('MISMATCH')
    except Exception as exc:
        raise EvidenceError('PRODUCT_FACTS_INTEGRITY') from exc
