from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from decimal import localcontext, ROUND_DOWN

import pytest

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.intelligence import BudgetPolicy, GatewayError, Ledger, PriceSnapshot, Scope

SCOPE = Scope('tenant-a', 'run-synthetic', 'policy-synthetic', 1)
RATE = PriceSnapshot('fixture-price-1', 'CNY', '1.0', '1.0')
WHEN = '2026-11-11T00:00:00+00:00'


def request(number=1):
    return 'req-' + document_hash({'request': number})


def ledger(cap='1.0', price=RATE, **kwargs):
    return Ledger(SCOPE, BudgetPolicy('CNY', cap, **kwargs), price)


@pytest.mark.parametrize('value', ['0', '-1', 'NaN', 'Infinity', '1e2', '0.0000001',
    '1000000', '', ' 1', '1 ', None, True, 0.1])
def test_bad_budget_never_becomes_executable_zero_or_rounded_authorization(value):
    with pytest.raises(GatewayError):
        BudgetPolicy('CNY', value)


@pytest.mark.parametrize('value', ['0', '-1', 'NaN', 'Infinity', '1e2', '0.0000000001',
    '1000000', '', None, True, 0.01])
def test_unknown_or_invalid_rates_refused(value):
    with pytest.raises(GatewayError):
        PriceSnapshot('rate-fixed', 'CNY', value, '0.1')


def test_currency_and_price_snapshot_never_perform_implicit_fx():
    for currency in ('JPY', 'RMB', None, 'usd'):
        with pytest.raises(GatewayError):
            BudgetPolicy(currency, '1.0')
    with pytest.raises(GatewayError):
        Ledger(SCOPE, BudgetPolicy('USD', '1.0'), RATE)
    book = ledger(price=None)
    with pytest.raises(GatewayError, match='PRICE_UNKNOWN'):
        book.reserve(SCOPE, 'op-one', request(), 1, 1)
    assert book.snapshot()['records'] == {}


def test_round_up_micro_units_and_smallest_known_rate_are_not_silently_free():
    rate = PriceSnapshot('rate-tiny', 'USD', '0.000000001', '0.000000001')
    assert rate.cost(1, 0) == rate.cost(1, 1) == 1
    assert rate.cost(0, 0) == 0  # Explicit known zero usage, not missing usage.
    assert RATE.cost(1, 1) == 2000
    assert RATE.ref != replace(RATE, input_per_1000='1.1').ref


def test_ambient_decimal_context_cannot_change_cost_or_budget():
    with localcontext() as context:
        context.prec = 2
        context.Emax = 2
        context.Emin = -2
        context.rounding = ROUND_DOWN
        assert RATE.cost(1, 1) == 2000
        assert BudgetPolicy('CNY', '1.0').cap_micros == 1000000


@pytest.mark.parametrize('input_tokens,output_tokens', [(-1, 1), (True, 1), (1, -1), (1, False),
    (float('nan'), 1), (float('inf'), 1), (10**30, 1), (1, None)])
def test_negative_nonfinite_overflow_usage_and_bounds_rejected(input_tokens, output_tokens):
    with pytest.raises(GatewayError):
        RATE.cost(input_tokens, output_tokens)
    with pytest.raises(GatewayError):
        ledger().reserve(SCOPE, 'op-test', request(), input_tokens, output_tokens)


