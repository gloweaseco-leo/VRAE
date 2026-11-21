"""Partial self-declared context; no legal identity, authenticity or delivery judgment."""
from collections import Counter
from urllib.parse import urljoin

from .execution import _records, _row, _metadata
from .journey import _body_evidence
from .product_scope import navigation
from .retained_context import role, document, citation, closed_anchor, contact_targets
from .trust_facts import ABOUT_LABELS, NAME_LABELS
from .universal_static import ancestors, usable


def evaluate(pack, doc, rule):
    citations, names, intros, contacts, pages = [], set(), 0, 0, []
    context: list[dict] = []
    limited = False

    def add(kind, parser, node, ev, snap):
        nonlocal limited
        if len(context) >= 128:
            limited = True
            return
        citations.append(citation(parser, node, ev, snap))
        context.append({'kind': kind, 'citation_indexes': [len(citations)-1]})

    for record in _records(doc):
        snap = record[2]
        page_role = role(snap['url'])
        if page_role not in ('HOME', 'ABOUT', 'CONTACT'):
            continue
        meta = _metadata(record)
        page = {'source_page': meta, 'status': 'UNKNOWN', 'reason': 'SOURCE_NOT_OBSERVED'}
        pages.append(page)
        if snap['status'] != 'OBSERVED' or role(snap['final_url']) not in ('HOME', 'ABOUT', 'CONTACT'):
            continue
        ev = _body_evidence(doc, snap)
        if ev is None:
            continue
        raw = pack.resolve(ev['evidence_ref'], expected_pack_ref=pack.ref)['content']
        try:
            parser = document(raw, strip_bom=False)
            targets = contact_targets(raw, snap['final_url'])
        except (ValueError, UnicodeError):
            page['reason'] = 'BOUNDED_STATIC_PARSER_UNSUPPORTED'
            continue
        start = len(context)
        nodes = [n for n in parser.nodes if usable(n) and not navigation(n)]
        paragraph_count = 0
        for node in nodes:
            if node['tag'] == 'p' and len(node['text'].strip()) >= 40 and paragraph_count < 2:
                if page_role == 'ABOUT':
                    add('ABOUT_TEXT', parser, node, ev, snap)
                    paragraph_count += 1
                parent = node['parent']
                heading = next((c for c in parent['children'] if c['tag'] in ('h1', 'h2', 'h3')), None) if parent else None
                if (parent and parent['tag'] == 'section' and heading
                        and parent['children'][0] is heading
                        and not any(c['tag'] in ('h1', 'h2', 'h3', 'h4') and c is not heading
                                    and c['start'] < node['start'] for c in parent['children'])
                        and heading['text'].strip().casefold() in ABOUT_LABELS):
                    add('SELF_DESCRIPTION', parser, node, ev, snap)
                    intros += 1
                    if page_role != 'ABOUT':
                        paragraph_count += 1
            scope = next((a for a in ancestors(node) if 'itemscope' in a['attrs']), None)
            declared = (node['attrs'].get('itemprop') == 'name' and scope is not None
                and scope['attrs'].get('itemtype') in ('https://schema.org/Organization', 'http://schema.org/Organization'))
            if node['tag'] == 'tr':
                cells = [n for n in node['children'] if n['tag'] in ('th', 'td')]
                if (len(cells) == 2 and all(usable(n) for n in cells)
                        and cells[0]['text'].strip().casefold() in NAME_LABELS - {'brand name', '品牌名称'}):
                    node, declared = cells[1], True
            if declared:
                names.add(' '.join(node['text'].split()).casefold())
                add('DECLARED_NAME', parser, node, ev, snap)
        link_count = 0
        for node in parser.nodes:
            if not closed_anchor(node) or link_count >= 4:
                continue
            if urljoin(snap['final_url'], node['attrs'].get('href') or '') in targets:
                add('STATIC_CONTACT_LINK', parser, node, ev, snap)
                contacts += 1
                link_count += 1
        page.update(status='EXTRACTED' if len(context) > start else 'UNKNOWN',
                    reason='BOUNDED_SOURCE_CONTEXT_RETAINED' if len(context) > start else 'NO_SUPPORTED_STRUCTURED_TEXT')
    missing = [label for label, present in (
        ('UNAMBIGUOUS_DECLARED_ORGANIZATION_NAME', len(names) == 1),
        ('STRUCTURED_COMPANY_INTRODUCTION', intros > 0), ('STATIC_PUBLIC_CONTACT_LINK', contacts > 0)) if not present]
    if limited:
        missing.append('CONTEXT_BOUND_REACHED')
    result = 'PASS' if pages and not missing else 'UNKNOWN'
    row = _row(doc, rule, result, 'BOUNDED_SELF_DECLARED_PREREQUISITES_RETAINED' if result == 'PASS'
        else 'TRUST_PREREQUISITES_OR_CAPTURE_SCOPE_UNRESOLVED', citations=citations,
        statement='Retained self-declared organization, introduction and contact context only; legal identity and authenticity are unverified.',
        coverage_note='Captured HOME/ABOUT/CONTACT static regions only; unvisited candidates are not defects. No entity authentication, visibility or inquiry delivery verification.')
    row.update(context_facts=context, source_pages=pages, missing_prerequisites=missing,
               context_counts=dict(Counter(c['kind'] for c in context)))
    # Additional row metadata participates in the immutable execution ref.
    return [row]
