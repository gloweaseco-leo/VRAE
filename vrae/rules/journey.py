"""Bounded static category/product/contact edges, composed only from proven steps."""
from urllib.parse import urljoin, urlsplit

from vrae.collection.discovery import page_role
from vrae.collection.manifest import document_hash
from vrae.collection.policy import canonical_url
from vrae.domain.evidence import classify_rule
from .execution import Navigation, _metadata, _records, _row

ROLES = {'DISC-02': (('CATEGORY', 'CATALOG'), ('PRODUCT',)),
         'CTA-02': (('PRODUCT',), ('CONTACT',))}


class PageLinks(Navigation):
    """Reuse Navigation's bounds/ambiguity handling for anchors outside nav too."""
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            nav = self.nav
            self.nav = 1
            super().handle_starttag(tag, attrs)
            self.nav = nav
        else:
            super().handle_starttag(tag, attrs)


def _body_evidence(doc, snapshot):
    return next((e for e in doc['evidence'] if e['snapshot_ref'] == snapshot['snapshot_ref']
        and e['kind'] == 'HTTP_BODY' and e['status'] == 'OBSERVED' and e['blob_ref'] is not None), None)


def evaluate_links(pack, doc, rule):
    source_roles, target_roles = ROLES[rule['rule_id']]
    records = _records(doc)
    sources = [record for record in records if record[1]['role'] in source_roles]
    rows = []

    def add(result, reason, source=None, target=None, citations=None):
        statement = {
            'PASS': 'This captured static href reached HTTP 200 at the required target path role.',
            'FAIL_WITH_EVIDENCE': 'This captured static href returned HTTP 404 or 410 at capture time.',
            'UNKNOWN': 'Insufficient evidence for this bounded static path step.',
            'ACCESS_BLOCKED': 'Access was blocked for this path step; no website defect is asserted.',
        }[result]
        rows.append(_row(doc, rule, result, reason, source=source, target=target,
            citations=citations, statement=statement,
            coverage_note='One captured static href and its target response only; path roles are URL heuristics, not semantic identity. No visibility, form submission/delivery, SKU transfer, conversion or whole-site claim.'))

    for source in sources:
        _, _, snapshot, _ = source
        source_meta = _metadata(source)
        if snapshot['status'] == 'ACCESS_BLOCKED':
            add('ACCESS_BLOCKED', 'SOURCE_ACCESS_BLOCKED', source_meta)
            continue
        evidence = _body_evidence(doc, snapshot)
        if evidence is None:
            add('UNKNOWN', 'SOURCE_RETAINED_HTML_REQUIRED', source_meta)
            continue
        if page_role(snapshot['final_url']) not in source_roles:
            add('UNKNOWN', 'SOURCE_FINAL_ROLE_UNSUPPORTED', source_meta)
            continue
        parser = PageLinks()
        raw = pack.resolve(evidence['evidence_ref'], expected_pack_ref=pack.ref)['content']
        try:
            if raw is None or len(raw) > 131072:
                raise ValueError('HTML_BOUND')
            parser.feed(raw.decode('utf-8-sig', errors='strict'))
            parser.close()
            if parser.ambiguous:
                raise ValueError('AMBIGUOUS_HTML')
        except (ValueError, UnicodeError):
            add('UNKNOWN', 'HTML_UNSUPPORTED_OR_AMBIGUOUS', source_meta)
            continue
        candidates = []
        for anchor in parser.anchors:
            href = anchor['raw_href']
            if len(href) > 2048 or any(ord(c) <= 32 or ord(c) >= 127 for c in href):
                continue
            try:
                url = canonical_url(urljoin(snapshot['final_url'], href))
            except ValueError:
                continue
            if (urlsplit(url).hostname != urlsplit(snapshot['url']).hostname
                    or urlsplit(snapshot['url']).scheme == 'https' and urlsplit(url).scheme != 'https'
                    or page_role(url) not in target_roles):
                continue
            candidates.append((anchor, url))
        if not candidates:
            add('UNKNOWN', 'NO_SUPPORTED_STATIC_HREF', source_meta)
        for anchor, url in candidates:
            target = next((record for record in records if record[2]['url'] == url), None)
            citation = {'evidence_ref': evidence['evidence_ref'], 'source_ref': evidence['source_ref'],
                'locator': evidence['locator'], 'snapshot_ref': snapshot['snapshot_ref'],
                'url': snapshot['url'], 'observed_at': snapshot['observed_at'], **anchor}
            result, reason = 'UNKNOWN', 'TARGET_NOT_OBSERVED'
            if target is not None:
                _, target_page, target_snap, _ = target
                if target_snap['status'] == 'ACCESS_BLOCKED':
                    result, reason = 'ACCESS_BLOCKED', 'TARGET_ACCESS_BLOCKED'
                elif (target_page['http_status'] in (404, 410) and target_page['error']
                      and target_page['error']['code'] == 'HTTP_ERROR'):
                    result = classify_rule(False, [evidence['evidence_ref']])
                    reason = 'CAPTURED_BROKEN_HREF'
                elif target_snap['status'] == 'OBSERVED' and target_page['http_status'] == 200:
                    target_ev = _body_evidence(doc, target_snap)
                    if target_ev is not None and page_role(target_snap['final_url']) in target_roles:
                        pack.resolve(target_ev['evidence_ref'], expected_pack_ref=pack.ref)
                        citation['target_evidence_ref'] = target_ev['evidence_ref']
                        result, reason = classify_rule(True, [evidence['evidence_ref']]), 'CAPTURED_REACHABLE_HREF'
            add(result, reason, source_meta, _metadata(target) if target else None, [citation])
    if not sources:
        add('UNKNOWN', 'SOURCE_ROLE_NOT_CAPTURED')
    return rows


def compose_paths(executions):
    """Join only identical captured snapshots, stopping at failed/unknown/blocked edges."""
    stages = [next(e for e in executions if e['rule_id'] == rule)['observations']
              for rule in ('DISC-01', 'DISC-02', 'CTA-02')]
    paths: list[dict] = []
    truncated = False

    def walk(row, index, steps):
        nonlocal truncated
        if len(paths) >= 256:
            truncated = True
            return
        observation = row['observation']
        source = row.get('source_page', row.get('homepage'))
        if source is None:
            return
        step = {'rule_id': observation['rule_id'], 'rule_version': observation['rule_version'],
            'observation_id': observation['observation_id'], 'result': observation['result'],
            'source_page': source, 'target_response': row['target_response'],
            'citations': row['citations']}
        steps = [*steps, step]
        target = row['target_response']
        if observation['result'] == 'PASS' and target is not None and index < 2:
            next_rows = [candidate for candidate in stages[index + 1]
                if candidate.get('source_page', {}).get('snapshot_ref') == target['snapshot_ref']]
            if next_rows:
                for candidate in next_rows:
                    walk(candidate, index + 1, steps)
                return
        path = {'steps': steps, 'complete': index == 2 and observation['result'] == 'PASS',
                'terminal_result': observation['result']}
        path['journey_ref'] = 'journey-' + document_hash(path)
        paths.append(path)

    for row in stages[0]:
        walk(row, 0, [])
    return paths, {'max_paths': 256, 'truncated': truncated,
                   'scope': 'Bounded captured paths only; no whole-site coverage assertion.'}
