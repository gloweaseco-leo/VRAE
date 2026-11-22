"""L-B observations for evaluator ra2b6-1.0.6. Not a second rule engine.

INFO-02 follows the abrasive checklist. Unsigned checklists cannot fail.
TRUST-03 compares normalized declarations and never emits FAIL. TRUST-02 records
certificate or case statements; authenticity stays UNKNOWN. TECH-01 and SEO-02
stay inside the captured sample.
"""
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from .execution import _records, _row

LEVEL = 'L-B'
INFO02_NOTE = '只覆盖本次产品页；不判断工程适配，也不判断全站。'
NOTE = '单次测量，含调度开销，不含 DNS。不是用户体验，也不是评分。渲染性能与移动端本次未测。'
SCHEMA = json.loads((Path(__file__).parents[2] /
    'contracts/v1/collection/extensions/MetadataCitation.schema.json').read_text(encoding='utf-8'))
EMAIL = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.I)
PHONE = re.compile(r'(?:\+\d[\d\s().-]{6,}\d)')
CERT = re.compile(r'(certificate|iso\s*\d|case study|证书|案例)', re.I)
ISSUER = re.compile(r'(issued by|issuer|发证方|认证机构)\s*[:：]\s*([^\n,;]{2,80})', re.I)
NUMBER = re.compile(r'(no\.|number|编号|证书号)\s*[:：]\s*([A-Z0-9-]{3,40})', re.I)
DATE = re.compile(r'(20\d{2}-\d{2}-\d{2})')


def _meta(status=None, redirects=(), nbytes=None, first_byte=None, exchange=None):
    document = {'schema_version': '1.0', 'kind': 'METADATA_CITATION', 'http_status': status,
                'redirects': [{'status': code} for code in redirects], 'bytes': nbytes,
                'first_byte_ms': first_byte, 'exchange_ms': exchange, 'note': NOTE}
    Draft202012Validator(SCHEMA).validate(document)
    return document


def normalize_name(value):
    return ' '.join(value.casefold().split())


def normalize_email(value):
    return value.strip().casefold()


def normalize_phone(value):
    return ''.join(ch for ch in value if ch.isdigit())


def compare_declarations(pages):
    """Exact normalized comparison. Conflict is UNKNOWN, never FAIL."""
    buckets = {'name': {}, 'email': {}, 'phone': {}}
    normalizers = {'name': normalize_name, 'email': normalize_email, 'phone': normalize_phone}
    for page in pages:
        identity = page.get('url') or page.get('id')
        for key, normalize in normalizers.items():
            raw = page.get(key)
            if not raw:
                continue
            buckets[key].setdefault(normalize(raw), set()).add(identity)
    conflicts, consistent, seen = [], [], 0
    for key, groups in buckets.items():
        identities = {item for ids in groups.values() for item in ids}
        if len(identities) >= 2:
            seen += 1
        if len(groups) > 1 and len(identities) >= 2:
            conflicts.append(key)
        elif len(groups) == 1 and len(identities) >= 2:
            consistent.append(key)
    if conflicts:
        return 'UNKNOWN', 'CONFLICT_REVIEW_REQUIRED'
    if consistent:
        return 'PASS', 'DECLARATIONS_CONSISTENT'
    return 'UNKNOWN', 'FEWER_THAN_TWO_PAGES'


def record_proof(text, *, expired_before_capture=False):
    """Record a main-content certificate or case statement. Authenticity stays UNKNOWN."""
    if not text or not CERT.search(text):
        return 'UNKNOWN', 'PROOF_STATEMENT_NOT_RECORDED', {'authenticity': 'UNKNOWN', 'expiry_comparison': None}
    details = {'authenticity': 'UNKNOWN', 'issuer': None, 'number': None, 'date': None,
               'expiry_comparison': 'BEFORE_CAPTURE' if expired_before_capture else None,
               'expiry_is_qualification': False}
    issuer, number, date = ISSUER.search(text), NUMBER.search(text), DATE.search(text)
    if issuer:
        details['issuer'] = issuer.group(2).strip()
    if number:
        details['number'] = number.group(2).strip()
    if date:
        details['date'] = date.group(1)
    return 'PASS', 'DECLARATION_CONTEXT_RECORDED', details


