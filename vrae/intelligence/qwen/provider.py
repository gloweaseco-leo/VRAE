"""Native Chat Completions protocol; fixture accounting is deliberately not reused."""
import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import re
import sys
from time import monotonic
from typing import TYPE_CHECKING, NoReturn

from vrae.intelligence.common import encode
from .testing import FakeTransport

if TYPE_CHECKING:
    from .quota import Quota

MODEL = 'qwen3.7-plus-2026-05-26'
PROVIDER = 'aliyun-bailian-beijing'
PROMPT = 'qwen-minimized-buyer-1.0.0'
INPUT_CAP = 65536  # Conservative reservation ceiling, never reported as actual usage.
OUTPUT_CAP = 2048
OUTPUT_RESERVE = OUTPUT_CAP + 10  # Documented supplier cap rounding tolerance.
MAX_RESPONSE = 131072


class QwenError(ValueError):
    """Fixed local codes only; no remote bodies, exceptions, keys or identifiers."""


def fail(code) -> NoReturn:
    raise QwenError(code)


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def strict_json(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                fail('DUPLICATE_JSON_FIELD')
            out[k] = v
        return out
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: fail('INVALID_JSON'))
    except QwenError:
        raise
    except Exception:
        raise QwenError('INVALID_JSON') from None


@dataclass(frozen=True)
class Config:
    """Server-held configuration. Neither model nor endpoint is a request parameter."""
    workspace_id: str

    def __post_init__(self):
        if type(self.workspace_id) is not str or not re.fullmatch(
                r'[a-z0-9][a-z0-9-]{0,62}', self.workspace_id):
            fail('WORKSPACE_INVALID')

    @property
    def host(self):
        return self.workspace_id + '.cn-beijing.maas.aliyuncs.com'


@dataclass(frozen=True)
class Permission:
    """Trusted operator's recorded synthetic-only fee/region approval, not authentication.

    Construct only after separate Owner approval. HTTP/model input cannot create it.
    No default permission, key lookup, network permission or spend allowance exists.
    """
    approval_ref: str
    expires_at: datetime
    max_calls: int
    cap_micros: int
    region: str = 'cn-beijing'
    synthetic_only: bool = True

    def check(self, now):
        if (not re.fullmatch(r'[A-Za-z0-9_.-]{3,128}', self.approval_ref)
                or type(self.expires_at) is not datetime or self.expires_at.utcoffset() is None
                or now.utcoffset() is None or now >= self.expires_at
                or type(self.max_calls) is not int or not 1 <= self.max_calls <= 16
                or type(self.cap_micros) is not int or not 1 <= self.cap_micros <= 100_000_000
                or self.region != 'cn-beijing' or self.synthetic_only is not True):
            fail('OWNER_PERMISSION_REQUIRED')


@dataclass(frozen=True)
class Price:
    """Pinned operator-verified CNY micro-units per million tokens, not an invoice."""
    snapshot_id: str
    source: str
    input_micros_per_million: int
    output_micros_per_million: int
    valid_until: datetime
    currency: str = 'CNY'

    def check(self, now):
        if (not re.fullmatch(r'[A-Za-z0-9_.-]{3,128}', self.snapshot_id)
                or self.source != 'https://help.aliyun.com/zh/model-studio/models'
                or self.currency != 'CNY' or type(self.valid_until) is not datetime
                or self.valid_until.utcoffset() is None or now >= self.valid_until
                or any(type(v) is not int or not 1 <= v <= 1_000_000_000 for v in (
                    self.input_micros_per_million, self.output_micros_per_million))):
            fail('PRICE_REQUIRED')

    def cost(self, inputs, outputs):
        return int((Decimal(inputs * self.input_micros_per_million +
                            outputs * self.output_micros_per_million) / 1_000_000)
                   .to_integral_value(rounding=ROUND_CEILING))

    @property
    def document(self):
        return {**asdict(self), 'valid_until': self.valid_until.isoformat(),
                'model_id': MODEL, 'basis': 'ESTIMATE_NOT_PROVIDER_INVOICE'}


class NativeTransport:
    """One bounded dedicated egress process; fixed host/path, no proxies or retry.

    Does not alter the R1B NO_MODEL container or claim kernel egress isolation.
    Secret travels through an anonymous stdin pipe, never argv/environment/logs.
    """
    async def post(self, config, key, body, timeout_ms):
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-I', '-X', 'utf8', str(Path(__file__).with_name('egress.py')),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env={})
        envelope = encode({'workspace': config.workspace_id, 'key': key,
                           'body': body, 'timeout_ms': timeout_ms})
        try:
            # Child reads at most a fixed response bound and emits no remote headers/errors.
            raw, _ = await asyncio.wait_for(process.communicate(envelope), timeout_ms / 1000)
            if process.returncode != 0 or len(raw) > MAX_RESPONSE * 2:
                fail('EGRESS_FAILED')
            reply = strict_json(raw)
            if set(reply) != {'status', 'body'}:
                fail('EGRESS_FAILED')
            return reply['status'], reply['body'].encode('utf-8')
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()


