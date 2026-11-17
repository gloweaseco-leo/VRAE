"""Read-only BrowserObservation v1 projection, NOT an evaluator or authorization.

P0 intentionally cannot infer href, hit-testing, alt or geometry from the legacy
DOM producer. Only original retained bytes and original pack references are used.
The caller must retain its signed current-task authority throughout consumption.
"""
from dataclasses import dataclass
from datetime import datetime
import json
import re

from vrae.evidence import EvidenceError, EvidencePack

VERSION = 's2-ux-browser-projection-1.0.0'
RULES = ('INFO-03', 'CTA-01', 'CTA-03', 'TECH-02')
DIMENSIONS = ('DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL')


@dataclass(frozen=True)
class BrowserPins:
    """Independently held server context, never supplied by the browser form.

    observed_after/before bound the source observation time to this actual task;
    source_refs is the exact selected set, not every source in a shared pack.
    These consistency pins do not grant access or prove signed provenance.
    """
    tenant_id: str
    run_id: str
    policy_id: str
    policy_version: int
    pack_ref: str
    source_refs: tuple[str, ...]
    observed_after: datetime
    observed_before: datetime


@dataclass(frozen=True)
class BrowserProjection:
    payload: bytes

    @property
    def document(self):
        return json.loads(self.payload)


def _deny():
    raise EvidenceError('S2_UX_SOURCE_BINDING_INVALID')


