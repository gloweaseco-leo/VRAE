from pathlib import Path
from copy import deepcopy
import hashlib
import json
import subprocess
import shutil
import sys

import pytest

from vrae.collection.manifest import document_hash
from .human_gold import (load_packet, empty_review, assess_reviews, validate_review, export_csv,
    export_markdown, import_csv, ReviewError, write_blank_packet, OwnerTrust, _verify_signature,
    selective_counts, verified_owner_rows)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def packet():
    return load_packet(ROOT)


def simulated_review(packet):
    review = empty_review(packet)
    review['origin'] = 'SIMULATED_NOT_HUMAN_GOLD'
    selected = set()
    for binding, row in zip(packet['rows'], review['rows']):
        actual = binding['observed_result']
        if actual not in ('PASS', 'FAIL_WITH_EVIDENCE') or actual in selected:
            continue
        selected.add(actual)
        row.update(status='REVIEWED', human_verdict='PASS' if actual == 'FAIL_WITH_EVIDENCE' else 'FAIL_WITH_EVIDENCE',
            rationale='SIMULATED test disagreement, NOT a human judgement.',
            reviewer_identity='SIMULATED_REVIEWER_NOT_A_PERSON', reviewed_at='2000-01-01T00:00:00Z',
            conflict_decision='NO_CONFLICT', owner_approval_reference='SIMULATED_NOT_AN_APPROVAL')
    return review


def test_generated_defaults_never_become_gold(packet):
    result = assess_reviews(packet, empty_review(packet))
    assert len(packet['rows']) == 26
    assert result['status'] == 'HUMAN_REVIEW_READY'
    assert result['gold_status'] == 'GOLD_LABEL_PENDING'
    assert result['quality_gate'] == 'QUALITY_GATE_NOT_EVALUABLE'
    assert result['eligible_verified_rows'] == 0 and result['pending_rows'] == 26
    assert all(v is None for v in result['provisional_human_synthetic_metrics'].values())


def test_reviewer_artifacts_bind_all_26_units_and_csv_roundtrips(packet):
    assert import_csv(packet, export_csv(packet)) == empty_review(packet)
    assert len(export_csv(packet).splitlines()) == 27
    assert export_markdown(packet).count('UNREVIEWED — all human fields blank') == 26
    for binding in packet['rows']:
        assert binding['unit_ref'] and binding['controlled_sample_sha256']
        assert binding['pins']['expected_evaluator_version'] == 'ra2b1-1.0.0'


def test_disagreement_is_valid_but_demo_is_never_human_gold_even_with_nonempty_names(packet):
    review = simulated_review(packet)
    validate_review(packet, review)
    result = assess_reviews(packet, review)
    assert result['simulation_diagnostics']['FP'] == result['simulation_diagnostics']['FN'] == 1
    assert result['eligible_verified_rows'] == 0
    assert result['quality_gate'] == 'QUALITY_GATE_NOT_EVALUABLE'
    assert all(value is None for value in result['provisional_human_synthetic_metrics'].values())
    assert result['ra2d_final_pass'] is False and result['ra3_authorized'] is False


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'unit', 'binding', 'scope',
    'packet_pin', 'manifest', 'version', 'gold_stamp', 'trust_in_input'])
def test_identity_scope_or_self_approval_tamper_rejected(packet, mutation):
    review = empty_review(packet)
    row = review['rows'][0]
    if mutation == 'duplicate':
        review['rows'][1] = deepcopy(row)
    elif mutation == 'missing':
        review['rows'].pop()
    elif mutation == 'unit':
        row['unit_ref'] = 'unit-' + '0' * 64
    elif mutation == 'binding':
        row['binding_sha256'] = '0' * 64
    elif mutation == 'scope':
        row['scope'] = 'WHOLE_SITE_CANNOT_RECEIVE_INQUIRIES'
    elif mutation == 'packet_pin':
        review['packet_ref'] = 'review-packet-' + '0' * 64
    elif mutation == 'manifest':
        review['manifest_ref'] = '0' * 64
    elif mutation == 'version':
        row['rule_version'] = 'future-2.0.0'
    elif mutation == 'gold_stamp':
        row['status'] = 'GOLD_APPROVED'
    else:
        review['owner_trust'] = 'I approve myself'
    with pytest.raises(ReviewError):
        assess_reviews(packet, review)


