"""Typed replacement seam, runtime-allowlisted deterministic fixture implementation only."""
import asyncio
from dataclasses import dataclass
from typing import Protocol

from .common import GatewayError

PROVIDER = 'deterministic-fixture'
MODEL = 'fixture-bytes-v1'


@dataclass(frozen=True)
class ProviderReply:
    text: str
    input_tokens: int | None
    output_tokens: int | None


class OfflineProvider(Protocol):
    async def complete(self, payload: bytes, max_output_tokens: int) -> ProviderReply: ...


@dataclass(frozen=True)
class FixtureProvider:
    text: str = 'One bounded source fact may be explained; independent claim validation is still required.'
    behavior: str = 'ok'

    def __post_init__(self):
        if type(self.text) is not str or len(self.text) > 16384 or type(self.behavior) is not str:
            raise GatewayError('FIXTURE_INVALID')
        try:
            self.text.encode('utf-8')
        except UnicodeError as exc:
            raise GatewayError('FIXTURE_INVALID') from exc

    async def complete(self, payload: bytes, max_output_tokens: int) -> ProviderReply:
        if self.behavior == 'timeout':
            await asyncio.sleep(10)
        if self.behavior in ('error', 'egress', 'credential'):
            raise GatewayError('FIXTURE_REFUSED')
        if self.behavior == 'cancel':
            raise asyncio.CancelledError()
        if self.behavior == 'missing_usage':
            return ProviderReply(self.text, None, None)
        if self.behavior == 'negative_usage':
            return ProviderReply(self.text, -1, 0)
        if self.behavior == 'excess_usage':
            return ProviderReply(self.text, len(payload), max_output_tokens + 1)
        if self.behavior == 'malformed':
            return None  # type: ignore[return-value]
        if self.behavior != 'ok':
            raise GatewayError('FIXTURE_REFUSED')
        return ProviderReply(self.text, len(payload), len(self.text.encode('utf-8')))
