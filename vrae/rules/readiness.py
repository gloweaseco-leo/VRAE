"""Implementation gaps; the original catalog remains the rule/version authority."""
import json
from pathlib import Path

from vrae.domain.contracts import validate_contract

GAPS = {
    'DISC-01': 'Requires retained homepage HTML nav href and same-pack target response; scope is one static anchor.',
    'DISC-02': 'Category-to-product sequence extraction and product identity are not implemented.',
    'DISC-03': 'No independently established industry/application relevance mapping.',
    'INFO-01': 'No product identity/specification parser with field locators.',
    'INFO-02': 'Industry pack has material requirement but no observed attribute mapping or applicability proof.',
    'INFO-03': 'Language clarity requires human verification; no deterministic semantic judgment.',
    'TRUST-01': 'No verified company identity/context extraction; href alone cannot establish identity.',
    'TRUST-02': 'No proof/context parser or authenticity evidence.',
    'TRUST-03': 'No scoped entity resolution or comparable company/contact passages.',
    'CTA-01': 'Browser DOM has tag/visible/text but no href; HTML href cannot prove rendered visibility.',
    'CTA-02': 'No product-context-to-contact path verification; no form submission is permitted.',
    'CTA-03': 'No overflow geometry or scoped visual-layout evaluator.',
    'SEO-01': 'Sitemap/tag combination and metadata applicability not implemented; robots hashes are insufficient.',
    'SEO-02': 'No verified product text/anchor context or crawlability evaluator.',
    'TECH-01': 'Non-200 snapshots have no observed EvidencePack evidence_ref; metadata-only Observation adapter deferred.',
    'TECH-02': 'No image/heading context extraction or accessibility evaluator.',
}


def catalog():
    doc = json.loads((Path(__file__).parents[2] /
        'industry-packs/rule_catalog.v1.json').read_text(encoding='utf-8'))
    validate_contract('RuleCatalog', doc)
    if {r['rule_id'] for r in doc['rules']} != set(GAPS):
        raise ValueError('RULE_CATALOG_MISMATCH')
    return doc
