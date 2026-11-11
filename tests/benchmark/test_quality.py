import base64
from copy import deepcopy
import json
from pathlib import Path

import pytest

from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError
from vrae.findings import FindingError
from .quality import (BenchmarkError, evaluate_directory, replay_sample, assess_sample,
                      validate_candidates, score_candidate, PENDING)

ROOT = Path(__file__).parent / 'samples'
MANIFEST_REF = 'cdea4fd2db9abcdce16e31632c9f6c96ff27fe32eb7a37ffc8711b432655a8fa'


@pytest.fixture(scope='module')
def samples():
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    return {entry['site_id']: json.loads((ROOT / entry['file']).read_text(encoding='utf-8'))
            for entry in manifest['samples']}


@pytest.fixture(scope='module')
def report():
    return evaluate_directory(ROOT, expected_manifest_ref=MANIFEST_REF)


def test_candidates_never_become_human_gold_or_quality_pass(report):
    assert report['status'] == 'SYNTHETIC_BENCHMARK_READY'
    assert report['site_count'] == 7 and report['distinct_site_types'] == 6
    gold = report['human_gold_evaluation']
    assert gold['quality_gate'] == 'QUALITY_GATE_NOT_EVALUABLE'
    assert gold['status'] == 'GOLD_LABEL_PENDING'
    assert gold['reviewed_units'] == 0 and gold['independent_reviewers'] == []
    assert all(gold[field] is None for field in ('TP', 'FP', 'FN', 'TN', 'precision', 'recall', 'denominator'))
    todos = [todo for site in report['sites'] for todo in site['review_todos']]
    assert len(todos) == 26
    assert all(all(todo[field] is None for field in (*PENDING, 'human_label')) for todo in todos)


def test_actual_defects_positives_unknown_and_blocks_are_separate(report):
    rules = [rule for site in report['sites'] for rule in site['rules']]
    totals = {status: sum(r['outcomes'][status] for r in rules)
              for status in ('PASS', 'FAIL_WITH_EVIDENCE', 'UNKNOWN', 'ACCESS_BLOCKED')}
    assert totals == dict(PASS=6, FAIL_WITH_EVIDENCE=3, UNKNOWN=14, ACCESS_BLOCKED=3)
    assert sum(r['binary_scored_units'] for r in rules) == 9
    assert sum(r['candidate_confusion']['TP'] for r in rules) == 3
    assert sum(r['candidate_confusion']['TN'] for r in rules) == 6
    assert report['synthetic_case_consistency']['mismatches'] == 0
    assert all(site['deferred_rule_count'] == 13 for site in report['sites'])
    assert sum(len(site['deferred_rule_ids']) for site in report['sites']) == 91
    assert all(site['mobile_layout_coverage'] == 'NOT_OBSERVED_NOT_SCORED' for site in report['sites'])


def test_all_resealed_false_diagnostic_counterexamples_rejected(report):
    assert {c['case'] for c in report['counterexamples']} == {
        'missing_target_response', 'whole_site_overclaim', '403_as_defect'}
    assert all(c['result'] == 'REJECTED' and c['counted_as_accurate_result'] is False
               for c in report['counterexamples'])


@pytest.mark.parametrize('expected,actual,cell', [
    ('PASS', 'FAIL_WITH_EVIDENCE', 'FP'), ('FAIL_WITH_EVIDENCE', 'PASS', 'FN'),
    ('PASS', 'PASS', 'TN'), ('FAIL_WITH_EVIDENCE', 'FAIL_WITH_EVIDENCE', 'TP'),
    ('UNKNOWN', 'PASS', 'unjustified_pass'), ('ACCESS_BLOCKED', 'FAIL_WITH_EVIDENCE', 'unsupported_defect'),
    ('FAIL_WITH_EVIDENCE', 'UNKNOWN', 'unresolved_expected_defects')])
def test_confusion_math_reveals_wrong_answers_instead_of_greenwashing(expected, actual, cell):
    counts = score_candidate(expected, actual)
    assert counts[cell] == 1
    if 'UNKNOWN' in (expected, actual) or 'ACCESS_BLOCKED' in (expected, actual):
        assert sum(counts[k] for k in ('TP', 'FP', 'FN', 'TN')) == 0


def test_zero_binary_denominator_is_not_perfect_accuracy(report):
    for site in report['sites']:
        if site['site_id'] in ('spa_navigation', 'waf_challenge', 'robots_denied', 'unretained_html'):
            assert all(rule['binary_scored_units'] == 0 for rule in site['rules'])
            assert all(rule['human_gold_confusion']['TN'] is None for rule in site['rules'])


@pytest.mark.parametrize('site_id', ['static_catalog', 'mixed_broken_paths', 'spa_navigation',
    'waf_challenge', 'robots_denied', 'redirect_budget', 'unretained_html'])
