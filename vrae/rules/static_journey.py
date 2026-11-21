"""Versioned static edges over retained sources; never click or infer delivery."""
from urllib.parse import urljoin, urlsplit

from vrae.collection.discovery import page_role, labelled_contact_targets
from vrae.collection.policy import canonical_url
from .execution import _records, _metadata, _row
from .journey import ROLES, _body_evidence
from .universal_static import parse, usable, cite


def evaluate(pack, doc, rule, *, contextual=False):
    from .retained_context import role, contact_targets, closed_anchor
    classify = role if contextual else page_role
    source_roles, target_roles = ROLES[rule['rule_id']]
    records = _records(doc)
    targets = {r[2]['url']: r for r in records}
    rows = []
    coverage = ('One retained static anchor and the same-pack target response only. '
        'URL roles and contact labels do not verify page semantics, rendered visibility, '
        'SKU transfer, form submission, delivery or the whole website.')

    def add(result, reason, source=None, target=None, citations=None):
        statement = {
            'PASS': 'A retained static href reached a captured HTTP 200 target for this bounded path step.',
            'FAIL_WITH_EVIDENCE': 'A retained static href returned HTTP 404 or 410 at capture time.',
            'UNKNOWN': 'This bounded path step remains unverified; unvisited links are not website defects.',
            'ACCESS_BLOCKED': 'Access was blocked for this path step; no website defect is asserted.',
        }[result]
        rows.append(_row(doc, rule, result, reason, source=source, target=target,
                         citations=citations, statement=statement, coverage_note=coverage))

    for source in (r for r in records if (classify(r[2]['url']) if contextual else r[1]['role']) in source_roles):
        snapshot = source[2]
        meta = _metadata(source)
        if snapshot['status'] == 'ACCESS_BLOCKED':
            add('ACCESS_BLOCKED', 'SOURCE_ACCESS_BLOCKED', meta)
            continue
        evidence = _body_evidence(doc, snapshot)
        if evidence is None:
            add('UNKNOWN', 'SOURCE_RETAINED_HTML_REQUIRED', meta)
            continue
        if classify(snapshot['final_url']) not in source_roles:
            add('UNKNOWN', 'SOURCE_FINAL_ROLE_UNSUPPORTED', meta)
            continue
        raw = pack.resolve(evidence['evidence_ref'], expected_pack_ref=pack.ref)['content']
        try:
            if raw is None or len(raw) > 131072:
                raise ValueError('STATIC_LINK_BOUND')
            parser = parse(raw.removeprefix(b'\xef\xbb\xbf'))
            if any(n['tag'] == 'base' and 'href' in n['attrs'] for n in parser.nodes):
                raise ValueError('STATIC_BASE_SCOPE_UNSUPPORTED')
            anchors = [n for n in parser.nodes if (closed_anchor(n) if contextual else n['tag'] == 'a' and usable(n))]
            if len(anchors) > 128:
                raise ValueError('STATIC_LINK_BOUND')
        except (ValueError, UnicodeError):
            add('UNKNOWN', 'HTML_UNSUPPORTED_OR_AMBIGUOUS', meta)
            continue
        contacts = (contact_targets if contextual else labelled_contact_targets)(raw, snapshot['final_url'])
        seen, outside = set(), 0
        matched = False
        for node in anchors:
            href = node['attrs'].get('href') or ''
            if (not href or len(href) > 2048 or '\\' in href or '%' in href
                    or any(ord(c) <= 32 or ord(c) >= 127 for c in href)):
                continue
            try:
                url = canonical_url(urljoin(snapshot['final_url'], href))
            except ValueError:
                continue
            labelled = rule['rule_id'] == 'CTA-02' and url in contacts
            if (urlsplit(url).netloc != urlsplit(snapshot['url']).netloc
                    or urlsplit(url).scheme != urlsplit(snapshot['url']).scheme
                    or (classify(url) not in target_roles and not labelled) or url in seen):
                continue
            seen.add(url)
            target = targets.get(url)
            if target is None:
                outside += 1
                continue
            matched = True
            target_snap = target[2]
            citation = {**cite(parser, node)['element'], 'raw_href': href,
                **{k: evidence[k] for k in ('evidence_ref', 'source_ref', 'locator')},
                'snapshot_ref': snapshot['snapshot_ref'], 'url': snapshot['url'],
                'observed_at': snapshot['observed_at']}
            result, reason = 'UNKNOWN', 'TARGET_NOT_OBSERVED'
            if target_snap['status'] == 'ACCESS_BLOCKED':
                result, reason = 'ACCESS_BLOCKED', 'TARGET_ACCESS_BLOCKED'
            elif target[1]['http_status'] in (404, 410) and (target[1].get('error') or {}).get('code') == 'HTTP_ERROR':
                result, reason = 'FAIL_WITH_EVIDENCE', 'CAPTURED_BROKEN_HREF'
            elif target_snap['status'] == 'OBSERVED' and target[1]['http_status'] == 200:
                ev = _body_evidence(doc, target_snap)
                role_verified = (classify(target_snap['final_url']) in target_roles
                                 or labelled and target_snap['final_url'] == url)
                if ev is not None and role_verified:
                    pack.resolve(ev['evidence_ref'], expected_pack_ref=pack.ref)
                    citation['target_evidence_ref'] = ev['evidence_ref']
                    result, reason = 'PASS', 'CAPTURED_REACHABLE_HREF'
            add(result, reason, meta, _metadata(target), [citation])
        if outside:
            add('UNKNOWN', 'TARGETS_OUTSIDE_CAPTURE_SCOPE', meta)
            rows[-1]['unvisited_target_count'] = outside
        elif not matched:
            add('UNKNOWN', 'NO_SUPPORTED_STATIC_HREF', meta)
    return rows or [_row(doc, rule, 'UNKNOWN', 'SOURCE_ROLE_NOT_CAPTURED', coverage_note=coverage)]
