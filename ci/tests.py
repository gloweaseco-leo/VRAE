"""Explicit CI policy tests, outside the frozen product test inventory."""
import importlib
from pathlib import Path

import pytest


def policy():
    return importlib.import_module('ci.policy')


@pytest.mark.parametrize('path', ['vrae/reporting/s2_candidate.py', 'vrae/rules/s2/static.py',
                                  'tests/s2_contract/buyer_candidate_cases.py'])
def test_readonly_known_paths_fast_with_source_security_smoke(path):
    plan = policy().make_plan([path])
    assert plan['tier'] == 'FAST'
    assert plan['legacy_311'] is False
    assert 's2_rule_contract' in plan['families']
    assert plan['core_tests'] == policy().SECURITY_SMOKE
    assert plan['business_full_pass_claim'] is False


@pytest.mark.parametrize('path', ['vrae/evidence/pack.py', 'vrae/interpretation/guard.py',
    'vrae/collection/policy.py', 'vrae/application/ra4b/store.py', 'worker/ra4b/run.py',
    'db/migrations/0004.sql', 'apps/operator_console/b5b_http.py'])
def test_security_paths_require_all_affected_real_safety_suites(path):
    plan = policy().make_plan([path])
    assert plan['tier'] == 'SECURITY'
    assert set(plan['families']) == set(policy().ALL_FAMILIES)
    assert plan['core_tests'] == ['tests']
    assert plan['isolated_http'] and plan['isolated_browser']


@pytest.mark.parametrize('path', ['new/unknown.py', 'README.md', '.github/workflows/ra0-ci.yml',
                                  'ci/policy.py', 'requirements-ra4b-p1.lock', 'pyproject.toml'])
def test_unknown_policy_or_dependency_changes_are_full_not_silent_skip(path):
    plan = policy().make_plan([path])
    assert plan['tier'] == 'FULL'
    assert set(plan['families']) == set(policy().ALL_FAMILIES)


def test_mixed_and_rename_old_security_path_cannot_be_hidden_by_readonly_path():
    assert policy().make_plan(['vrae/reporting/s2_candidate.py', 'vrae/evidence/pack.py'])['tier'] == 'SECURITY'
    assert policy().make_plan([])['tier'] == 'FULL'
    assert policy().make_plan(['vrae/reporting/s2_candidate.py', 'unknown/file'])['tier'] == 'FULL'


def test_only_manual_comparisons_can_select_controlled_readonly_paths():
    with pytest.raises(ValueError):
        policy().make_plan(['vrae/evidence/pack.py'], event='pull_request', mode='compare-readonly')
    plan = policy().make_plan([], event='workflow_dispatch', mode='compare-readonly')
    assert plan['comparison_only'] and plan['tier'] == 'FAST'
    assert plan['effective_paths'] == ['vrae/reporting/s2_candidate.py']
    assert plan['current_code_unchanged'] is True


def test_legacy_manual_and_scheduled_entries_retained():
    assert policy().make_plan([], event='schedule')['legacy_311'] is True
    assert policy().make_plan([], event='workflow_dispatch', mode='compatibility')['legacy_311'] is True
    assert policy().make_plan(['.github/workflows/ra0-ci.yml'])['legacy_311'] is True
    plan = policy().make_plan([], event='workflow_dispatch', mode='compare-baseline')
    assert plan['legacy_311'] and plan['comparison_only']
    assert set(plan['families']) == set(policy().OLD_COMMON_FAMILIES)


def test_job_results_do_not_turn_skips_or_failures_into_business_pass():
    plan = policy().make_plan(['vrae/reporting/s2_candidate.py'])
    results = {'plan': 'success', 'contracts-domain': 'success', 's2_rule_contract': 'success'}
    policy().verify_results(plan, results)
    for bad in ('skipped', 'cancelled', 'failure'):
        with pytest.raises(ValueError):
            policy().verify_results(plan, {**results, 's2_rule_contract': bad})
    with pytest.raises(ValueError):
        policy().verify_results(plan, {'plan': 'success', 'contracts-domain': 'success'})


def test_pr_gate_and_comparison_check_names_are_distinct():
    source = (Path(__file__).parents[1] / '.github/workflows/ra0-ci.yml').read_text(encoding='utf-8')
    assert 'ci-policy-result' in source and 'ci-policy-manual-result' in source


def test_existing_workflows_are_reused_without_changing_original_executable_steps():
    policy().verify_workflow_parity()