def test_reserve_commit_unused_reservation_release_and_double_spend_guards():
    book = ledger('0.2')
    reserved = book.reserve(SCOPE, 'op-one', request(), 50, 50)
    ref = reserved['reservation_ref']
    assert book.snapshot()['held_micros'] == 100000
    book.update(SCOPE, 'op-one', ref, 'START')
    book.update(SCOPE, 'op-one', ref, 'COMMIT', input_tokens=20, output_tokens=10)
    snap = book.snapshot()
    assert snap['spent_micros'] == 30000 and snap['held_micros'] == 0
    usage = book.usage(SCOPE, 'op-one', WHEN)
    validate_contract('UsageRecord', usage)
    assert usage['cost_status'] == 'ESTIMATED' and usage['amount'] == 0.03
    for action in ('START', 'RELEASE', 'COMMIT', 'UNKNOWN'):
        with pytest.raises(GatewayError):
            book.update(SCOPE, 'op-one', ref, action)
        assert book.snapshot() == snap
    for op, req in [('op-one', request(2)), ('op-other', request())]:
        with pytest.raises(GatewayError, match='DUPLICATE'):
            book.reserve(SCOPE, op, req, 10, 10)


def test_pre_dispatch_rollback_allows_new_attempt_but_not_old_operation_replay():
    book = ledger('0.1')
    row = book.reserve(SCOPE, 'op-before', request(), 50, 50)
    book.update(SCOPE, 'op-before', row['reservation_ref'], 'RELEASE')
    assert book.snapshot()['held_micros'] == book.snapshot()['spent_micros'] == 0
    assert book.usage(SCOPE, 'op-before', WHEN)['cost_status'] == 'UNKNOWN'
    with pytest.raises(GatewayError):
        book.reserve(SCOPE, 'op-before', request(), 50, 50)
    book.reserve(SCOPE, 'op-retry', request(), 50, 50)
    assert book.snapshot()['held_micros'] == 100000


def test_unknown_after_dispatch_holds_liability_blocks_execution_and_survives_restore():
    book = ledger('0.2')
    row = book.reserve(SCOPE, 'op-unknown', request(), 50, 50)
    book.update(SCOPE, 'op-unknown', row['reservation_ref'], 'START')
    book.update(SCOPE, 'op-unknown', row['reservation_ref'], 'UNKNOWN', reason='USAGE_UNKNOWN')
    snap = book.snapshot()
    assert snap['held_micros'] == 100000 and snap['spent_micros'] == 0
    usage = book.usage(SCOPE, 'op-unknown', WHEN)
    assert usage['cost_status'] == 'UNKNOWN' and usage['amount'] is usage['input_tokens'] is None
    for candidate in (book, Ledger.restore(snap, expected_ledger_ref=snap['ledger_ref'],
        scope=SCOPE, policy=BudgetPolicy('CNY', '0.2'), price=RATE)):
        with pytest.raises(GatewayError, match='QUARANTINE'):
            candidate.reserve(SCOPE, 'op-next', request(2), 1, 1)
        with pytest.raises(GatewayError):
            candidate.update(SCOPE, 'op-unknown', row['reservation_ref'], 'RELEASE')


def test_interrupted_dispatch_recovers_to_unknown_never_a_free_retry():
    book = ledger()
    row = book.reserve(SCOPE, 'op-crash', request(), 50, 50)
    book.update(SCOPE, 'op-crash', row['reservation_ref'], 'START')
    snap = book.snapshot()
    restored = Ledger.restore(snap, expected_ledger_ref=snap['ledger_ref'],
        scope=SCOPE, policy=BudgetPolicy('CNY', '1.0'), price=RATE)
    assert restored.record(SCOPE, 'op-crash')['state'] == 'UNKNOWN'
    assert restored.record(SCOPE, 'op-crash')['reason'] == 'INTERRUPTED'
    assert restored.snapshot()['held_micros'] == snap['held_micros']


def test_unfinished_pre_dispatch_checkpoint_is_conservatively_unknown_after_restart():
    book = ledger()
    row = book.reserve(SCOPE, 'op-checkpoint', request(), 10, 10)
    snap = book.snapshot()
    restored = Ledger.restore(snap, expected_ledger_ref=snap['ledger_ref'],
        scope=SCOPE, policy=BudgetPolicy('CNY', '1.0'), price=RATE)
    assert restored.record(SCOPE, 'op-checkpoint')['state'] == 'UNKNOWN'
    with pytest.raises(GatewayError):
        restored.update(SCOPE, 'op-checkpoint', row['reservation_ref'], 'RELEASE')


