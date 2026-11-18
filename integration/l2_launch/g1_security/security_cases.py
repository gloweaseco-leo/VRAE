"""Independent negative assertions, explicit invocation outside default inventory."""
import json
import time
from dataclasses import replace

import pytest

from integration.l2_launch.runtime.adapter import Denied, LocalPolicy, PrivateAdapter
from integration.l2_launch.security.adapter import capture_live
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient

from .contract_cases import (
    READ_CASES,
    SUBMIT_CASES,
    VIEW_CASES,
    idempotency_attack,
    log_attack,
    session_attack,
    submit_attack,
    view_attack,
)
from .replay import http_gaps, network_tripwire
from .source_cases import CASES, execute


@pytest.fixture(autouse=True)
def no_network():
    with network_tripwire() as attempts:
        yield
        assert not attempts


@pytest.mark.parametrize('spec', CASES, ids=[c['id'] for c in CASES])
def test_original_source_capture_or_actual_denial(spec):
    result, _ = execute(spec)
    assert result['verdict'] == 'PASS', result
    assert result['http_service_verified'] is False
    assert not result['promoted_findings']


@pytest.mark.parametrize('kind', SUBMIT_CASES)
def test_frozen_submission_function_refuses_independent_attack(tmp_path, kind):
    assert submit_attack(tmp_path, kind)['verdict'] == 'PASS'


@pytest.mark.parametrize('kind', VIEW_CASES)
def test_counter_evidence_and_projection_cannot_be_silently_damaged(kind):
    assert view_attack(kind)['verdict'] == 'PASS'


@pytest.mark.parametrize('kind', READ_CASES)
def test_frozen_report_function_is_not_ref_authority(tmp_path, kind):
    assert session_attack(tmp_path, kind)['verdict'] == 'PASS'


def test_same_key_different_signed_intent_is_conflict(tmp_path):
    assert idempotency_attack(tmp_path)['denial'] == 409


def test_fixed_log_labels_do_not_accept_source_or_token_values():
    assert log_attack()['synthetic_sentinel_reflected'] is False


def test_nonexistent_http_is_blocked_instead_of_mock_pass():
    rows = http_gaps()
    assert len(rows) == 24 and all(row['verdict'] == 'BLOCKED' for row in rows)
    assert all(row['code'] == 'BLOCKED_PENDING_G1_IMPL' for row in rows)
    assert all('mock' not in row.get('realm', '').lower() for row in rows)


def test_source_replay_is_deterministic():
    for spec in (CASES[0], CASES[22], CASES[32]):
        first, again = execute(spec), execute(spec)
        assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)


@pytest.mark.parametrize('change', [{'mode': 'LIVE'}, {'public': True}, {'bind': '0.0.0.0'},
                                  {'model': 'PAID'}, {'expires': 0}])
def test_original_offline_synthetic_entry_cannot_become_live(change):
    policy = LocalPolicy('tenant-test', time.time()+60)
    policy.require('tenant-test')  # positive control of the accepted callable guard
    with pytest.raises(Denied):
        replace(policy, **change).require('tenant-test')
    with pytest.raises(PermissionError, match='LIVE_CAPTURE_DISABLED'):
        capture_live(approved=True)


def test_private_callable_cannot_accept_user_url_or_role_before_original_client():
    client = TaskClient(AppEndpoint('synthetic-key-not-live'.ljust(40, 'x'), 'tenant-test', frozenset(('accepted-404',))))
    adapter = PrivateAdapter(client, LocalPolicy('tenant-test', time.time()+60))
    for body in ({'url': 'http://169.254.169.254/'}, {'source_ref': 'accepted-404', 'tenant_id': 'tenant-beta'}):
        with pytest.raises(Denied, match='SERVER_REGISTERED_SOURCE_ONLY'):
            adapter.submit('tenant-test', body, 'g1-security-negative')
