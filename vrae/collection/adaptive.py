"""Bounded source-link investigation hints, never a diagnosis or generated URL."""
from urllib.parse import urljoin, urlsplit

from vrae.rules.universal_static import ancestors, landmark, parse, product, usable
from .discovery import representative_role
from .manifest import sha256

POLICY = 'SOURCE_LINK_GAPS_V1'
PURPOSES = ('TECHNICAL_MATERIAL', 'APPLICATION_CONTEXT', 'PROOF_CONTEXT')
LABELS = (
    {'technical specifications', 'technical data', 'datasheet', 'data sheet', 'specifications'},
    {'application', 'applications', 'application guide', 'applications and solutions'},
    {'certificate', 'certificates', 'certification', 'certifications', 'quality certifications', 'case study'},
)
REASONS = ('NO_STRUCTURED_PRODUCT_FIELDS_RECORDED', 'NO_APPLICATION_FIELD_RECORDED',
           'PROOF_CONTEXT_NOT_YET_FETCHED')


def proposals(raw, source_url, source_index, inventory_urls):
    """Only explicit main-content HTML links intersected with checked inventory."""
    if len(raw) > 131072:
        return []
    role = representative_role(source_url)
    if role not in ('PRODUCT', 'ABOUT'):
        return []
    try:
        parser = parse(raw)
        if any(n['tag'] == 'base' and 'href' in n['attrs'] for n in parser.nodes):
            return []
        needed = {2} if role == 'ABOUT' else set()
        if role == 'PRODUCT':
            _, _, fields, _ = product(raw, multi_column=True)
            known = [(a, b) for a, b in fields if b['text'].strip().casefold()
                     not in ('', '-', '--', 'n/a', 'na', 'tbd', 'unknown')]
            if not known:
                needed.add(0)
            if not any(a['text'].strip().rstrip(':').casefold() in
                       ('application', 'applications', 'usage', 'use', 'intended use') for a, _ in known):
                needed.add(1)
        result = []
        for node in parser.nodes:
            if not usable(node) or node['tag'] != 'a' or node['end'] is None:
                continue
            parents = list(ancestors(node))
            if (not any(landmark(a) for a in parents) or any(a['tag'] in
                    ('nav', 'header', 'footer', 'aside') for a in parents)):
                continue
            label = ' '.join(node['text'].split()).casefold()
            purpose = next((i for i in sorted(needed) if label in LABELS[i]), None)
            href = node['attrs'].get('href')
            if purpose is None or not href or len(href) > 2048 or any(
                    ord(c) <= 32 or ord(c) >= 127 for c in href) or '%' in href or '\\' in href:
                continue
            target = urlsplit(urljoin(source_url, href))
            if (target.scheme != 'https' or target.netloc != urlsplit(source_url).netloc
                    or target.username or target.password or target.query or target.fragment
                    or target.geturl() not in inventory_urls):
                continue
            result.append({'source_page_index': source_index, 'target_url': target.geturl(),
                'purpose': PURPOSES[purpose], 'trigger': REASONS[purpose],
                'source_sha256': sha256(raw),
                'byte_start': len(parser.text[:node['start']].encode('utf-8')),
                'byte_end': len(parser.text[:node['end']].encode('utf-8'))})
            if len(result) == 16:
                break
        return result
    except (ValueError, UnicodeError):
        # Unsupported parsing is not evidence of missing information.
        return []


class Investigation:
    def __init__(self):
        self.pending: list[dict] = []
        self.decisions: list[dict] = []
        self.pending_decision: dict | None = None
        self.last_gate = 'NO_ELIGIBLE_SOURCE_LINK'

    def observe(self, raw, url, index, inventory_urls):
        self.pending.extend(proposals(raw, url, index, inventory_urls)[:16-len(self.pending)])

    def choose(self, items, baseline, attempted, covered, budget, page_index, contact_targets):
        self.pending_decision = None
        if len(self.decisions) >= 2:
            self.last_gate = 'ADAPTIVE_LIMIT_REACHED'
            return None
        role = ('CONTACT' if baseline['url'] in contact_targets else representative_role(baseline['url']))
        if role in ('HOME', 'CATALOG', 'CATEGORY', 'PRODUCT', 'CONTACT', 'ABOUT') and role not in covered:
            self.last_gate = 'BASELINE_COVERAGE_FIRST'
            return None
        if budget.deadline-budget.clock() < budget.limits.request_seconds+budget.interval+.25:
            self.last_gate = 'TIME_BUDGET_RESERVED'
            return None
        selected = {d['purpose'] for d in self.decisions}
        eligible = [p for p in self.pending if p['target_url'] not in attempted and p['purpose'] not in selected]
        eligible.sort(key=lambda p: (PURPOSES.index(p['purpose']), p['source_page_index'], p['target_url']))
        by_url = {i['url']: i for i in items}
        for proposal in eligible:
            if proposal['target_url'] in by_url:
                self.pending_decision = {**proposal, 'target_page_index': page_index}
                self.last_gate = 'SOURCE_LINK_SELECTED'
                return by_url[proposal['target_url']]
        self.last_gate = 'NO_ELIGIBLE_SOURCE_LINK'
        return None

    def record(self):
        if self.pending_decision is None:
            raise ValueError('ADAPTIVE_SELECTION_REQUIRED')
        self.decisions.append(self.pending_decision)
        self.pending_decision = None

    def document(self, *, full, stopped):
        return {'policy': POLICY, 'max_supplemental_pages': 2, 'decisions': self.decisions,
            'stop_reason': 'SAFETY_OR_BUDGET_STOP' if stopped else
                'PAGE_LIMIT_REACHED' if full else self.last_gate,
            'whole_site_coverage_known': False, 'unknown_is_defect': False}


def verify(manifest, objects):
    """Historical source replay only; current authority stays in the Collector."""
    from .errors import CollectionError
    rows = manifest['pages']
    seen, purposes, targets = set(), set(), set()
    for decision in manifest['adaptive_investigation']['decisions']:
        si, ti = decision['source_page_index'], decision['target_page_index']
        if not 0 <= si < ti < len(rows) or ti in seen or si in seen:
            raise CollectionError('EVIDENCE_INTEGRITY')
        source, target = rows[si]['snapshot'], rows[ti]['snapshot']
        raw = objects.get(source['private_object_ref'])
        if (source['status'] != 'FETCHED' or raw is None or decision['target_url'] != target['url']
                or decision['purpose'] in purposes or target['url'] in targets
                or any(p['snapshot']['url'] == target['url'] or p['snapshot']['final_url'] == target['url'] for p in rows[:ti])):
            raise CollectionError('EVIDENCE_INTEGRITY')
        proposal = {k:v for k,v in decision.items() if k != 'target_page_index'}
        candidates = proposals(raw, source['final_url'], si,
            {decision['target_url']} & {i['url'] for i in manifest['inventory']})
        if proposal not in candidates:
            raise CollectionError('EVIDENCE_INTEGRITY')
        seen.add(ti)
        purposes.add(decision['purpose'])
        targets.add(target['url'])