@dataclass(repr=False, frozen=True)
class QwenProvider:
    config: Config
    quota: 'Quota'
    permission: Permission | None = None
    price: Price | None = None
    key: str | None = field(default=None, repr=False)
    _transport: NativeTransport | FakeTransport = field(default_factory=NativeTransport, repr=False)

    def __repr__(self):
        return 'QwenProvider(<server-held configuration and secret>)'

    @property
    def protocol_fake(self):
        # Only the shipped offline fake is accepted; arbitrary HTTP clients are rejected.
        return type(self._transport) is FakeTransport

    def authorize(self, now):
        from .quota import Quota
        if type(self.config) is not Config or type(self.quota) is not Quota:
            fail('TRUSTED_CONFIGURATION_REQUIRED')
        if type(self.permission) is not Permission:
            fail('OWNER_PERMISSION_REQUIRED')
        self.permission.check(now)
        if type(self.price) is not Price:
            fail('PRICE_REQUIRED')
        self.price.check(now)
        if (type(self.key) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{16,256}', self.key)):
            fail('KEY_REQUIRED')
        if type(self._transport) is not NativeTransport and not self.protocol_fake:
            fail('TRANSPORT_DISABLED')
        if not self.protocol_fake and (self.permission.approval_ref.startswith('TEST_')
                                       or self.key.startswith('synthetic-')):
            fail('OWNER_PERMISSION_REQUIRED')

    async def complete(self, body, *, operation, scope, context_ref, now, timeout_ms):
        self.authorize(now)
        assert self.price is not None and self.permission is not None
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 30000:
            fail('TIMEOUT_BOUND')
        if len(encode(body)) > 48000 or body['model'] != MODEL:
            fail('REQUEST_BOUND')
        identity = digest({'scope': scope, 'operation': operation})
        intent = digest({'context': context_ref, 'body': body,
                         'protocol_fake': self.protocol_fake})
        # A restart/replay can never dispatch the same operation a second time.
        self.quota.reserve(identity, intent, config=self.config, permission=self.permission,
                           price=self.price, protocol_fake=self.protocol_fake)
        start = monotonic()
        try:
            status, raw = await asyncio.wait_for(
                self._transport.post(self.config, self.key, body, timeout_ms), timeout_ms / 1000)
            if type(status) is not int or status != 200:
                fail('RATE_LIMITED' if status == 429 else 'PROVIDER_HTTP_ERROR')
            if type(raw) is not bytes or len(raw) > MAX_RESPONSE:
                fail('RESPONSE_BOUND')
            response = strict_json(raw)
            usage = response.get('usage', {})
            counts = [usage.get(k) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')]
            if (any(type(v) is not int or v < 0 for v in counts)
                    or counts[0] < 1 or counts[1] < 1 or counts[0] > INPUT_CAP
                    or counts[1] > OUTPUT_RESERVE or counts[2] != counts[0] + counts[1]):
                fail('USAGE_UNKNOWN')
            if response.get('object') != 'chat.completion' or response.get('model') != MODEL:
                fail('MODEL_NOT_CONFIRMED')
            request_id = response.get('id')
            if type(request_id) is not str or not 1 <= len(request_id) <= 256:
                fail('REQUEST_ID_MISSING')
            receipt = {'provider': PROVIDER, 'model_id': response['model'],
                'request_id_hash': hashlib.sha256(request_id.encode()).hexdigest(),
                'prompt_version': PROMPT, 'input_tokens': counts[0], 'output_tokens': counts[1],
                'total_tokens': counts[2], 'amount_micros': self.price.cost(*counts[:2]),
                'currency': 'CNY', 'cost_status': 'ESTIMATED', 'price_snapshot': self.price.document,
                'usage_origin': 'PROTOCOL_FAKE_NOT_REAL_API' if self.protocol_fake else 'PROVIDER_REPORTED',
                'duration_ms': int((monotonic() - start) * 1000), 'recorded_at': now.isoformat(),
                'real_model_calls': 0 if self.protocol_fake else 1, 'provider_attempts': 1,
                'billing_origin': 'TOKEN_BASED_ESTIMATE_NOT_INVOICE'}
            # Persist genuine usage even when the subsequent content/Guard check refuses.
            self.quota.settle(identity, intent, receipt)
            choices = response.get('choices')
            if (type(choices) is not list or len(choices) != 1
                    or choices[0].get('finish_reason') != 'stop'):
                fail('INCOMPLETE_OUTPUT')
            message = choices[0].get('message', {})
            if (message.get('role') != 'assistant' or message.get('tool_calls')
                    or message.get('function_call') or type(message.get('content')) is not str):
                fail('CONTENT_INVALID')
            return message['content'], receipt
        except asyncio.CancelledError:
            self.quota.unknown(identity, 'CANCELLED')
            raise
        except Exception as exc:
            code = str(exc) if type(exc) is QwenError else (
                'TIMEOUT' if isinstance(exc, TimeoutError) else 'PROVIDER_FAILURE')
            self.quota.unknown(identity, code)
            raise QwenError(code) from None
