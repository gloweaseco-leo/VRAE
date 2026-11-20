"""Positive-only INFO-01 adapter over the accepted pinned product source extractor."""
from .execution import _metadata, _records, _row
from .product_facts import extract

COVERAGE = (
    'One captured product-path page, URL role heuristic only; original static h1 and '
    'TH/TD text only. No rendered visibility, SKU identity, specification accuracy, '
    'authenticity, engineering fit, completeness, buyer comprehension or business impact. '
    'Missing, empty or ambiguous information is not a website defect.'
)


def evaluate_product_info(pack, doc, rule, *, expected_pack_ref, generic=False):
    facts = extract(pack, expected_pack_ref=expected_pack_ref, generic=generic)
    records = {r[2]['snapshot_ref']: r for r in _records(doc)}
    rows = []
    for page in facts['pages']:
        source = _metadata(records[page['snapshot']['snapshot_ref']])
        result = {'EXTRACTED': 'PASS', 'UNKNOWN': 'UNKNOWN',
                  'ACCESS_BLOCKED': 'ACCESS_BLOCKED'}[page['status']]
        citations = []
        # Retain available original locators even for UNKNOWN, but never promote
        # them into objective Observation.evidence_ids without a positive result.
        if page['name'] is not None:
            citations.append({**page['name'], 'fact_role': 'NAME', 'field_index': None})
        for index, field in enumerate(page['fields']):
            if generic and field['status'] != 'EXTRACTED':
                continue
            for key, role in (('label', 'SPEC_LABEL'), ('value', 'SPEC_VALUE')):
                citations.append({**field[key], 'fact_role': role, 'field_index': index})
        citations.extend({**d, 'fact_role': 'DESCRIPTION', 'field_index': None}
                         for d in page.get('descriptions', []))
        statement = {
            'PASS': 'A product display name and at least one label-value specification were observed in this captured static HTML.',
            'UNKNOWN': 'Insufficient unambiguous retained static HTML evidence for the bounded product name/specification check.',
            'ACCESS_BLOCKED': 'Access to this captured product-path page was blocked; no product information defect is asserted.',
        }[result]
        if generic and result == 'PASS':
            statement = 'A display name and at least one label-value field were retained on this captured product-path page; descriptive text is source context only.'
        row = _row(doc, rule, result, page['reason'], source=source,
                         citations=citations, statement=statement, coverage_note=(
                             'Bounded static source text only; no rendered visibility, product identity, specification accuracy, completeness or engineering suitability verified.'
                             if generic else COVERAGE))
        if generic and page['name'] is not None:
            row['source_text_presence'] = 'OBSERVED'
        rows.append(row)
    return rows or [_row(doc, rule, 'UNKNOWN', 'PRODUCT_PATH_NOT_CAPTURED',
        statement='No supported captured product-path source is available for this bounded check.',
        coverage_note=COVERAGE)]