def tech01(records):
    """Key-page 200, captured 404/410, single 5xx, and access blocks. Redirects are recorded only."""
    redirects = tuple(item.get('redirect_status') for item in records if item.get('redirect_status'))
    statuses = [item.get('http_status') for item in records]
    if any(item.get('access_blocked') or item.get('http_status') in (401, 403, 429) for item in records):
        return 'ACCESS_BLOCKED', 'ACCESS_BLOCKED', _meta(redirects=redirects)
    if any(status in (404, 410) for status in statuses):
        return 'FAIL_WITH_EVIDENCE', 'CAPTURED_INTERNAL_LINK_404_OR_410', _meta(
            status=404 if 404 in statuses else 410, redirects=redirects)
    if any(status is not None and 500 <= status <= 599 for status in statuses):
        return 'UNKNOWN', 'TRANSIENT_NOT_PROVEN', _meta(status=next(
            status for status in statuses if status is not None and status >= 500), redirects=redirects)
    key = [item for item in records if item.get('key_page')]
    if key and all(item.get('http_status') == 200 for item in key):
        return 'PASS', 'KEY_PAGES_FINAL_200', _meta(status=200, redirects=redirects,
            nbytes=key[0].get('bytes'), first_byte=key[0].get('first_byte_ms'), exchange=key[0].get('exchange_ms'))
    return 'UNKNOWN', 'KEY_PAGE_NOT_OBSERVED', _meta(redirects=redirects)


def seo02(*, main_text=None, internal_link=False, script_dependent=False):
    if script_dependent:
        return 'UNKNOWN', 'SCRIPT_DEPENDENT_NOT_A_FAILURE'
    if main_text and internal_link:
        return 'PASS', 'STATIC_MAIN_CONTENT_AND_INTERNAL_LINK'
    return 'UNKNOWN', 'STATIC_MAIN_OR_LINK_NOT_OBSERVED'


def _declarations_from_pack(pack, doc):
    pages = []
    for record in _records(doc):
        _, page, snapshot, _ = record
        if snapshot.get('status') not in ('OBSERVED', 'FETCHED') and page.get('snapshot', {}).get('status') != 'FETCHED':
            continue
        role = page.get('role') or snapshot.get('role')
        if role not in ('HOME', 'ABOUT', 'CONTACT'):
            continue
        evidence = next((item for item in doc['evidence']
                         if item.get('snapshot_ref') == snapshot.get('snapshot_ref')
                         and item.get('kind') == 'HTTP_BODY' and item.get('status') == 'OBSERVED'), None)
        text = ''
        if evidence and evidence.get('blob_ref'):
            try:
                raw = pack.resolve(evidence['evidence_ref'], expected_pack_ref=pack.ref)['content'] or b''
                text = raw.decode('utf-8', errors='ignore')
            except Exception:
                text = ''
        email, phone = EMAIL.search(text), PHONE.search(text)
        pages.append({'url': snapshot.get('url'), 'name': None,
                      'email': email.group(0) if email else None,
                      'phone': phone.group(0) if phone else None, 'text': text[:4000]})
    return pages


def _evidence_ref(doc, snapshot):
    evidence = next((item for item in doc.get('evidence') or []
                     if item.get('snapshot_ref') == snapshot.get('snapshot_ref')
                     and item.get('status') == 'OBSERVED' and item.get('evidence_ref')), None)
    return None if evidence is None else evidence['evidence_ref']


def _tech_records(doc):
    rows = []
    for record in _records(doc):
        _, page, snapshot, _ = record
        status = page.get('http_status')
        error = (page.get('error') or {}).get('code')
        rows.append({'http_status': status, 'key_page': page.get('role') in ('HOME', 'CATEGORY', 'PRODUCT', 'CONTACT'),
                     'access_blocked': error == 'ACCESS_BLOCKED' or status in (401, 403, 429),
                     'redirect_status': next((hop.get('status') for hop in page.get('redirect_trace') or []
                                              if isinstance(hop, dict) and hop.get('status') in range(300, 400)), None),
                     'bytes': snapshot.get('bytes') if isinstance(snapshot.get('bytes'), int) else None,
                     'evidence_ref': _evidence_ref(doc, snapshot)})
    return rows


