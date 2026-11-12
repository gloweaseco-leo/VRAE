"""Invocation-local synthetic reservations; exact micro-units, no invoices or global state."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Context, Decimal, ROUND_CEILING, localcontext
import re
from threading import RLock

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from .common import GatewayError, integer
from .provider import PROVIDER, MODEL
from .request import Scope


def decimal_value(value, places):
    if type(value) is not str or not re.fullmatch(r'(0|[1-9][0-9]{0,5})(\.[0-9]{1,' + str(places) + '})?', value):
        raise GatewayError('PRICE_OR_BUDGET_INVALID')
    number = Decimal(value)
    if not number.is_finite() or number <= 0:
        raise GatewayError('PRICE_OR_BUDGET_INVALID')
    return number


def stamp(value):
    try:
        if (type(value) is not str or len(value) > 40 or not re.fullmatch(
                r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})', value)
                or datetime.fromisoformat(value).utcoffset() is None):
            raise ValueError()
        return value
    except Exception as exc:
        raise GatewayError('RECORD_TIME_INVALID') from exc


@dataclass(frozen=True)
class PriceSnapshot:
    snapshot_id: str
    currency: str
    input_per_1000: str
    output_per_1000: str
    provider: str = PROVIDER
    model_id: str = MODEL

    def __post_init__(self):
        if any(type(v) is not str for v in (self.provider, self.model_id, self.currency)):
            raise GatewayError('PRICE_OR_BUDGET_INVALID')
        if self.provider != PROVIDER or self.model_id != MODEL:
            raise GatewayError('MODEL_PROVIDER_DISABLED')
        if self.currency not in ('CNY', 'USD'):
            raise GatewayError('CURRENCY_UNSUPPORTED')
        if type(self.snapshot_id) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,127}', self.snapshot_id):
            raise GatewayError('PRICE_OR_BUDGET_INVALID')
        decimal_value(self.input_per_1000, 9)
        decimal_value(self.output_per_1000, 9)

    @property
    def ref(self):
        return 'rate-' + document_hash(asdict(self))

    def cost(self, input_tokens, output_tokens):
        integer(input_tokens, 0, 1_000_000)
        integer(output_tokens, 0, 1_000_000)
        with localcontext(Context(prec=80)):
            value = (Decimal(self.input_per_1000) * input_tokens +
                     Decimal(self.output_per_1000) * output_tokens) * 1000
            return int(value.to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True)
class BudgetPolicy:
    currency: str
    cap_amount: str
    max_input_tokens: int = 16384
    max_output_tokens: int = 2048
    max_total_tokens: int = 65536
    max_operations: int = 16

    def __post_init__(self):
        if type(self.currency) is not str or self.currency not in ('CNY', 'USD'):
            raise GatewayError('CURRENCY_UNSUPPORTED')
        decimal_value(self.cap_amount, 6)
        integer(self.max_input_tokens, 1, 16384)
        integer(self.max_output_tokens, 1, 2048)
        integer(self.max_total_tokens, 1, 1_000_000)
        integer(self.max_operations, 1, 128)

    @property
    def cap_micros(self):
        with localcontext(Context(prec=80)):
            return int(Decimal(self.cap_amount) * 1_000_000)


class Ledger:
    """Single authoritative local instance; immutable checkpoints require a trusted latest pin."""
    def __init__(self, scope: Scope, policy: BudgetPolicy, price: PriceSnapshot | None):
        if type(scope) is not Scope or type(policy) is not BudgetPolicy or (price is not None and type(price) is not PriceSnapshot):
            raise GatewayError('ACCOUNTING_INTEGRITY')
        if price is not None and price.currency != policy.currency:
            raise GatewayError('CURRENCY_MISMATCH_NO_FX')
        self._scope, self._policy, self._price = scope, policy, price
        self._events: list[dict] = []
        self._lock = RLock()

    def _authorize(self, scope):
        if type(scope) is not Scope or scope != self._scope:
            raise GatewayError('ACCOUNTING_SCOPE_MISMATCH')

    def _reservation(self, event):
        return 'res-' + document_hash({'scope': asdict(self._scope), 'policy': asdict(self._policy),
            'rate_ref': self._price.ref if self._price else None,
            **{k: event[k] for k in ('operation_id', 'request_ref', 'input_bound', 'output_bound')}})

    def _fold(self, events):
        records: dict[str, dict] = {}
        for event in events:
            action, operation = event['action'], event['operation_id']
            if type(operation) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,127}', operation):
                raise GatewayError('ACCOUNTING_INTEGRITY')
            if action == 'RESERVE':
                if set(event) != {'action', 'operation_id', 'request_ref', 'input_bound', 'output_bound', 'reservation_ref'}:
                    raise GatewayError('ACCOUNTING_INTEGRITY')
                if self._price is None:
                    raise GatewayError('PRICE_UNKNOWN')
                if any(r['state'] == 'UNKNOWN' for r in records.values()):
                    raise GatewayError('USAGE_UNKNOWN_QUARANTINE')
                if (operation in records or any(r['request_ref'] == event['request_ref']
                        and r['state'] != 'RELEASED' for r in records.values())):
                    raise GatewayError('DUPLICATE_OPERATION_OR_REQUEST')
                if len(records) >= self._policy.max_operations:
                    raise GatewayError('OPERATION_LIMIT')
                if type(event['request_ref']) is not str or not re.fullmatch(r'req-[0-9a-f]{64}', event['request_ref']):
                    raise GatewayError('ACCOUNTING_INTEGRITY')
                i = integer(event['input_bound'], 1, self._policy.max_input_tokens)
                o = integer(event['output_bound'], 1, self._policy.max_output_tokens)
                if event['reservation_ref'] != self._reservation(event):
                    raise GatewayError('ACCOUNTING_INTEGRITY')
                records[operation] = {**event, 'state': 'RESERVED', 'reserved_micros': self._price.cost(i, o),
                                      'spent_micros': 0, 'input_tokens': None, 'output_tokens': None}
            else:
                if operation not in records or event['reservation_ref'] != records[operation]['reservation_ref']:
                    raise GatewayError('ACCOUNTING_INTEGRITY')
                row = records[operation]
                keys = {'action', 'operation_id', 'reservation_ref'}
                if action == 'START' and row['state'] == 'RESERVED':
                    if any(r['state'] == 'UNKNOWN' for r in records.values()):
                        raise GatewayError('USAGE_UNKNOWN_QUARANTINE')
                    row['state'] = 'IN_FLIGHT'
                elif action == 'RELEASE' and row['state'] == 'RESERVED':
                    row['state'] = 'RELEASED'
                elif action == 'COMMIT' and row['state'] == 'IN_FLIGHT':
                    keys |= {'input_tokens', 'output_tokens'}
                    i = integer(event['input_tokens'], 0, row['input_bound'])
                    o = integer(event['output_tokens'], 0, row['output_bound'])
                    assert self._price is not None
                    row.update(state='COMMITTED', input_tokens=i, output_tokens=o,
                               spent_micros=self._price.cost(i, o))
                    if 'response_ref' in event:
                        keys |= {'response_ref'}
                        if type(event['response_ref']) is not str or not re.fullmatch(r'response-[0-9a-f]{64}', event['response_ref']):
                            raise GatewayError('ACCOUNTING_INTEGRITY')
                        row['response_ref'] = event['response_ref']
                elif action == 'UNKNOWN' and (row['state'] == 'IN_FLIGHT' or
                        (row['state'] == 'RESERVED' and event.get('reason') == 'INTERRUPTED')):
                    keys |= {'reason'}
                    if event['reason'] not in ('PROVIDER_ERROR', 'CANCELLED', 'TIMEOUT', 'MALFORMED_REPLY',
                                              'USAGE_UNKNOWN', 'INVALID_USAGE', 'OUTPUT_BOUND', 'INTERRUPTED'):
                        raise GatewayError('ACCOUNTING_INTEGRITY')
                    row.update(state='UNKNOWN', reason=event['reason'])
                else:
                    raise GatewayError('ACCOUNTING_TRANSITION_REFUSED')
                if set(event) != keys:
                    raise GatewayError('ACCOUNTING_INTEGRITY')
            spent = sum(r['spent_micros'] for r in records.values())
            held = sum(r['reserved_micros'] for r in records.values() if r['state'] in ('RESERVED', 'IN_FLIGHT', 'UNKNOWN'))
            tokens = sum((r['input_tokens'] + r['output_tokens']) if r['state'] == 'COMMITTED' else
                (r['input_bound'] + r['output_bound']) if r['state'] in ('RESERVED', 'IN_FLIGHT', 'UNKNOWN') else 0
                for r in records.values())
            if spent + held > self._policy.cap_micros or tokens > self._policy.max_total_tokens:
                raise GatewayError('BUDGET_EXCEEDED')
        return records

    def _append(self, scope, event):
        self._authorize(scope)
        if len(self._events) >= 512:
            raise GatewayError('JOURNAL_BOUND')
        try:
            records = self._fold([*self._events, event])
        except GatewayError:
            raise
        except Exception as exc:
            raise GatewayError('ACCOUNTING_INTEGRITY') from exc
        self._events.append(deepcopy(event))
        return deepcopy(records[event['operation_id']])

    def reserve(self, scope, operation_id, request_ref, input_bound, output_bound):
        with self._lock:
            self._authorize(scope)
            integer(input_bound, 1, self._policy.max_input_tokens)
            integer(output_bound, 1, self._policy.max_output_tokens)
            if (type(operation_id) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,127}', operation_id)
                    or type(request_ref) is not str or not re.fullmatch(r'req-[0-9a-f]{64}', request_ref)):
                raise GatewayError('ACCOUNTING_INTEGRITY')
            event = dict(action='RESERVE', operation_id=operation_id, request_ref=request_ref,
                         input_bound=input_bound, output_bound=output_bound)
            event['reservation_ref'] = self._reservation(event)
            return self._append(scope, event)

    def update(self, scope, operation_id, reservation_ref, action, **details):
        with self._lock:
            return self._append(scope, dict(action=action, operation_id=operation_id,
                                           reservation_ref=reservation_ref, **details))

    def record(self, scope, operation_id):
        with self._lock:
            self._authorize(scope)
            records = self._fold(self._events)
            if operation_id not in records:
                raise GatewayError('OPERATION_UNKNOWN')
            return deepcopy(records[operation_id])

    def snapshot(self):
        with self._lock:
            rows = self._fold(self._events)
            result = {'version': 'ra3a-ledger-1.0.0', 'scope': asdict(self._scope),
                'policy': asdict(self._policy), 'price': asdict(self._price) if self._price else None,
                'events': deepcopy(self._events), 'records': rows, 'synthetic_only': True,
                'external_invoice': None, 'reconciled': False,
                'spent_micros': sum(r['spent_micros'] for r in rows.values()),
                'held_micros': sum(r['reserved_micros'] for r in rows.values()
                                  if r['state'] in ('RESERVED', 'IN_FLIGHT', 'UNKNOWN'))}
            result['ledger_ref'] = 'ledger-' + document_hash(result)
            return result

    @classmethod
    def restore(cls, snapshot, *, expected_ledger_ref, scope, policy, price):
        try:
            if type(expected_ledger_ref) is not str or not re.fullmatch(r'ledger-[0-9a-f]{64}', expected_ledger_ref):
                raise ValueError()
            ledger = cls(scope, policy, price)
            if type(snapshot['events']) is not list or len(snapshot['events']) > 512:
                raise ValueError()
            ledger._fold(snapshot['events'])  # Check bounded event primitives before copying.
            ledger._events = deepcopy(snapshot['events'])
            rebuilt = ledger.snapshot()
            if snapshot != rebuilt or rebuilt['ledger_ref'] != expected_ledger_ref:
                raise ValueError()
            # A recovered dispatch without a receipt is not retried or released as free.
            for op, row in rebuilt['records'].items():
                if row['state'] in ('RESERVED', 'IN_FLIGHT'):
                    ledger.update(scope, op, row['reservation_ref'], 'UNKNOWN', reason='INTERRUPTED')
            return ledger
        except Exception as exc:
            raise GatewayError('ACCOUNTING_INTEGRITY') from exc

    def usage(self, scope, operation_id, recorded_at):
        row = self.record(scope, operation_id)
        known = row['state'] == 'COMMITTED'
        with localcontext(Context(prec=80)):
            amount = float(Decimal(row['spent_micros']) / 1_000_000) if known else None
        result = dict(schema_version='1.0', tenant_id=scope.tenant_id, run_id=scope.run_id,
            usage_id='usage-' + document_hash({'operation': operation_id, 'scope': asdict(scope),
                                             'reservation': row['reservation_ref']}),
            cost_type='MODEL', provider=PROVIDER, model_id=MODEL,
            input_tokens=row['input_tokens'] if known else None,
            output_tokens=row['output_tokens'] if known else None, amount=amount,
            currency=self._policy.currency, cost_status='ESTIMATED' if known else 'UNKNOWN',
            recorded_at=stamp(recorded_at))
        validate_contract('UsageRecord', result)
        return result
