"""Explicit new grants append to one ledger; historical UNKNOWN stays intact."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import sqlite3

import pytest

from vrae.intelligence.qwen import Config, Permission, Price, Quota, QwenError
from vrae.intelligence.qwen.provider import MODEL_SOURCE


@pytest.fixture
def book(tmp_path):
    path = tmp_path / 'existing.sqlite'
    old = Quota(path, create=True)
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO policy VALUES (1, ?)', ('original-immutable-policy',))
        db.executemany('INSERT INTO calls VALUES (?, ?, ?, ?, NULL, ?)',
            [(f'old-{i}', f'intent-{i}', 147536, 'DISPATCHED_USAGE_UNKNOWN', 'ORIGINAL_ERROR') for i in range(3)])
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    options = dict(config=Config('synthetic-workspace'), protocol_fake=True,
        permission=Permission('TEST_NEW_EXPLICIT_OWNER_GRANT', expiry, 2, 6000000),
        price=Price('test-price', MODEL_SOURCE, 10000000, 30000000, expiry))
    return old, options


def original(path):
    with sqlite3.connect(path) as db:
        return db.execute('SELECT * FROM policy').fetchall(), db.execute(
            "SELECT * FROM calls WHERE id LIKE 'old-%' ORDER BY id").fetchall()


def test_new_batch_retains_original_rows_and_two_dispatch_cap_across_restart(book):
    old, opts = book
    before = original(old.path)
    new = Quota(old.path, batch='new-owner-grant')
    new.reserve('new-1', 'intent1', **opts)
    new.unknown('new-1', 'TIMEOUT')
    reopened = Quota(old.path, batch='new-owner-grant')
    reopened.reserve('new-2', 'intent2', **opts)
    with pytest.raises(QwenError, match='BUDGET_REFUSED'):
        reopened.reserve('new-3', 'intent3', **opts)
    assert original(old.path) == before
    assert reopened.dispatched('new-1') and reopened.receipt('new-1') is None


def test_same_approval_cannot_create_another_allowance(book):
    old, opts = book
    Quota(old.path, batch='new-owner-grant').reserve('new-1', 'intent1', **opts)
    with pytest.raises(QwenError, match='BATCH_APPROVAL_ALREADY_USED'):
        Quota(old.path, batch='different-batch-name').reserve('new-2', 'intent2', **opts)


def test_batch_cannot_rewrite_historical_unknown_or_change_its_pinned_price(book):
    old, opts = book
    before = original(old.path)
    new = Quota(old.path, batch='new-owner-grant')
    new.reserve('new-1', 'intent1', **opts)
    with pytest.raises(QwenError, match='QUOTA_BATCH_MISMATCH'):
        new.unknown('old-0', 'NEW_ERROR')
    with pytest.raises(QwenError, match='QUOTA_BATCH_MISMATCH'):
        new.settle('old-0', 'intent-0', {'amount_micros': 0})
    with pytest.raises(QwenError, match='QUOTA_POLICY_MISMATCH'):
        new.reserve('new-2', 'intent2', **{**opts, 'price':replace(opts['price'], input_micros_per_million=20000000)})
    assert original(old.path) == before


def test_batch_budget_and_global_operation_identity_are_fail_closed(book):
    old, opts = book
    new = Quota(old.path, batch='new-owner-grant')
    with pytest.raises(QwenError, match='BUDGET_REFUSED'):
        new.reserve('new-1', 'intent1', **{**opts, 'permission':replace(opts['permission'], cap_micros=1)})
    with pytest.raises(QwenError, match='OPERATION_ALREADY_RESERVED'):
        new.reserve('old-0', 'intent-0', **opts)
    assert len(original(old.path)[1]) == 3
