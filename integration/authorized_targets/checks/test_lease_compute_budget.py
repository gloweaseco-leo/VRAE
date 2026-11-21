"""No website or model calls: preserve replay integrity and original lease."""
from copy import deepcopy
from datetime import datetime, UTC, timedelta
from types import SimpleNamespace

import pytest

from integration.authorized_targets import worker
from integration.authorized_targets.checks.test_inventory_budget import scoped, grant  # noqa: F401,F811
from tests.s2_contract.batch2_fixtures import fixture
from vrae.industry.l2_v1.diagnose import source_chain
from vrae.rules import patch_execution as rules
from vrae.rules.replay_scope import execution_scope
from vrae.collection.errors import CollectionError


def test_production_reuses_only_identical_pack_and_returns_detached_rows(monkeypatch):
    pack, other = fixture(), fixture()
    original = rules._execute
    calls = []

    def compute(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(rules, '_execute', compute)
    def run(p):
        return rules.execute(p, expected_pack_ref=p.ref, evaluator_version=rules.CONTEXT_VERSION)
    with execution_scope(pack):
        first = run(pack)
        expected = deepcopy(first)
        first['executions'][0]['observations'][0]['reason'] = 'FORGED'
        assert run(pack) == expected
        with pytest.raises(Exception):
            rules.verify_execution(first, pack, expected_pack_ref=pack.ref,
                                   expected_evaluator_version=rules.CONTEXT_VERSION)
        with pytest.raises(Exception):
            rules.execute(pack, expected_pack_ref='ep-'+'0'*64,
                          evaluator_version=rules.CONTEXT_VERSION)
        assert len(calls) == 1
        run(other)
        assert len(calls) == 2
        # Full Finding/Guard consumers still compare their rows and claims.
        a = source_chain(pack, pack.ref, diagnostic_version='l2-industrial-1.0.5')
        b = source_chain(pack, pack.ref, diagnostic_version='l2-industrial-1.0.5')
        assert a[0] == b[0] == expected and a[2:] == b[2:]
        assert len(calls) == 2
    assert run(pack) == expected and len(calls) == 3
    with execution_scope(pack):
        assert run(pack) == expected and len(calls) == 4


def test_scope_is_cleared_after_failure_and_pack_mutation_is_not_reused():
    pack = fixture()
    payload = pack._payload
    with pytest.raises(Exception):
        with execution_scope(pack):
            rules.execute(pack, expected_pack_ref=pack.ref, evaluator_version=rules.CONTEXT_VERSION)
            object.__setattr__(pack, '_payload', b'{}')
            rules.execute(pack, expected_pack_ref='ep-'+'0'*64, evaluator_version=rules.CONTEXT_VERSION)
    object.__setattr__(pack, '_payload', payload)
    assert rules.execute(pack, expected_pack_ref=pack.ref,
                         evaluator_version=rules.CONTEXT_VERSION)['execution_ref'].startswith('rx-')


@pytest.mark.parametrize('change', ['policy', 'signing_key', 'expiry'])
def test_each_authority_check_reloads_and_denies_revocation(scoped, change):  # noqa: F811
    access, counts, policy, registry = scoped
    access.check(access.start_url)
    assert counts == {'pg': 1, 'current': 1}
    if change == 'policy':
        policy['revoked_at'] = datetime.now(UTC).isoformat()
    elif change == 'signing_key':
        registry['keys']['admin']['revoked'] = True
    else:
        access.now = lambda: datetime.now(UTC) + timedelta(days=1)
    with pytest.raises(Exception):
        access.check(access.start_url)
    assert counts['current'] == 2


def test_capture_window_expiry_is_bounded_timeout_with_live_source_grant(scoped):  # noqa: F811
    from dataclasses import replace
    access, counts, _, registry = scoped
    access.permit = replace(access.permit, expires_at=datetime.now(UTC)-timedelta(seconds=1))
    with pytest.raises(CollectionError, match='TIMEOUT'):
        access.check(access.start_url)
    registry['keys']['admin']['revoked'] = True
    with pytest.raises(PermissionError):
        access.check(access.start_url)
    assert counts['current'] == 2


def test_slow_capture_keeps_evidence_and_finishes_inside_original_lease(monkeypatch):
    start = datetime(2026, 11, 21, tzinfo=UTC)
    elapsed = [0.0]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return start + timedelta(seconds=elapsed[0])

    monkeypatch.setattr(worker, 'datetime', Clock)
    monkeypatch.setattr(worker, 'time', SimpleNamespace(monotonic=lambda: elapsed[0]))
    task = {'request_id': 'request-fixture', 'run_id': 'run-fixture'}
    plan = {'automatic_result': True, 'limits': {'max_pages': 6, 'task_seconds': 24},
            'policy': {'authorization_reference': 'fixture'}}
    loaded = {'task': task, 'plan': plan, 'submission': {'command': {'request': {}}},
              'loaded_at': start.isoformat()}
    observed = {}

    def capture(audit, policy, plan, run_id, workload, current):
        # Six slow pages would consume 24s, leaving no time for a 6s report.
        budget = min(plan['limits']['task_seconds'], workload['task_seconds'])
        count = min(6, int(budget // 4))
        elapsed[0] += count * 4
        observed['pages'] = count
        return SimpleNamespace(manifest={'errors': [], 'pages': [
            {'snapshot': {'status': 'FETCHED'}} for _ in range(count)]})

    def produce(*args, **kwargs):
        elapsed[0] += 6
        return {'pack_ref': 'fixture', 'diagnosis': {'source_facts': []},
                'native_document': {'findings': [], 'blueprint': []}}

    class Port:
        def call(self, name, *args):
            if name == 'load':
                return loaded
            assert name == 'commit'
            elapsed[0] += 1
            assert elapsed[0] < 30, 'ORIGINAL_LEASE_EXPIRED'
            observed['committed'] = True
            return '1'*64

    monkeypatch.setattr(worker, 'capture', capture)
    monkeypatch.setattr(worker, 'produce_capture', produce)
    result = worker.execute({'tenant_id': 'fixture'}, {}, Port(),
        ('job-fixture', 'run-fixture', 'lease-token', 1, start+timedelta(seconds=30)))
    assert observed == {'pages': 4, 'committed': True}
    assert result['artifact_sha256'] and elapsed[0] == 23


def test_exhausted_finish_budget_never_starts_network(monkeypatch):
    start = datetime(2026, 11, 21, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return start

    monkeypatch.setattr(worker, 'datetime', Clock)
    monkeypatch.setattr(worker, 'capture', lambda *a, **k: pytest.fail('NO_CAPTURE_BUDGET'))
    loaded = {'task': {'request_id': 'request-fixture', 'run_id': 'run-fixture'},
              'plan': {'automatic_result': True}, 'submission': {'command': {'request': {}}}}
    port = SimpleNamespace(call=lambda *a: loaded)
    with pytest.raises(ValueError, match='ORIGINAL_LEASE_BUDGET_EXHAUSTED'):
        worker.execute({'tenant_id': 'fixture'}, {}, port,
            ('job-fixture', 'run-fixture', 'lease-token', 1, start+timedelta(seconds=10)))


@pytest.mark.parametrize('setup_seconds', [5, 19])
def test_component_setup_cannot_extend_capture_deadline(monkeypatch, setup_seconds):
    from integration.authorized_targets import capture as runtime
    start = datetime(2026, 11, 21, tzinfo=UTC)
    elapsed = [0]
    deadline = start+timedelta(seconds=18)
    seen = []

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return start+timedelta(seconds=elapsed[0])

    def components(*args):
        elapsed[0] += setup_seconds
        return None, None

    class Collector:
        def __init__(self, *a, **k):
            pass

        async def capture(self, *a, **k):
            seen.append(True)
            assert Clock.now()+timedelta(seconds=k['limits'].task_seconds) <= deadline
            return SimpleNamespace(verify=lambda: None)

    monkeypatch.setattr(runtime, 'datetime', Clock)
    monkeypatch.setattr(runtime, 'components', components)
    monkeypatch.setattr(runtime, 'Collector', Collector)
    def call():
        return runtime.capture({}, None, {'limits': {'task_seconds': 24},
            'retain_raw_html': True}, 'run-fixture', {'deadline': deadline.isoformat(), 'task_seconds': 18})
    if setup_seconds > 18:
        with pytest.raises(CollectionError, match='TIMEOUT'):
            call()
        assert not seen
    else:
        call()
        assert seen
