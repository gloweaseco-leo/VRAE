"""Static navigation reachability only, replayed against a caller-held pack pin."""
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit

from vrae.collection.discovery import page_role
from vrae.collection.manifest import document_hash
from vrae.collection.policy import canonical_url
from vrae.domain.contracts import validate_contract
from vrae.domain.evidence import classify_rule
from vrae.evidence import EvidenceError, EvidencePack
from .readiness import catalog, GAPS

VERSION = 'ra2b0-1.0.0'
JOURNEY_VERSION = 'ra2b1-1.0.0'
INFO_VERSION = 'ra2b3-1.0.0'


class Navigation(HTMLParser):
    """Read only anchors in explicit static nav markup; no rendered/visibility claim."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nav = 0
        self.ignored = 0
        self.anchors: list[dict] = []
        self.ambiguous = False

    def handle_starttag(self, tag, attrs):
        if tag == 'base':
            self.ambiguous = True
        if tag in ('template', 'noscript', 'script', 'style'):
            self.ignored += 1
        if tag == 'nav':
            self.nav += 1
        if tag == 'a' and self.nav and not self.ignored:
            hrefs = [v for k, v in attrs if k == 'href']
            if len(hrefs) != 1 or hrefs[0] is None or len(self.anchors) >= 128:
                self.ambiguous = True
            elif not any(k in ('hidden', 'inert') for k, _ in attrs):
                line, column = self.getpos()
                self.anchors.append({'raw_href': hrefs[0], 'line': line, 'column': column,
                                     'anchor_index': len(self.anchors)})

    def handle_endtag(self, tag):
        if tag == 'nav':
            self.nav = max(0, self.nav - 1)
        if tag in ('template', 'noscript', 'script', 'style'):
            self.ignored = max(0, self.ignored - 1)


def _records(doc):
    records = []
    for source in doc['sources']:
        if source['kind'] != 'CaptureManifest':
            continue
        for index, page in enumerate(source['document']['pages']):
            locator = f'/pages/{index}'
            snap = next(s for s in doc['snapshots']
                if s['source_ref'] == source['source_ref'] and s['locator'] == locator + '/snapshot')
            records.append((source, page, snap, locator))
    return records


def _metadata(record):
    source, page, snap, locator = record
    return {'source_ref': source['source_ref'], 'locator': locator,
        'snapshot_ref': snap['snapshot_ref'], 'url': snap['url'],
        'final_url': snap['final_url'], 'observed_at': snap['observed_at'],
        'http_status': page['http_status'], 'redirect_trace': page['redirect_trace'],
        'error': page['error']}


def _row(doc, rule, result, reason, *, citations=None, home=None, target=None,
         source=None, statement=None, coverage_note=None):
    citations = citations or []
    objective = result in ('PASS', 'FAIL_WITH_EVIDENCE')
    ids = sorted({ref for c in citations for ref in
                  (c['evidence_ref'], c.get('target_evidence_ref')) if ref}) if objective else []
    statement = statement or {
        'PASS': 'This captured static homepage nav href reached a captured HTTP 200 category-path page.',
        'FAIL_WITH_EVIDENCE': 'This captured static homepage nav href returned HTTP 404 or 410 at capture time.',
        'UNKNOWN': 'Insufficient evidence for this bounded rule judgment.',
        'ACCESS_BLOCKED': 'Access was blocked in this bounded capture; no website defect is asserted.',
    }[result]
    observation = {'schema_version': '1.0', 'tenant_id': doc['tenant_id'], 'run_id': doc['run_id'],
        'rule_id': rule['rule_id'], 'rule_version': rule['rule_version'],
        'evidence_ids': ids, 'result': result, 'kind': 'OBJECTIVE' if objective else 'UNKNOWN',
        'statement': statement,
        'coverage_note': coverage_note or 'One static HTML nav anchor and its captured target response only; no rendered visibility, whole-site absence, category semantics, mobile usability or live availability claim.'}
    row = {'observation': observation, 'reason': reason, 'citations': citations,
           'homepage': home, 'target_response': target}
    if source is not None:
        row['source_page'] = source
        del row['homepage']
    observation['observation_id'] = 'obs-' + document_hash(row)
    validate_contract('Observation', observation)
    return row


def _discover(pack, doc, rule):
    records = _records(doc)
    homes = [r for r in records if r[1]['role'] == 'HOME']
    rows = []
    for home in homes:
        _, page, snapshot, _ = home
        home_meta = _metadata(home)
        if snapshot['status'] == 'ACCESS_BLOCKED':
            rows.append(_row(doc, rule, 'ACCESS_BLOCKED', 'HOMEPAGE_ACCESS_BLOCKED', home=home_meta))
            continue
        ev = next((e for e in doc['evidence'] if e['snapshot_ref'] == snapshot['snapshot_ref']
                   and e['kind'] == 'HTTP_BODY' and e['status'] == 'OBSERVED'), None)
        if ev is None or ev['blob_ref'] is None:
            rows.append(_row(doc, rule, 'UNKNOWN', 'HOMEPAGE_RAW_HTML_REQUIRED', home=home_meta))
            continue
        raw = pack.resolve(ev['evidence_ref'], expected_pack_ref=pack.ref)['content']
        parser = Navigation()
        try:
            if raw is None or len(raw) > 131072:
                raise ValueError('HTML_BOUND')
            parser.feed(raw.decode('utf-8-sig', errors='strict'))
            parser.close()
            if parser.ambiguous:
                raise ValueError('AMBIGUOUS_HTML')
        except (ValueError, UnicodeError):
            rows.append(_row(doc, rule, 'UNKNOWN', 'HTML_UNSUPPORTED_OR_AMBIGUOUS', home=home_meta))
            continue
        candidates = []
        for anchor in parser.anchors:
            try:
                href = anchor['raw_href']
                if len(href) > 2048 or any(ord(c) <= 32 or ord(c) >= 127 for c in href):
                    continue
                url = canonical_url(urljoin(snapshot['final_url'], anchor['raw_href']))
            except ValueError:
                continue
            if urlsplit(url).hostname != urlsplit(snapshot['url']).hostname:
                continue
            # These are the collector's path roles, not a semantic product claim.
            if page_role(url) not in ('CATEGORY', 'CATALOG'):
                continue
            candidates.append((anchor, url))
        if not candidates:
            rows.append(_row(doc, rule, 'UNKNOWN', 'NO_SUPPORTED_STATIC_NAV_CANDIDATE', home=home_meta))
        for anchor, url in candidates:
            target = next((r for r in records if r[2]['url'] == url), None)
            citation = {'evidence_ref': ev['evidence_ref'], 'source_ref': ev['source_ref'],
                'locator': ev['locator'], 'snapshot_ref': snapshot['snapshot_ref'],
                'url': snapshot['url'], 'observed_at': snapshot['observed_at'], **anchor}
            result, reason = 'UNKNOWN', 'TARGET_NOT_OBSERVED'
            if target is not None:
                _, target_page, target_snap, _ = target
                status = target_page['http_status']
                if target_snap['status'] == 'ACCESS_BLOCKED':
                    result, reason = 'ACCESS_BLOCKED', 'TARGET_ACCESS_BLOCKED'
                elif (status in (404, 410) and target_page['error']
                      and target_page['error']['code'] == 'HTTP_ERROR'):
                    result, reason = classify_rule(False, [ev['evidence_ref']]), 'CAPTURED_BROKEN_NAV_HREF'
                elif target_snap['status'] == 'OBSERVED' and status == 200:
                    target_ev = next((e for e in doc['evidence']
                        if e['snapshot_ref'] == target_snap['snapshot_ref'] and e['kind'] == 'HTTP_BODY'
                        and e['status'] == 'OBSERVED' and e['blob_ref'] is not None), None)
                    if target_ev is not None and page_role(target_snap['final_url']) in ('CATEGORY', 'CATALOG'):
                        pack.resolve(target_ev['evidence_ref'], expected_pack_ref=pack.ref)
                        result, reason = classify_rule(True, [ev['evidence_ref']]), 'CAPTURED_REACHABLE_NAV_HREF'
                        citation['target_evidence_ref'] = target_ev['evidence_ref']
            rows.append(_row(doc, rule, result, reason, citations=[citation], home=home_meta,
                             target=_metadata(target) if target else None))
    return rows or [_row(doc, rule, 'UNKNOWN', 'HTTP_HOMEPAGE_REQUIRED')]


def execute(pack: EvidencePack, *, expected_pack_ref: str, evaluator_version: str = VERSION) -> dict:
    if not isinstance(expected_pack_ref, str) or not re.fullmatch(r'ep-[0-9a-f]{64}', expected_pack_ref):
        raise EvidenceError('RULE_EXECUTION_INTEGRITY')
    pack.verify(expected_ref=expected_pack_ref)
    if evaluator_version not in (VERSION, JOURNEY_VERSION, INFO_VERSION):
        raise EvidenceError('RULE_VERSION_UNSUPPORTED')
    doc = pack.document
    rules = catalog()
    executions = []
    for rule in rules['rules']:
        enabled = rule['rule_id'] == 'DISC-01'
        if evaluator_version == INFO_VERSION and rule['rule_id'] == 'INFO-01':
            from .info01 import evaluate_product_info
            enabled, rows = True, evaluate_product_info(
                pack, doc, rule, expected_pack_ref=expected_pack_ref)
        elif evaluator_version in (JOURNEY_VERSION, INFO_VERSION) and rule['rule_id'] in ('DISC-02', 'CTA-02'):
            from .journey import evaluate_links
            enabled, rows = True, evaluate_links(pack, doc, rule)
        else:
            rows = _discover(pack, doc, rule) if enabled else [_row(
                doc, rule, 'UNKNOWN', GAPS[rule['rule_id']])]
        executions.append({'rule_id': rule['rule_id'], 'rule_version': rule['rule_version'],
            'buyer_task': rule['buyer_task'], 'enabled': enabled, 'observations': rows})
    result = {'schema_version': '1.0', 'evaluator_version': evaluator_version,
        'catalog_version': rules['catalog_version'], 'catalog_sha256': document_hash(rules),
        'expected_pack_ref': expected_pack_ref, 'tenant_id': doc['tenant_id'], 'run_id': doc['run_id'],
        'executions': executions, 'coverage': doc['coverage'],
        'limitations': ['OFFLINE_SYNTHETIC_CONSISTENCY_ONLY', 'NO_LIVE_AUTHORIZATION_CHECK',
                        'STATIC_NAV_HREF_ONLY', 'NO_FINDINGS_OR_BUSINESS_IMPACT']}
    if evaluator_version in (JOURNEY_VERSION, INFO_VERSION):
        from .journey import compose_paths
        result['journeys'], result['journey_composition'] = compose_paths(executions)
        result['recorded_capture_scope'] = [{
            'source_ref': source['source_ref'],
            **{k: source['document'][k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')},
            'terms_reference': source['document'].get('terms_reference'),
            'authorization_limit': 'RECORDED_SCOPE_NOT_CURRENT_AUTHORIZATION',
        } for source in doc['sources']]
        result['limitations'][2] = 'STATIC_HREF_PATH_ONLY'
    if evaluator_version == INFO_VERSION:
        result['limitations'][2] = 'STATIC_HREF_PATH_AND_PRODUCT_SOURCE_TEXT_ONLY'
        result['limitations'].extend(['INFO01_POSITIVE_ONLY_NO_FAIL_OR_NOT_APPLICABLE',
                                      'NO_PRODUCT_ACCURACY_COMPLETENESS_OR_FIT_CLAIM'])
    result['execution_ref'] = 'rx-' + document_hash(result)
    return result


def verify_execution(output: dict, pack: EvidencePack, *, expected_pack_ref: str,
                     expected_evaluator_version: str | None = None) -> None:
    """Recompute every assertion, locator, response and output against a trusted pin."""
    try:
        version = output['evaluator_version']
        if expected_evaluator_version is not None and version != expected_evaluator_version:
            raise ValueError('RULE_VERSION_MISMATCH')
        expected = execute(pack, expected_pack_ref=expected_pack_ref, evaluator_version=version)
        if json.dumps(output, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True):
            raise ValueError('RULE_EXECUTION_MISMATCH')
    except Exception as exc:
        raise EvidenceError('RULE_EXECUTION_INTEGRITY') from exc
