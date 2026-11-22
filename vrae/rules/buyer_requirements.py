"""INFO-02 over parsed product facts. Unsigned checklists cannot become defects."""
import re

from vrae.industry.l2_v1.buyer_stages import approved, judge, load, match_groups
from .execution import _metadata, _records, _row
from .product_facts import extract

COVERAGE = ('One captured product page and its parsed parameter region only. '
            'An unsigned buyer-stage checklist stays REVIEW_REQUIRED and is not a website defect. '
            'A missing field, an unparsed PDF, or an uncombined option list is not a defect.')
OPTION = re.compile(r'\bor\b|或', re.I)


def _span(body, raw):
    if not raw:
        return None
    needle = raw.encode('utf-8')
    start = body.find(needle)
    if start < 0 or body.find(needle, start + 1) >= 0:
        return None
    return start, start + len(needle)


def _locate(node, body, evidence_ref, role):
    if node.get('evidence_ref') != evidence_ref or not node.get('snapshot_ref'):
        return None
    span = _span(body, node.get('element', {}).get('raw_element'))
    if span is None or not node.get('product_scope_ref'):
        return None
    return {'evidence_ref': evidence_ref, 'snapshot_ref': node['snapshot_ref'],
            'product_scope_ref': node['product_scope_ref'], 'fact_role': role,
            'byte_start': span[0], 'byte_end': span[1]}


def _pair(field, body, evidence_ref):
    """A field is proven only when its label and value share one product region and one page."""
    label = _locate(field['label'], body, evidence_ref, 'SPEC_LABEL')
    value = _locate(field['value'], body, evidence_ref, 'SPEC_VALUE')
    if label is None or value is None:
        return None
    if label['snapshot_ref'] != value['snapshot_ref'] or label['product_scope_ref'] != value['product_scope_ref']:
        return None
    if label['byte_start'] == value['byte_start'] or label['byte_end'] == value['byte_end']:
        return None
    return label, value


def evaluate(pack, doc, rule, *, expected_pack_ref):
    checklist = load()
    facts = extract(pack, expected_pack_ref=expected_pack_ref, generic=True, content=True, scoped=True)
    records = {record[2]['snapshot_ref']: record for record in _records(doc)}
    rows = []
    for page in facts['pages']:
        record = records[page['snapshot']['snapshot_ref']]
        source = _metadata(record)
        evidence = next(item for item in doc['evidence']
                        if item['snapshot_ref'] == source['snapshot_ref'] and item['kind'] == 'HTTP_BODY'
                        and item['status'] == 'OBSERVED' and item['blob_ref'] is not None)
        body = pack.resolve(evidence['evidence_ref'], expected_pack_ref=pack.ref)['content']
        parsed = page['status'] == 'EXTRACTED'
        extracted = [field for field in page['fields'] if field['status'] == 'EXTRACTED']
        paired = []
        citations = []
        for field in extracted:
            pair = _pair(field, body, evidence['evidence_ref'])
            if pair is None:
                continue
            paired.append(field)
            citations.extend(pair)
            for cite in pair:
                cite['field_index'] = len(paired)
        grouped = match_groups(checklist, [{'label': field['label']['text']} for field in paired])
        technical = b'.pdf' in body.lower() or b'datasheet' in body.lower()
        contact = b'contact' in body.lower() or b'inquiry' in body.lower()
        requirements = judge(checklist, groups=grouped, parsed=parsed,
                             ambiguous=not parsed, technical_link=technical, contact_recorded=contact)
        if any(item['decision'] == 'GAP_WITH_EVIDENCE' for item in requirements) and not approved(checklist):
            raise RuntimeError('UNSIGNED_CHECKLIST_GAP')
        result = 'FAIL_WITH_EVIDENCE' if any(item['is_defect'] for item in requirements) else 'UNKNOWN'
        reason = 'BUYER_STAGE_GAP' if result == 'FAIL_WITH_EVIDENCE' else (
            'CHECKLIST_REVIEW_REQUIRED' if not approved(checklist) else 'BUYER_STAGE_NOT_A_DEFECT')
        relation = any(OPTION.search(field['value']['text']) for field in extracted)
        row = _row(doc, rule, result, reason, source=source, citations=citations, statement=(
            'Parsed product fields were located on this captured product page. '
            'An unsigned checklist or an uncombined option is not a website defect.'),
            coverage_note=COVERAGE)
        row['buyer_requirements'] = requirements
        row['option_relation_needs_review'] = relation
        row['checklist_approved'] = approved(checklist)
        rows.append(row)
    if not rows:
        rows.append(_row(doc, rule, 'UNKNOWN', 'PRODUCT_PATH_NOT_CAPTURED', coverage_note=COVERAGE))
    return rows