def apply(pack, result):
    from vrae.industry.l2_v1.buyer_stages import evaluate, info02_result, load
    doc = pack.document
    evaluated = evaluate(load(), [])
    info_result, info_reason = info02_result(evaluated)
    if info_result == 'FAIL_WITH_EVIDENCE':
        info_result, info_reason = 'UNKNOWN', 'UNSIGNED_OR_UNMAPPED'
    declarations = _declarations_from_pack(pack, doc)
    trust_result, trust_reason = compare_declarations(declarations)
    proof_text = '\n'.join(page.get('text') or '' for page in declarations)
    proof_result, proof_reason, proof_details = record_proof(proof_text)
    tech_result, tech_reason, citation = tech01(_tech_records(doc))
    seo_result, seo_reason = seo02()
    tech_rows = _tech_records(doc)
    if tech_result == 'FAIL_WITH_EVIDENCE':
        bound = next((item.get('evidence_ref') for item in tech_rows
                      if item.get('http_status') in (404, 410) and item.get('evidence_ref')), None)
    else:
        bound = next((item.get('evidence_ref') for item in tech_rows if item.get('evidence_ref')), None)
    if tech_result in ('PASS', 'FAIL_WITH_EVIDENCE') and bound is None:
        tech_result, tech_reason = 'UNKNOWN', 'EVIDENCE_REF_REQUIRED'
    if trust_result == 'PASS' and bound is None:
        trust_result, trust_reason = 'UNKNOWN', 'EVIDENCE_REF_REQUIRED'
    if proof_result == 'PASS' and bound is None:
        proof_result, proof_reason = 'UNKNOWN', 'EVIDENCE_REF_REQUIRED'
    replacements = {
        'INFO-02': (info_result, info_reason, INFO02_NOTE, None, None),
        'TRUST-03': (trust_result, trust_reason, '声明比较不是法人核验，冲突不构成缺陷。', None, bound if trust_result == 'PASS' else None),
        'TRUST-02': (proof_result, proof_reason, '只记录声明上下文；真伪为 UNKNOWN。过期比较不是无资质结论。', proof_details, bound if proof_result == 'PASS' else None),
        'TECH-01': (tech_result, tech_reason, NOTE, citation, bound if tech_result in ('PASS', 'FAIL_WITH_EVIDENCE') else None),
        'SEO-02': (seo_result, seo_reason, '脚本依赖保持 UNKNOWN，不据此判定失败。', None, None),
    }
    for rule_id, (code, reason, note, extra, evidence_ref) in replacements.items():
        entry = next((row for row in result['executions'] if row['rule_id'] == rule_id), None)
        if entry is None:
            continue
        rule = {'rule_id': rule_id, 'rule_version': entry.get('rule_version', '1.0.0')}
        citations = [{'evidence_ref': evidence_ref}] if evidence_ref else None
        row = _row(doc, rule, code, reason, citations=citations, coverage_note=note,
                   statement=_statement(rule_id, code))
        entry['enabled'] = True
        entry['observations'] = [row]
        entry['evidence_level'] = LEVEL
        if extra is not None and rule_id == 'TECH-01':
            entry['metadata_citation'] = extra
        if extra is not None and rule_id == 'TRUST-02':
            entry['declaration'] = extra
    return result


def _statement(rule_id, result):
    if result == 'FAIL_WITH_EVIDENCE':
        return 'A captured internal link returned HTTP 404 or 410. This is pending review, not a confirmed defect score.'
    if result == 'ACCESS_BLOCKED':
        return 'Access was blocked in this capture. No website defect is asserted.'
    if result == 'NOT_APPLICABLE':
        return 'This check is not applicable to the recorded sample.'
    if result == 'PASS' and rule_id == 'TRUST-02':
        return 'A certificate or case statement was recorded. Authenticity remains UNKNOWN.'
    if result == 'PASS':
        return 'The bounded check matched its recorded condition. This is not whole-site approval.'
    return 'The bounded check did not reach a pass or evidenced failure.'