def _time(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.utcoffset() is None:
            _deny()
        return parsed
    except (ValueError, TypeError, AttributeError):
        _deny()


def _dom(raw, url):
    """Narrow to the actual v1 producer; unknown extensions confer no capability."""
    try:
        doc = json.loads(raw)
        if (set(doc) != {'title', 'url', 'elements'} or doc['url'] != url
                or not isinstance(doc['title'], str) or len(doc['title']) > 256
                or not isinstance(doc['elements'], list) or len(doc['elements']) > 128):
            return None
        for e in doc['elements']:
            if (not isinstance(e, dict) or set(e) != {'tag', 'visible', 'text'}
                    or e['tag'] not in ('H1', 'H2', 'A', 'BUTTON', 'INPUT', 'IMG')
                    or type(e['visible']) is not bool or not isinstance(e['text'], str)
                    or len(e['text']) > 160):
                return None
        return doc
    except (ValueError, TypeError, UnicodeError):
        return None


def project_browser(pack: EvidencePack, *, held: BrowserPins) -> BrowserProjection:
    """Project only independently selected browser sources; no rule PASS/FAIL.

    Missing fields produce UNKNOWN, not an assertion of a website defect.
    HUMAN_REVIEW_REQUIRED candidates are quotations, not English quality labels.
    Counts describe selected observations (max 3 URLs x 2 viewports per source),
    never whole-site coverage or the C1 scope_manifest denominator.
    """
    if type(pack) is not EvidencePack or type(held) is not BrowserPins:
        _deny()
    if (type(held.source_refs) is not tuple or not held.source_refs
            or len(set(held.source_refs)) != len(held.source_refs)
            or type(held.policy_version) is not int
            or not isinstance(held.observed_after, datetime)
            or not isinstance(held.observed_before, datetime)
            or held.observed_after.utcoffset() is None
            or held.observed_before.utcoffset() is None
            or held.observed_after > held.observed_before):
        _deny()
    pack.verify(expected_ref=held.pack_ref)
    doc = pack.document
    if any(doc[k] != getattr(held, k) for k in
           ('tenant_id', 'run_id', 'policy_id', 'policy_version')):
        _deny()
    sources = {s['source_ref']: s for s in doc['sources']}
    if any(ref not in sources or sources[ref]['kind'] != 'BrowserObservation'
           for ref in held.source_refs):
        _deny()
    rows = []
    for ref in sorted(held.source_refs):
        source = sources[ref]
        manifest = source['document']
        for url in manifest['approved_urls']:
            for name in ('desktop', 'mobile'):
                item = next((o for o in manifest['observations']
                             if o['url'] == url and o['viewport']['name'] == name), None)
                row = {'source_ref': ref, 'url': url, 'viewport': name,
                       'snapshot_ref': None, 'observed_at': None, 'evidence_refs': [],
                       'candidates': [], 'rules': [], 'status': 'NOT_VISITED',
                       'dom_usable': False}
                dom = None
                if item is not None:
                    at = _time(item['observed_at'])
                    if not held.observed_after <= at <= held.observed_before:
                        _deny()
                    index = manifest['observations'].index(item)
                    snap = next(s for s in doc['snapshots'] if s['source_ref'] == ref
                                and s['locator'] == f'/observations/{index}')
                    row.update(snapshot_ref=snap['snapshot_ref'], observed_at=item['observed_at'],
                               status=item['status'])
                    evs = [e for e in doc['evidence'] if e['snapshot_ref'] == snap['snapshot_ref']
                           and e['status'] == 'OBSERVED']
                    if item['status'] == 'OBSERVED':
                        ev = next(e for e in evs if e['kind'] == 'BROWSER_DOM')
                        dom = _dom(pack.objects[ev['blob_ref']], url)
                        if dom is not None:
                            row['dom_usable'] = True
                            row['evidence_refs'] = [e['evidence_ref'] for e in evs]
                            for n, element in enumerate(dom['elements']):
                                # Only quote what the bounded producer retained. Width/height
                                # >0 is NOT visibility, clickability or an accessible name.
                                kinds = []
                                if re.search(r'[\u3400-\u9fff]|\blorem ipsum\b', element['text'], re.I):
                                    kinds.append('LANGUAGE_TEXT_REVIEW')
                                if element['tag'] in ('A', 'BUTTON') and re.search(
                                        r'contact|quote|rfq|inquir|联系|询价', element['text'], re.I):
                                    kinds.append('CTA_TEXT_ONLY')
                                if element['tag'] in ('H1', 'H2', 'IMG'):
                                    kinds.append('HEADING_OR_IMAGE_TAG_ONLY')
                                for kind in kinds:
                                    row['candidates'].append({'kind': kind,
                                        'review': 'HUMAN_REVIEW_REQUIRED', 'text': element['text'],
                                        'tag': element['tag'], 'box_nonzero': element['visible'],
                                        'evidence_ref': ev['evidence_ref'],
                                        'json_pointer': f'/elements/{n}'})
                for rule, reason in zip(RULES, (
                        'BOUNDED_TEXT_NOT_LANGUAGE_QUALITY', 'HREF_AND_HIT_TEST_NOT_RETAINED',
                        'GEOMETRY_AND_OCCLUSION_NOT_RETAINED', 'ALT_SRC_AND_IMAGE_LOAD_NOT_RETAINED')):
                    status = 'ACCESS_BLOCKED' if row['status'] == 'ACCESS_BLOCKED' else 'UNKNOWN'
                    if row['status'] == 'NOT_VISITED':
                        reason = 'VIEWPORT_NOT_VISITED'
                    elif row['status'] != 'OBSERVED':
                        reason = 'BROWSER_OBSERVATION_INCOMPLETE'
                    elif dom is None:
                        reason = 'DOM_PRODUCER_UNSUPPORTED_OR_AMBIGUOUS'
                    row['rules'].append({'rule_id': rule, 'result': status, 'reason': reason})
                rows.append(row)
    result = {'projection_version': VERSION, 'pack_ref': held.pack_ref,
              'tenant_id': held.tenant_id, 'run_id': held.run_id,
              'rows': rows, 'coverage': {'unit': 'SELECTED_URL_VIEWPORT', 'selected': len(rows),
                  'observed': sum(r['status'] == 'OBSERVED' for r in rows),
                  'usable_dom': sum(r['dom_usable'] for r in rows),
                  'not_visited': sum(r['status'] == 'NOT_VISITED' for r in rows)},
              'limitations': ['CONSISTENCY_NOT_SIGNED_PROVENANCE', 'NOT_RULE_EXECUTION',
                  'NOT_WHOLE_SITE_COVERAGE', 'CURRENT_TASK_AUTHORITY_REQUIRED',
                  'NO_RFQ_SUBMISSION_OR_DELIVERY', 'NO_ACCESSIBILITY_OR_RANKING_CLAIM']}
    return BrowserProjection(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                       separators=(',', ':'), allow_nan=False).encode())
