"""Server-only PR164 -> original S3 Session -> existing strict Qwen4 provider.

No credentials, fee grant, endpoint or selection pins are taken from a request.
Use with authorized_targets.postcommit.run, never as a browser JSON endpoint.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import re
import threading

from vrae.intelligence.common import encode as canonical
from integration.qwen_provider.postcommit import InputPins, replay_input
from vrae.intelligence.qwen import QwenError
from vrae.intelligence.qwen.provider import digest
from vrae.intelligence.s3 import Session, S3Error, prepare_context
from vrae.intelligence.s3.committed import CommittedCompletionPins
from vrae.l2.native import NativeTask


def current_input(binding, job_id):
    """A fresh original PG transaction, closed before any provider I/O."""
    from integration.authorized_targets.delivery import committed_input
    with committed_input(binding, job_id, purpose='POST_COMMIT_AI_INPUT') as value:
        return deepcopy(value)


def execute(binding, job_id, adapter, *, operation_id):
    """Call the original PG port, preserving usage if its final recheck fails.

    The provider ledger settles only supplier usage. A failed PG receipt is never
    presented as a committed candidate, and never retried by this wrapper.
    """
    from integration.authorized_targets.postcommit import run
    seen = {}

    def invoke(request):
        result = adapter(request)
        seen.update(deepcopy(result))
        return result

    try:
        result = run(binding, job_id, invoke, operation_id=operation_id)
        return {**result, 'pg_receipt_status': 'RECORDED'}
    except Exception:
        return {**seen, 'state': 'AI_UNAVAILABLE', 'reason': 'CURRENT_PG_RECEIPT_UNAVAILABLE',
                'operation_id': operation_id, 'claims': [],
                'usage': seen.get('usage'), 'cost_status': seen.get('cost_status', 'UNKNOWN'),
                'pg_receipt_status': 'UNKNOWN', 'grants_report_access': False,
                'shareable': False, 'approval_status': 'NOT_APPROVED'}


class Adapter:
    """Trusted server composition; projection/BuyerCandidatePins are held by C1.

    The original PG/signature port supplies authority. Python objects, callbacks
    and request-shaped dictionaries are not an authentication mechanism.
    Construct once per task; keep the existing provider's durable quota unchanged.
    """
    def __init__(self, binding, job_id, *, projection, buyer_pins, provider=None,
                 clock=lambda: datetime.now(timezone.utc), timeout_ms=120000):
        self._binding, self._job_id = deepcopy(binding), str(job_id)
        self._projection, self._buyer_pins = deepcopy(projection), buyer_pins
        self._provider, self._clock, self._timeout = provider, clock, timeout_ms
        self._session = None
        self._lock = threading.Lock()

    def __call__(self, request):
        # Session's asyncio cache belongs to one invocation loop at a time.
        if not self._lock.acquire(blocking=False):
            return {'state': 'AI_UNAVAILABLE', 'reason': 'OPERATION_IN_FLIGHT',
                    'operation_id': request.get('ai_operation_id') if type(request) is dict else None,
                    'model': 'qwen4-max', 'claims': [], 'usage': None,
                    'real_model_calls': None, 'provider_attempts': None, 'cost_status': 'UNKNOWN',
                    'shareable': False, 'approval_status': 'NOT_APPROVED'}
        try:
            return self._run(request)
        finally:
            self._lock.release()

    def _run(self, request):
        operation = request.get('ai_operation_id') if type(request) is dict else None
        output = {'state': 'AI_UNAVAILABLE', 'reason': 'COMMITTED_INPUT_UNAVAILABLE',
                  'operation_id': operation, 'model': 'qwen4-max', 'claims': [],
                  'real_model_calls': 0, 'provider_attempts': 0, 'usage': None,
                  'cost_status': 'NOT_INCURRED_BY_THIS_OPERATION', 'shareable': False,
                  'approval_status': 'NOT_APPROVED'}
        if self._provider is not None:
            output.update(real_model_calls=None, provider_attempts=None, cost_status='UNKNOWN')
        phase = 'INPUT'
        try:
            if type(operation) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{7,127}', operation):
                raise S3Error('COMMITTED_OPERATION_INVALID')
            held = current_input(self._binding, self._job_id)
            expected = {k: v for k, v in request.items()
                        if k not in ('ai_operation_id', 'current_authority')}
            authority = request.get('current_authority')
            extra_deadline = None
            if authority is not None:
                # The additional V2 authority is a server-held PG-rechecking
                # object, never a JSON trust hint or model input.
                from integration.authorized_targets.current_authority import CurrentCommittedAuthority
                if type(authority) is not CurrentCommittedAuthority:
                    raise S3Error('COMMITTED_AUTHORITY_INVALID')
                live = authority.check_current()
                base_live = {k: v for k, v in live.items()
                             if k not in ('authority_profile', 'authority_expires_at')}
                if canonical(base_live) != canonical(held) or canonical(expected) != canonical(live):
                    raise S3Error('COMMITTED_INPUT_MISMATCH')
                extra_deadline = live['authority_expires_at']
            if (canonical(expected) != canonical(held) and authority is None
                    or held['contract'] != 'vrae.committed-target-input.v1'
                    or held['purpose'] != 'POST_COMMIT_AI_INPUT'
                    or held['publication'] != 'UNPUBLISHED' or held['grants_report_access'] is not False
                    or held['task']['tenant_id'] != self._binding['tenant_id']
                    or held['task']['job_id'] != self._job_id
                    or canonical(held['task']) != canonical(held['artifact']['task'])):
                raise S3Error('COMMITTED_INPUT_MISMATCH')
            frozen = canonical(held)
            d, commit = held['artifact'], held['commit']
            task = NativeTask(**d['native_document']['native_context'])
            pins = InputPins(task, commit['artifact_sha256'], d['version']['content_hash'], d['display_hash'])
            pack, source = replay_input(canonical(d), pins=pins)
            if self._provider is not None:
                # Read the SAME durable ledger before calling a preflight zero.
                # A restarted/cached operation may already have incurred usage.
                identity = digest({'scope': {k: pack.document[k] for k in
                    ('tenant_id', 'run_id', 'policy_id', 'policy_version')}, 'operation': operation})
                previous = self._provider.quota.receipt(identity)
                reserved = self._provider.quota.dispatched(identity)
                output.update(usage=previous,
                    provider_attempts=1 if reserved else 0,
                    real_model_calls=(previous['real_model_calls'] if previous else
                        None if reserved and not self._provider.protocol_fake else 0),
                    cost_status=(previous['cost_status'] if previous else
                        'UNKNOWN' if reserved else 'NOT_INCURRED_BY_THIS_OPERATION'))

            def recheck(checked_source, now):
                try:
                    if authority is not None:
                        authority.check_current()
                    if (checked_source.held != task or
                            canonical(current_input(self._binding, self._job_id)) != frozen):
                        raise ValueError
                except Exception:
                    raise S3Error('CURRENT_COMMITTED_AUTHORITY_DENIED') from None

            # committed_at is the PG result-row timestamp, not an exact physical
            # COMMIT instant. Visibility through current_input proves COMMIT.
            deadlines = [held['source_plan']['expires_at'], held['source_plan']['policy']['expires_at']]
            if 'source_authority' in d:
                auth = d['source_authority']['authorization']['document']
                deadlines += [auth['expires_at'], auth['retention_until']]
            if extra_deadline is not None:
                deadlines.append(extra_deadline)
            language = held.get('request_language', 'en')
            if d['diagnosis']['diagnostic_version'] == 'l2-industrial-1.0.3' and 'request_language' not in held:
                raise S3Error('COMMITTED_REQUEST_LANGUAGE_REQUIRED')
            completion = CommittedCompletionPins(task, pins.report_content_hash,
                datetime.fromisoformat(commit['lease_started_at']),
                datetime.fromisoformat(commit['lease_expires_at']),
                datetime.fromisoformat(commit['committed_at']),
                min(datetime.fromisoformat(t) for t in deadlines),
                commit['transaction_id'], pins.artifact_sha256, hashlib.sha256(frozen).hexdigest(), recheck, response_language=language)
            phase = 'CONTEXT'
            context = prepare_context(pack, source, self._projection, buyer_pins=self._buyer_pins,
                                      completion=completion, now=self._clock())
            if self._session is None:
                self._session = Session(context, clock=self._clock)
            elif self._session.context.context_ref != context.context_ref:
                raise S3Error('COMMITTED_INPUT_MISMATCH')
            if self._provider is None:
                output['reason'] = 'PROVIDER_GO_NOT_GRANTED'
                output['failure_stage'] = 'PREFLIGHT'
                return output
            # From this point Session may dispatch or return a cached operation.
            # Keep uncertainty if it raises without a result; preflight is zero.
            output.update(real_model_calls=None, provider_attempts=None, cost_status='UNKNOWN')
            phase = 'SESSION_UNKNOWN'
            result = asyncio.run(self._session.run(operation, mode='REAL_QWEN', provider=self._provider,
                                                  timeout_ms=self._timeout))
            output.update(state=result['status'], reason=result['code'], claims=result['claims'],
                usage=result['usage'], real_model_calls=result['real_model_calls'],
                provider_attempts=result['provider_attempts'], context_ref=result['context_ref'],
                deterministic_report_hash=result['deterministic_report_hash'],
                verification_realm=result['verification_realm'])
            output['failure_stage'] = result.get('failure_stage')
            output['cost_status'] = (result['usage']['cost_status'] if result['usage'] is not None else
                'NOT_INCURRED_BY_THIS_OPERATION' if result['provider_attempts'] == 0 else 'UNKNOWN')
            # Covers cached results as well as fresh dispatch. Preserve durable
            # usage on refusal; candidates cannot survive lost source authority.
            phase = 'CURRENT_AUTHORITY'
            completion.check(source, self._clock())
        except (S3Error, QwenError) as error:
            output.update(state='AI_UNAVAILABLE', reason=str(error), claims=[], failure_stage=phase)
        except Exception:
            output.update(state='AI_UNAVAILABLE', reason='COMMITTED_INPUT_UNAVAILABLE', claims=[], failure_stage=phase)
        return output