def test_each_site_independently_replays_with_authored_input_and_candidate_refs(samples, site_id):
    sample = samples[site_id]
    pack, execution = replay_sample(sample)
    site = assess_sample(sample, execution)
    assert pack.ref == sample['pins']['expected_pack_ref']
    assert all(rule['candidate_confusion']['mismatch'] == 0 for rule in site['rules'])
    assert site['controlled_sample_sha256'] == sample['controlled_sample_sha256']


@pytest.mark.parametrize('mutation', ['gold_stamp', 'reviewer', 'whole_site_scope', 'duplicate'])
def test_candidate_files_cannot_self_approve_or_overclaim(samples, mutation):
    sample = deepcopy(samples['static_catalog'])
    if mutation == 'gold_stamp':
        sample['candidate_labels'][0]['status'] = 'GOLD_APPROVED'
    elif mutation == 'reviewer':
        sample['candidate_labels'][0]['reviewer'] = 'AUTOMATIC_NOT_INDEPENDENT'
    elif mutation == 'whole_site_scope':
        sample['candidate_labels'][0]['scope'] = 'WHOLE_SITE_HAS_NO_PRODUCTS'
    else:
        sample['candidate_labels'].append(deepcopy(sample['candidate_labels'][0]))
    with pytest.raises(BenchmarkError):
        validate_candidates(sample)


@pytest.mark.parametrize('mutation', ['blob', 'pack_ref', 'missing_target', 'wrong_status'])
def test_bad_evidence_never_enters_quality_counts(samples, mutation):
    sample = deepcopy(samples['mixed_broken_paths'])
    if mutation == 'blob':
        sample['objects_base64'][next(iter(sample['objects_base64']))] = base64.b64encode(b'fabricated').decode()
    elif mutation == 'pack_ref':
        sample['pins']['expected_pack_ref'] = 'ep-' + '0' * 64
    else:
        package = sample['finding_package']
        item = next(i for i in package['items'] if i['finding']['kind'] == 'OBSERVATION')
        if mutation == 'missing_target':
            del item['provenance']['target_response']
        else:
            item['provenance']['target_response']['http_status'] = 403
        package['package_ref'] = 'fp-' + document_hash({k: v for k, v in package.items() if k != 'package_ref'})
        sample['pins']['expected_package_ref'] = package['package_ref']
    from .quality import controlled_sample_ref
    sample['controlled_sample_sha256'] = controlled_sample_ref(sample)
    for label in sample['candidate_labels']:
        label['controlled_sample_sha256'] = sample['controlled_sample_sha256']
    with pytest.raises((BenchmarkError, EvidenceError, FindingError)):
        replay_sample(sample)


def test_wrong_manifest_pin_is_not_automatically_accepted():
    with pytest.raises(BenchmarkError):
        evaluate_directory(ROOT, expected_manifest_ref='0' * 64)


def test_incorrect_candidate_expectations_show_mismatch_not_gold_success(samples):
    sample = deepcopy(samples['static_catalog'])
    _, execution = replay_sample(sample)
    sample['candidate_labels'][0]['expected'] = 'FAIL_WITH_EVIDENCE'
    result = assess_sample(sample, execution)
    assert result['rules'][0]['candidate_confusion']['FN'] == 1
    assert result['rules'][0]['candidate_confusion']['mismatch'] == 1
    assert result['human_gold_confusion']['FN'] is None


def test_candidate_false_positive_is_reported_without_official_accuracy(samples):
    sample = deepcopy(samples['mixed_broken_paths'])
    _, execution = replay_sample(sample)
    sample['candidate_labels'][0]['expected'] = 'PASS'  # Deliberately inconsistent annotation.
    result = assess_sample(sample, execution)
    assert result['rules'][0]['candidate_confusion']['FP'] == 1
    assert result['rules'][0]['candidate_confusion']['mismatch'] == 1
    assert result['rules'][0]['human_gold_confusion']['FP'] is None


def test_unknown_cannot_be_reclassified_as_pass_before_counting(samples):
    sample = deepcopy(samples['spa_navigation'])
    execution = sample['finding_package']['rule_execution']
    execution['executions'][0]['observations'][0]['observation']['result'] = 'PASS'
    with pytest.raises(BenchmarkError):
        assess_sample(sample, execution)


def test_unobserved_candidate_unit_is_pending_not_tn_or_complete(samples):
    sample = deepcopy(samples['static_catalog'])
    _, execution = replay_sample(sample)
    extra = deepcopy(sample['candidate_labels'][0])
    extra.update(target_url='https://example.org/category/unobserved', anchor_index=99,
                 expected='UNKNOWN', rationale='Uncovered candidate unit for the review test.')
    sample['candidate_labels'].append(extra)
    result = assess_sample(sample, execution)
    assert result['rules'][0]['uncovered_candidate_units'] == 1
    assert result['rules'][0]['candidate_confusion']['TN'] == 1
    assert any(todo['observed_result'] is None and todo['review_status'] == 'GOLD_LABEL_PENDING'
               for todo in result['review_todos'])
