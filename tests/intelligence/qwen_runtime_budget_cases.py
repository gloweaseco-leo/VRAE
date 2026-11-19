"""Real retained SQLite budget boundaries. No sockets, supplier or PG dependency."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import timedelta
import json
import sqlite3
import threading

import pytest
from integration.s3_offline.fixture import NOW
from vrae.intelligence.qwen import Config, Permission, Price, QwenError, Quota
from vrae.intelligence.qwen.provider import MODEL_SOURCE, INPUT_CAP, OUTPUT_RESERVE, digest

CONFIG = Config('synthetic-workspace')
PRICE = Price('TEST_ONLY_OFFICIAL_RATE', MODEL_SOURCE, 10_000_000, 30_000_000, NOW + timedelta(days=3))


def reserve(q, identity, now=NOW):
    permission = Permission('TEST_ONLY_' + identity, NOW + timedelta(days=2), 1, 2_000_000)
    q.reserve(identity, 'intent', config=CONFIG, permission=permission,
              price=PRICE, protocol_fake=True, now=now)


def test_shared_daily_ceiling_across_tasks_restart_and_unknown_day_rollover(tmp_path):
    path = tmp_path / 'q.sqlite'
    Quota(path, create=True)
    first = Quota(path, batch='task-first', daily_cap_micros=1_000_000)
    reserve(first, 'first')
    second = Quota(path, batch='task-second', daily_cap_micros=1_000_000)
    with pytest.raises(QwenError, match='DAILY_BUDGET_REFUSED'):
        reserve(second, 'second')
    with pytest.raises(QwenError, match='DAILY_BUDGET_REFUSED'):
        reserve(Quota(path, batch='task-next-day', daily_cap_micros=1_000_000),
                'nextday', NOW + timedelta(days=1))
    status = first.daily_status(NOW + timedelta(days=1))
    assert status['occupied_micros'] == PRICE.cost(INPUT_CAP, OUTPUT_RESERVE)
    assert status['actual_invoice'] == 'UNKNOWN'
    first.settle('first', 'intent', {'amount_micros': 10_000, 'recorded_at': NOW.isoformat(),
                                   'usage_origin': 'PROTOCOL_FAKE_NOT_REAL_API'})
    reserve(second, 'second')
    with pytest.raises(QwenError, match='OPERATION_ALREADY_RESERVED'):
        reserve(first, 'first')
    assert second.daily_status(NOW)['occupied_micros'] == 10_000 + PRICE.cost(INPUT_CAP, OUTPUT_RESERVE)


def test_legacy_unknown_and_same_day_usage_occupy_budget_without_rewriting_old_rows(tmp_path):
    path = tmp_path / 'q.sqlite'
    legacy = Quota(path, create=True)
    reserve(legacy, 'old-unknown')
    with sqlite3.connect(path) as db:
        before = db.execute('SELECT * FROM calls').fetchall()
        policy = db.execute('SELECT * FROM policy').fetchall()
    runtime = Quota(path, batch='new-runtime', daily_cap_micros=1_000_000)
    with pytest.raises(QwenError, match='DAILY_BUDGET_REFUSED'):
        reserve(runtime, 'new-call')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT * FROM calls').fetchall() == before
        assert db.execute('SELECT * FROM policy').fetchall() == policy
    legacy.settle('old-unknown', 'intent', {'amount_micros': 100_000,
        'recorded_at': NOW.isoformat(), 'usage_origin': 'PROTOCOL_FAKE_NOT_REAL_API'})
    assert runtime.daily_status(NOW)['occupied_micros'] == 100_000
    assert runtime.daily_status(NOW + timedelta(days=1))['occupied_micros'] == 0


def test_parallel_distinct_tasks_cannot_overdraw_shared_daily_reservation(tmp_path):
    path = tmp_path / 'q.sqlite'
    Quota(path, create=True)
    quotas = [Quota(path, batch='task-parallel-' + str(i), daily_cap_micros=1_000_000) for i in range(2)]
    barrier = threading.Barrier(2)
    def run(i):
        barrier.wait()
        try:
            reserve(quotas[i], 'parallel-' + str(i))
            return 'RESERVED'
        except QwenError as e:
            return str(e)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == ['DAILY_BUDGET_REFUSED', 'RESERVED']
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM calls').fetchone()[0] == 1


@pytest.mark.parametrize('cap', [True, 0, -1, 100_000_001])
def test_invalid_daily_limit_does_not_create_a_fresh_ledger(tmp_path, cap):
    path = tmp_path / 'q.sqlite'
    with pytest.raises(QwenError, match='DAILY_BUDGET_REQUIRED'):
        Quota(path, create=True, batch='task-invalid', daily_cap_micros=cap)
    assert not path.exists()


def test_old_permission_pin_bytes_remain_compatible(tmp_path):
    path = tmp_path / 'q.sqlite'
    quota = Quota(path, create=True)
    reserve(quota, 'old-policy')
    permission = Permission('TEST_ONLY_old-policy', NOW + timedelta(days=2), 1, 2_000_000)
    old_fields = {k: v for k, v in asdict(permission).items() if k != 'runtime_approval'}
    policy = {**old_fields, 'expires_at': permission.expires_at.isoformat(),
              'config': asdict(CONFIG), 'price': PRICE.document, 'protocol_fake': True}
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT pin FROM policy').fetchone()[0] == digest(policy)
    assert 'runtime_approval' not in json.dumps(policy, default=str)