def test_rehashed_packet_cannot_change_target_metadata(packet):
    fake = deepcopy(packet)
    row = next(row for row in fake['rows'] if row['observed_result'] == 'FAIL_WITH_EVIDENCE')
    row['target_response']['http_status'] = 403
    fake['packet_ref'] = 'review-packet-' + document_hash({k: v for k, v in fake.items() if k != 'packet_ref'})
    with pytest.raises(ReviewError):
        assess_reviews(fake, empty_review(fake))


@pytest.mark.parametrize('field,value', [('human_verdict', None), ('human_verdict', 'INVALID'),
    ('reviewer_identity', None), ('reviewed_at', '2000-01-01'),
    ('conflict_decision', 'UNRESOLVED'), ('owner_approval_reference', None)])
def test_missing_or_invalid_review_fields_stay_pending(packet, field, value):
    review = simulated_review(packet)
    row = next(row for row in review['rows'] if row['status'] == 'REVIEWED')
    row[field] = value
    result = assess_reviews(packet, review)
    assert result['incomplete_or_invalid_reviewed_rows'] == 1
    assert result['gold_status'] == 'GOLD_LABEL_PENDING'
    assert result['quality_gate'] == 'QUALITY_GATE_NOT_EVALUABLE'


def test_external_human_claim_without_owner_proof_is_not_verified(packet):
    review = simulated_review(packet)
    # Adversarial relabeling of a clearly simulated file is not proof of a person.
    review['origin'] = 'EXTERNAL_HUMAN'
    result = assess_reviews(packet, review)
    assert result['authority_state'] == 'EXTERNAL_OWNER_VERIFICATION_REQUIRED'
    assert result['eligible_verified_rows'] == 0
    assert result['production_performance'] == 'NOT_ESTABLISHED'


def test_rejected_and_conflicted_rows_cannot_silently_score(packet):
    review = empty_review(packet)
    review['rows'][0]['status'] = 'REJECTED'
    review['rows'][1]['status'] = 'CONFLICTED'
    result = assess_reviews(packet, review)
    assert result['rejected_rows'] == result['conflicted_rows'] == 1
    assert result['pending_rows'] == 26


def test_unsigned_or_wrong_review_attestation_is_pending_not_authority(packet, tmp_path):
    review = simulated_review(packet)
    review['origin'] = 'EXTERNAL_HUMAN'  # Deliberately forged external-origin claim.
    approval = tmp_path / 'unsigned-demo.json'
    approval.write_text('{}', encoding='utf-8')
    trust = OwnerTrust(tmp_path / 'no-key-provided', '0' * 64, 'SIMULATED_NOT_A_REAL_OWNER')
    approved, state = verified_owner_rows(packet, review, repository=ROOT,
        approval_file=approval, signature_file=tmp_path / 'no-signature', trust=trust)
    assert approved == set() and state == 'OWNER_ATTESTATION_NOT_VALID'


def test_signature_verifier_accepts_no_bundled_key_or_unsigned_string(tmp_path):
    anchor = tmp_path / 'not-a-trusted-key'
    anchor.write_text('SIMULATED_INVALID_NOT_AN_OWNER_KEY', encoding='utf-8')
    signature = tmp_path / 'not-a-signature'
    signature.write_text('SIMULATED_INVALID_NOT_AN_OWNER_SIGNATURE', encoding='utf-8')
    trust = OwnerTrust(anchor, hashlib.sha256(anchor.read_bytes()).hexdigest(), 'SIMULATED_NOT_A_REAL_OWNER')
    assert not _verify_signature(b'SIMULATED_NOT_HUMAN_GOLD', signature, trust, tmp_path / 'different-repo')
    assert not _verify_signature(b'SIMULATED_NOT_HUMAN_GOLD', signature, trust, tmp_path)


@pytest.mark.parametrize('field', ['source_url', 'target_url', 'http_status', 'redirect_trace', 'rule_version'])
def test_csv_evidence_columns_cannot_be_edited_to_support_a_claim(packet, field):
    import csv
    import io
    reader = csv.DictReader(io.StringIO(export_csv(packet)))
    rows = list(reader)
    rows[0][field] = 'fabricated'
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    with pytest.raises(ReviewError):
        import_csv(packet, output.getvalue())


def test_exports_never_overwrite_changed_human_review(packet, tmp_path):
    folder = tmp_path / 'review'
    write_blank_packet(packet, folder)
    write_blank_packet(packet, folder)  # Identical explicit exports are harmless.
    target = folder / 'review-input.json'
    original = target.read_text(encoding='utf-8')
    target.write_text(original + '\n', encoding='utf-8')
    with pytest.raises(ReviewError):
        write_blank_packet(packet, folder)
    assert target.read_text(encoding='utf-8') == original + '\n'


