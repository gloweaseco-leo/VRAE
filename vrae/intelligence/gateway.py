"""Offline-only dispatch: independently prepared input, reserved costs, unvalidated output."""
import asyncio
import re
from dataclasses import asdict

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from .accounting import Ledger, stamp
from .common import GatewayError, integer
from .provider import FixtureProvider, OfflineProvider, ProviderReply, PROVIDER, MODEL
from .request import InputPins, prepare_request


class ModelGateway:
    def __init__(self, *, provider: OfflineProvider | None = None, ledger: Ledger | None = None,
                 provider_name: str | None = None, model_id: str | None = None, credentials: object = None):
        self._provider = provider if type(provider) is FixtureProvider else None
        self._ledger = ledger if type(ledger) is Ledger else None
        self._disabled = (credentials is not None or type(provider_name) not in (str, type(None))
            or type(model_id) not in (str, type(None)) or provider_name not in (None, 'NO_MODEL', PROVIDER)
            or model_id not in (None, MODEL) or (provider is not None and type(provider) is not FixtureProvider)
            or (provider_name == PROVIDER and provider is None))
        self._no_model = provider is None or (type(provider_name) is str and provider_name == 'NO_MODEL')

    async def run(self, pack, execution, package, *, pins: InputPins, operation_id: str, recorded_at: str,
                  max_output_tokens=256, timeout_ms=1000, cancel_before_dispatch=False):
        base = dict(version='ra3a-gateway-1.0.0', private=True, approval_status='NOT_APPROVED',
            shareable=False, synthetic_only=True, real_model_calls=0, real_token_charges=0,
            fixture_calls=0, provider_output=None, output_status='UNVALIDATED_NOT_AN_INTERPRETATION',
            billing_origin='SYNTHETIC_ONLY_NOT_PROVIDER_INVOICE', usage=None, interpretation=None,
            token_basis='SYNTHETIC_UTF8_BYTES_NOT_PROVIDER_TOKENIZER',
            operation_id=None, request=None, ledger=None)
        try:
            request = prepare_request(pack, execution, package, pins=pins)
            base['request'] = request.document
            stamp(recorded_at)
            if type(operation_id) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,127}', operation_id):
                raise GatewayError('OPERATION_INVALID')
        except Exception:
            return {**base, 'status': 'REFUSED', 'code': 'INPUT_INTEGRITY'}
        interpretation = dict(schema_version='1.0', tenant_id=pins.scope.tenant_id, run_id=pins.scope.run_id,
            interpretation_id='ai-notrun-' + document_hash({'request': request.ref, 'operation': operation_id}),
            observation_ids=[], evidence_ids=[], hypotheses=[], recommendations=[],
            missing_information=['RA3B_CLAIM_VALIDATION_NOT_IMPLEMENTED'], model_id=None,
            input_tokens=None, output_tokens=None, status='NOT_RUN')
        validate_contract('AIInterpretation', interpretation)
        base['interpretation'] = interpretation
        base['operation_id'] = operation_id
        unknown_usage = dict(schema_version='1.0', tenant_id=pins.scope.tenant_id, run_id=pins.scope.run_id,
            usage_id='usage-' + document_hash({'request': request.ref, 'operation': operation_id, 'scope': asdict(pins.scope)}),
            cost_type='MODEL', provider=None, model_id=None, input_tokens=None, output_tokens=None,
            amount=None, currency=None, cost_status='UNKNOWN', recorded_at=recorded_at)
        validate_contract('UsageRecord', unknown_usage)
        base['usage'] = unknown_usage
        if self._disabled:
            return {**base, 'status': 'REFUSED', 'code': 'MODEL_PROVIDER_DISABLED'}
        if self._no_model:
            return {**base, 'status': 'NOT_RUN', 'code': 'NO_MODEL'}
        if self._ledger is None:
            return {**base, 'status': 'REFUSED', 'code': 'BUDGET_REQUIRED'}
        ledger = self._ledger
        try:
            ledger._authorize(pins.scope)
        except GatewayError:
            return {**base, 'status': 'REFUSED', 'code': 'ACCOUNTING_SCOPE_MISMATCH'}
        reservation = None
        dispatched = False
        code, reply = None, None
        try:
            integer(timeout_ms, 1, 5000)
            integer(max_output_tokens, 1, 2048)
            if type(cancel_before_dispatch) is not bool:
                raise GatewayError('INVALID_LIMIT_OR_USAGE')
            reservation = ledger.reserve(pins.scope, operation_id, request.ref,
                                         len(request.provider_bytes), max_output_tokens)
            ref = reservation['reservation_ref']
            if cancel_before_dispatch:
                ledger.update(pins.scope, operation_id, ref, 'RELEASE')
                code = 'CANCELLED_BEFORE_DISPATCH'
            else:
                ledger.update(pins.scope, operation_id, ref, 'START')
                dispatched = True
                base['fixture_calls'] = 1
                assert self._provider is not None
                reply = await asyncio.wait_for(self._provider.complete(request.provider_bytes, max_output_tokens),
                                               timeout=timeout_ms / 1000)
                if type(reply) is not ProviderReply or type(reply.text) is not str:
                    raise GatewayError('MALFORMED_REPLY')
                if reply.input_tokens is None or reply.output_tokens is None:
                    raise GatewayError('USAGE_UNKNOWN')
                integer(reply.input_tokens, 0, len(request.provider_bytes))
                integer(reply.output_tokens, 0, max_output_tokens)
                if len(reply.text.encode('utf-8')) > max_output_tokens:
                    raise GatewayError('OUTPUT_BOUND')
                if reply.input_tokens != len(request.provider_bytes) or reply.output_tokens != len(reply.text.encode('utf-8')):
                    raise GatewayError('INVALID_USAGE')
                ledger.update(pins.scope, operation_id, ref, 'COMMIT',
                    input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
                    response_ref='response-' + document_hash({'request_ref': request.ref, 'text': reply.text,
                        'input_tokens': reply.input_tokens, 'output_tokens': reply.output_tokens}))
        except asyncio.CancelledError:
            code = 'CANCELLED'
        except TimeoutError:
            code = 'TIMEOUT'
        except GatewayError as exc:
            code = str(exc)
            if code == 'INVALID_LIMIT_OR_USAGE' and dispatched:
                code = 'INVALID_USAGE'
        except Exception:
            code = 'PROVIDER_ERROR'
        if reservation is not None:
            row = ledger.record(pins.scope, operation_id)
            if row['state'] == 'IN_FLIGHT':
                reason = code if code in ('CANCELLED', 'TIMEOUT', 'MALFORMED_REPLY', 'USAGE_UNKNOWN',
                                         'INVALID_USAGE', 'OUTPUT_BOUND') else 'PROVIDER_ERROR'
                ledger.update(pins.scope, operation_id, row['reservation_ref'], 'UNKNOWN', reason=reason)
            elif row['state'] == 'RESERVED':
                ledger.update(pins.scope, operation_id, row['reservation_ref'], 'RELEASE')
            base['usage'] = ledger.usage(pins.scope, operation_id, recorded_at)
        else:
            # Repeated operation returns the same usage identity, never a second charge.
            try:
                old = ledger.record(pins.scope, operation_id)
                if old['request_ref'] == request.ref:
                    base['usage'] = ledger.usage(pins.scope, operation_id, recorded_at)
            except (KeyError, GatewayError):
                pass
        base['ledger'] = ledger.snapshot()
        if code:
            return {**base, 'status': 'REFUSED', 'code': code if not dispatched or code in (
                'CANCELLED', 'TIMEOUT', 'MALFORMED_REPLY', 'USAGE_UNKNOWN', 'INVALID_USAGE', 'OUTPUT_BOUND') else 'PROVIDER_ERROR'}
        assert reply is not None
        return {**base, 'status': 'FAKE_COMPLETED_UNVALIDATED', 'code': 'RA3B_VALIDATION_REQUIRED',
                'provider_output': reply.text}
