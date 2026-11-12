"""Replay accepted C3 evidence through an offline fake gateway, with synthetic audit only."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from tests.intelligence.synthetic import accepted_input, PIN  # noqa: E402
from vrae.intelligence import (BudgetPolicy, FixtureProvider, InputPins, Ledger, ModelGateway,  # noqa: E402
    PriceSnapshot, Scope, prepare_request, verify_accounting_audit)

WHEN = '2026-11-11T00:00:00+00:00'
FIXTURE = root / 'tests/intelligence/fixtures/ra3a-offline-demo.json'


async def demonstrate():
    pack, execution, package = accepted_input()
    scope = Scope(**{k:pack.document[k] for k in ('tenant_id','run_id','policy_id','policy_version')})
    pins = InputPins(**PIN, scope=scope)
    request_pin = prepare_request(pack, execution, package, pins=pins).ref
    policy = BudgetPolicy('CNY', '1.00')  # Synthetic demonstration, not live-budget authorization.
    rate = PriceSnapshot('ra3a-demo-fixed-rate', 'CNY', '0.01', '0.02')

    async def invoke(provider, book, operation, **options):
        return await ModelGateway(provider=provider, ledger=book).run(pack, execution, package,
            pins=pins, operation_id=operation, recorded_at=WHEN, **options)

    no_model = await invoke(None, None, 'demo-no-model')
    book = Ledger(scope, policy, rate)
    complete = await invoke(FixtureProvider(), book, 'demo-fake')
    repeated = await invoke(FixtureProvider(), book, 'demo-fake')
    assert repeated['usage'] == complete['usage'] and repeated['ledger'] == complete['ledger']
    verify_accounting_audit(complete, expected_request_ref=request_pin,
        expected_ledger_ref=book.snapshot()['ledger_ref'], expected_recorded_at=WHEN,
        scope=scope, policy=policy, price=rate)
    restored = Ledger.restore(book.snapshot(), expected_ledger_ref=book.snapshot()['ledger_ref'],
                              scope=scope, policy=policy, price=rate)
    assert restored.snapshot() == book.snapshot()
    unknown_book = Ledger(scope, policy, rate)
    missing_usage = await invoke(FixtureProvider(behavior='missing_usage'), unknown_book, 'demo-missing-usage')
    blocked_retry = await invoke(FixtureProvider(), unknown_book, 'demo-retry')
    assert blocked_retry['code'] == 'USAGE_UNKNOWN_QUARANTINE' and blocked_retry['fixture_calls'] == 0
    assert unknown_book.snapshot()['held_micros'] > 0
    verify_accounting_audit(missing_usage, expected_request_ref=request_pin,
        expected_ledger_ref=unknown_book.snapshot()['ledger_ref'], expected_recorded_at=WHEN,
        scope=scope, policy=policy, price=rate)
    no_price = await invoke(FixtureProvider(), Ledger(scope, policy, None), 'demo-price-unknown')
    rollback_book = Ledger(scope, policy, rate)
    rollback = await invoke(FixtureProvider(), rollback_book, 'demo-before-send', cancel_before_dispatch=True)
    assert rollback_book.snapshot()['held_micros'] == rollback_book.snapshot()['spent_micros'] == 0
    assert complete['status'] == 'FAKE_COMPLETED_UNVALIDATED' and complete['usage']['cost_status'] == 'ESTIMATED'
    assert missing_usage['usage']['cost_status'] == 'UNKNOWN' and no_price['code'] == 'PRICE_UNKNOWN'
    cases = {'default_no_model': no_model, 'fake_complete': complete, 'repeat_same_operation': repeated,
             'missing_usage': missing_usage, 'quarantined_retry': blocked_retry,
             'unknown_price': no_price, 'pre_dispatch_rollback': rollback}
    for result in cases.values():
        assert result['real_model_calls'] == result['real_token_charges'] == 0
        assert result['interpretation']['status'] == 'NOT_RUN'
        assert result['interpretation']['hypotheses'] == result['interpretation']['recommendations'] == []
        assert result['private'] is True and result['shareable'] is False
    provider = complete['request']['provider_request']
    payload = json.dumps(provider)
    for forbidden in ('SV Industrial Valve Works', 'mailto:', 'sales@', 'https://', '<html'):
        assert forbidden not in payload
    return {'status': 'RA3A_OFFLINE_ADAPTER_READY_CANDIDATE', 'source_pins': PIN,
        'independent_request_pin': request_pin,
        'admission': 'RA3_OFFLINE_ENGINEERING_GO', 'live_provider': 'DISABLED',
        'real_model_calls': 0, 'real_token_charges': 0, 'report_or_share': False,
        'gold': 'OWNER_AUTHORIZED_GOLD_DEFERRED_0_OF_26_QUALITY_GATE_NOT_EVALUABLE',
        'limits': ['SYNTHETIC_PRICES_NOT_REAL_INVOICE', 'UTF8_BYTE_UNITS_NOT_LIVE_TOKENIZER',
            'NO_SOURCE_FREE_TEXT_SENT_TO_PROVIDER', 'RA3B_CLAIM_VALIDATION_NOT_IMPLEMENTED',
            'SINGLE_LOCAL_LEDGER_NOT_DISTRIBUTED_BILLING', 'TRUSTED_LATEST_CHECKPOINT_PIN_REQUIRED',
            'UNKNOWN_USAGE_QUARANTINED_NO_AUTOMATIC_RETRY', 'NO_CUSTOMER_REPORT_OR_RA3CD'],
        'provider_request': provider, 'cases': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-example', action='store_true', help='Write only new intelligence synthetic demo.')
    args = parser.parse_args()
    result = asyncio.run(demonstrate())
    if args.write_example:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    assert result == json.loads(FIXTURE.read_text(encoding='utf-8'))
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