def test_unknown_blocked_and_sparse_math_is_not_tn_or_precision(packet):
    review = empty_review(packet)
    bindings = {row['unit_ref']: row for row in packet['rows']}
    unknown = next(row for row in review['rows'] if bindings[row['unit_ref']]['observed_result'] == 'UNKNOWN')
    unknown['human_verdict'] = 'PASS'
    counts = selective_counts(bindings, [unknown])
    assert counts['binary_units'] == 0 and counts['TN'] == 0 and counts['abstentions'] == 1
    result = assess_reviews(packet, review)
    assert result['provisional_human_synthetic_metrics']['precision'] is None


def test_default_cli_is_read_only_pending_and_preserves_all_old_sample_bytes():
    paths = sorted((ROOT / 'tests/benchmark/samples').glob('*.json'))
    archived_report = ROOT / 'docs/03-engineering/ra2d0-evidence/report.json'
    if archived_report.exists():
        paths.append(archived_report)
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_ra2d1.py')],
                            capture_output=True, text=True, cwd=ROOT, check=True)
    document = json.loads(result.stdout)
    assert document['status'] == 'HUMAN_REVIEW_READY'
    assert document['quality_gate'] == 'QUALITY_GATE_NOT_EVALUABLE'
    assert before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_even_a_simulated_signature_verifier_cannot_promote_demo_rows(packet, monkeypatch, tmp_path):
    from . import human_gold
    calls = []
    monkeypatch.setattr(human_gold, '_verify_signature', lambda *args: calls.append(args) or True)
    trust = OwnerTrust(tmp_path / 'SIMULATED_NOT_A_KEY', '0' * 64, 'SIMULATED_NOT_A_REAL_OWNER')
    result = assess_reviews(packet, simulated_review(packet), repository=ROOT,
        approval_file=tmp_path / 'SIMULATED_NOT_APPROVAL', signature_file=tmp_path / 'SIMULATED_NOT_SIGNATURE', trust=trust)
    assert calls == [] and result['eligible_verified_rows'] == 0
    assert result['gold_status'] == 'GOLD_LABEL_PENDING'


def test_csv_extra_cells_are_not_silently_ignored(packet):
    text = export_csv(packet)
    lines = text.splitlines()
    lines[1] += ',GOLD_APPROVED'
    with pytest.raises(ReviewError):
        import_csv(packet, '\n'.join(lines) + '\n')


def test_relabelled_simulated_rows_never_count_even_under_a_simulated_positive_verifier(packet, monkeypatch):
    from . import human_gold
    review = simulated_review(packet)
    review['origin'] = 'EXTERNAL_HUMAN'  # Adversarial relabel; reserved DEMO identities remain.
    fake_rows = {row['unit_ref'] for row in review['rows'] if row['status'] == 'REVIEWED'}
    monkeypatch.setattr(human_gold, 'verified_owner_rows', lambda *args, **kwargs:
                        (fake_rows, 'SIMULATED_VERIFIER_NOT_REAL_AUTHORITY'))
    result = assess_reviews(packet, review)
    assert result['eligible_verified_rows'] == 0
    assert result['quality_gate'] == 'QUALITY_GATE_NOT_EVALUABLE'


def test_partial_review_never_claims_an_evaluated_gate_and_false_facts_cannot_pass():
    from .human_gold import _quality_gate
    # Pure simulated policy cases, not records of human approval.
    assert _quality_gate(False, True, True) == 'QUALITY_GATE_NOT_EVALUABLE'
    assert _quality_gate(True, True, True) == 'QUALITY_GATE_FAIL_FALSE_FACT'
    assert _quality_gate(True, True, False) == 'QUALITY_GATE_OWNER_DECISION_REQUIRED'
    assert _quality_gate(True, False, False) == 'QUALITY_GATE_NOT_EVALUABLE'


def test_minimal_isolated_layout_still_reconstructs_the_exact_sealed_report(packet, tmp_path):
    root = tmp_path / 'readonly-layout'
    target = root / 'tests/benchmark/samples'
    target.parent.mkdir(parents=True)
    shutil.copytree(ROOT / 'tests/benchmark/samples', target)
    assert not (root / 'docs').exists()
    assert load_packet(root) == packet