@pytest.mark.parametrize('field,value', [('tenant_id', 'tenant-other'), ('run_id', 'run-other'),
    ('policy_id', 'policy-other'), ('policy_version', 2)])
def test_scope_cannot_reserve_start_commit_or_read_another_ledger(field, value):
    book = ledger()
    row = book.reserve(SCOPE, 'op-scope', request(), 1, 1)
    wrong = replace(SCOPE, **{field: value})
    snap = book.snapshot()
    with pytest.raises(GatewayError):
        book.reserve(wrong, 'op-other', request(2), 1, 1)
    with pytest.raises(GatewayError):
        book.update(wrong, 'op-scope', row['reservation_ref'], 'START')
    with pytest.raises(GatewayError):
        book.record(wrong, 'op-scope')
    assert book.snapshot() == snap


def test_parallel_admission_and_commit_are_atomic():
    book = ledger('0.2')

    def reserve(i):
        try:
            return book.reserve(SCOPE, f'op-{i}', request(i), 50, 50)
        except GatewayError:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = [r for r in pool.map(reserve, range(8)) if r]
    assert len(rows) == 2 and book.snapshot()['held_micros'] == 200000
    row = rows[0]
    book.update(SCOPE, row['operation_id'], row['reservation_ref'], 'START')

    def commit(_):
        try:
            book.update(SCOPE, row['operation_id'], row['reservation_ref'], 'COMMIT', input_tokens=50, output_tokens=50)
            return True
        except GatewayError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(commit, range(8))) == 1
    assert book.snapshot()['spent_micros'] == book.snapshot()['held_micros'] == 100000


@pytest.mark.parametrize('mutation', ['balance', 'event', 'scope', 'rate', 'state', 'reconciled', 'extra'])
def test_checkpoint_rehash_is_not_a_trusted_pin_or_external_bill(mutation):
    book = ledger()
    book.reserve(SCOPE, 'op-tamper', request(), 10, 10)
    original = book.snapshot()
    changed = deepcopy(original)
    if mutation == 'balance':
        changed['held_micros'] = 0
    elif mutation == 'event':
        changed['events'][0]['input_bound'] = 1
    elif mutation == 'scope':
        changed['scope']['run_id'] = 'run-other'
    elif mutation == 'rate':
        changed['price']['input_per_1000'] = '0'
    elif mutation == 'state':
        changed['records']['op-tamper']['state'] = 'RELEASED'
    elif mutation == 'reconciled':
        changed['reconciled'] = True
    else:
        changed['external_invoice'] = 'fictional-bill'
    changed['ledger_ref'] = 'ledger-' + document_hash({k:v for k,v in changed.items() if k != 'ledger_ref'})
    with pytest.raises(GatewayError):
        Ledger.restore(changed, expected_ledger_ref=original['ledger_ref'],
            scope=SCOPE, policy=BudgetPolicy('CNY', '1.0'), price=RATE)
    assert book.snapshot() == original


def test_token_and_operation_caps_survive_refunds_and_known_snapshot_restore():
    book = ledger(max_total_tokens=20, max_operations=1)
    with pytest.raises(GatewayError, match='BUDGET_EXCEEDED'):
        book.reserve(SCOPE, 'op-too-many', request(), 15, 6)
    row = book.reserve(SCOPE, 'op-one', request(), 10, 10)
    book.update(SCOPE, 'op-one', row['reservation_ref'], 'RELEASE')
    snap = book.snapshot()
    restored = Ledger.restore(snap, expected_ledger_ref=snap['ledger_ref'], scope=SCOPE,
        policy=BudgetPolicy('CNY', '1.0', max_total_tokens=20, max_operations=1), price=RATE)
    with pytest.raises(GatewayError, match='OPERATION_LIMIT'):
        restored.reserve(SCOPE, 'op-next', request(2), 1, 1)
