"""Buyer-stage checklist and INFO-02 field binding. Synthetic pages only."""
from pathlib import Path

from tests.s2_contract.batch2_fixtures import fixture
from vrae.industry.l2_v1.buyer_stages import approved, digest, judge, load
from vrae.rules.patch_execution import execute
from vrae.rules.readiness import GAPS

WHEEL = b'''<html><body>
<nav>Bond Resin Grain Size 999 buyer@example.org</nav>
<main><h1>Back Grinding Wheel</h1><table>
<tr><th>Size(MM)</th><td>D150</td></tr>
<tr><th>Abrasive</th><td>Diamond</td></tr>
<tr><th>Grain Size</th><td>240# or as required</td></tr>
<tr><th>Bond</th><td>Resin</td></tr>
<tr><th>Usage</th><td>Sapphire</td></tr>
</table><a href="/sheet.pdf">Datasheet</a></main>
<footer>Grain Size 999</footer></body></html>'''


def test_json_signature_fields_do_not_approve():
    doc = load()
    doc['approval'] = {'signer': 'industry-reviewer', 'signed_at': '2026-11-22T00:00:00Z',
                       'config_sha256': digest(doc)}
    assert approved(doc) is False
    groups = {name: [1] for name in doc['label_aliases']}
    rows = judge(doc, groups=groups, parsed=True, ambiguous=False, technical_link=False, contact_recorded=True)
    assert all(row['decision'] == 'REVIEW_REQUIRED' and row['is_defect'] is False for row in rows)


def test_decision_table_needs_an_explicit_grant():
    doc = load()
    missing_grit = {name: [1] for name in doc['label_aliases']}
    missing_grit['grit'] = []
    blocked = judge(doc, groups=missing_grit, parsed=True, ambiguous=False,
                    technical_link=True, contact_recorded=False, grant=True)
    assert all(row['decision'] != 'GAP_WITH_EVIDENCE' for row in blocked)
    gap = judge(doc, groups=missing_grit, parsed=True, ambiguous=False,
                technical_link=False, contact_recorded=False, grant=True)
    assert next(row for row in gap if row['stage'] == 'COMPARISON')['decision'] == 'GAP_WITH_EVIDENCE'
    assert next(row for row in gap if row['stage'] == 'TECH_CONFIRMATION')['is_defect'] is False
    unclear = judge(doc, groups=missing_grit, parsed=False, ambiguous=True,
                    technical_link=False, contact_recorded=False, grant=True)
    assert all(row['decision'] == 'UNKNOWN' for row in unclear)


def test_info02_cites_the_product_page_and_leaves_1_0_5_unchanged():
    pack = fixture(overrides={'/products/p40': WHEEL})
    old = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.5')
    new = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.6')
    old_row = next(item for item in old['executions'] if item['rule_id'] == 'INFO-02')['observations'][0]
    assert old_row['reason'] == GAPS['INFO-02']
    product = next(row for row in next(item for item in new['executions'] if item['rule_id'] == 'INFO-02')['observations']
                   if row.get('source_page', {}).get('url', '').endswith('/p40'))
    assert product['observation']['result'] == 'UNKNOWN'
    assert product['checklist_approved'] is False
    assert all(not item['is_defect'] for item in product['buyer_requirements'])
    pairs = {}
    for cite in product['citations']:
        pairs.setdefault(cite['field_index'], []).append(cite)
    assert len(pairs) == 5
    for group in pairs.values():
        assert {item['fact_role'] for item in group} == {'SPEC_LABEL', 'SPEC_VALUE'}
        assert len({item['snapshot_ref'] for item in group}) == 1
        assert len({item['product_scope_ref'] for item in group}) == 1
        assert group[0]['snapshot_ref'] == product['source_page']['snapshot_ref']
        assert group[0]['byte_start'] != group[1]['byte_start']
    other = [row for row in next(item for item in new['executions'] if item['rule_id'] == 'INFO-02')['observations']
             if row.get('source_page', {}).get('snapshot_ref') != product['source_page']['snapshot_ref']]
    assert all(cite['snapshot_ref'] != product['source_page']['snapshot_ref']
               for row in other for cite in row.get('citations') or [])


def test_candidate_diagnosis_is_not_selected_for_automatic_tasks():
    source = Path('integration/authorized_targets/worker.py').read_text(encoding='utf-8')
    assert 'l2-industrial-1.0.8' not in source
    assert 'l2-industrial-1.0.7' in source


def test_candidate_executor_does_not_change_the_old_info02_reason():
    pack = fixture(overrides={'/products/p40': WHEEL})
    old = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.5')
    new = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.6')
    old_reason = next(item for item in old['executions'] if item['rule_id'] == 'INFO-02')['observations'][0]['reason']
    new_product = next(row for row in next(item for item in new['executions'] if item['rule_id'] == 'INFO-02')['observations']
                       if row.get('buyer_requirements'))
    assert old_reason == GAPS['INFO-02']
    assert new_product['observation']['result'] != 'FAIL_WITH_EVIDENCE'
