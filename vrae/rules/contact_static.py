"""Positive static contact href presence; never rendered visibility or delivery."""
from urllib.parse import urljoin, urlsplit
from vrae.collection.discovery import representative_role, labelled_contact_targets

from .execution import _records, _metadata, _row
from .universal_static import parse, usable, cite


def evaluate(pack, doc, rule, *, labelled=False, contextual=False):
    from .retained_context import role, contact_targets, closed_anchor
    classify = role if contextual else representative_role
    rows = []
    for record in _records(doc):
        snapshot = record[2]
        if snapshot['status'] != 'OBSERVED':
            continue
        evidence = next((e for e in doc['evidence'] if e['snapshot_ref'] == snapshot['snapshot_ref']
            and e['kind'] == 'HTTP_BODY' and e['status'] == 'OBSERVED' and e['blob_ref']), None)
        if evidence is None:
            continue
        raw = pack.resolve(evidence['evidence_ref'], expected_pack_ref=pack.ref)['content']
        try:
            parser = parse(raw)
        except (ValueError, UnicodeError):
            continue
        if labelled and any(n['tag'] == 'base' and 'href' in n['attrs'] for n in parser.nodes):
            continue
        citations = []
        labelled_targets = (contact_targets if contextual else labelled_contact_targets)(raw, snapshot['final_url']) if labelled else set()
        for node in parser.nodes:
            if not (closed_anchor(node) if contextual else node['tag'] == 'a' and usable(node)):
                continue
            href = node['attrs'].get('href') or ''
            if not href or len(href) > 2048 or any(ord(c) <= 32 for c in href) or '\\' in href:
                continue
            target = urlsplit(urljoin(snapshot['final_url'], href))
            if (target.scheme != 'https' or target.netloc != urlsplit(snapshot['final_url']).netloc
                    or target.query or target.fragment
                    or (classify(target.geturl()) != 'CONTACT'
                        and target.geturl() not in labelled_targets)):
                continue
            citations.append({**cite(parser, node), **{k: evidence[k] for k in (
                'evidence_ref', 'source_ref', 'snapshot_ref', 'locator', 'content_sha256')},
                'url': snapshot['url'], 'observed_at': snapshot['observed_at'], 'raw_href': href})
            if len(citations) == 4:
                break
        if citations:
            row = _row(doc, rule, 'UNKNOWN', 'STATIC_HREF_OBSERVED_VISIBILITY_UNVERIFIED',
                source=_metadata(record), citations=citations,
                statement='A labeled same-site contact or inquiry href was retained in this static source; rendered visibility, target availability and successful inquiry are unverified.',
                coverage_note='Static source href presence only. No clicks, form submissions, deliverability, visibility or buyer conversion verification.')
            row['static_href_presence'] = 'OBSERVED'
            row['rendered_visibility'] = 'UNKNOWN'
            rows.append(row)
    return rows or [_row(doc, rule, 'UNKNOWN', 'NO_SUPPORTED_STATIC_CONTACT_HREF',
        coverage_note='No supported href established in bounded retained sources; not proof that the website lacks contact options.')]
