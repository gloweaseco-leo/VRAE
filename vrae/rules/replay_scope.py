"""Reuse one source-derived execution inside one synchronous production only.

This stores neither authority nor a cross-request result. Every consumer still
compares its supplied rows, packages and claims against the derived execution.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import json

from vrae.evidence import EvidencePack, EvidenceError


@dataclass
class _Scope:
    pack: EvidencePack
    payload: bytes
    blobs: tuple
    execution: bytes | None = None


_current: ContextVar[_Scope | None] = ContextVar('rule_replay_scope', default=None)


@contextmanager
def execution_scope(pack):
    if type(pack) is not EvidencePack:
        raise EvidenceError('RULE_REPLAY_SCOPE_REQUIRED')
    pack.verify(expected_ref=pack.ref)
    existing = _current.get()
    if existing is not None and existing.pack is pack:
        if pack._payload is not existing.payload or pack._blobs is not existing.blobs:
            raise EvidenceError('RULE_REPLAY_SCOPE_CHANGED')
        yield
        return
    scope = _Scope(pack, pack._payload, pack._blobs)
    token = _current.set(scope)
    try:
        yield
    finally:
        _current.reset(token)


def replay(pack, expected_pack_ref, evaluator_version, compute):
    scope = _current.get()
    # Only the current automatic profile opts in. Historical replay and reads
    # outside production continue to derive the execution independently.
    if scope is None or scope.pack is not pack or evaluator_version != 'ra2b6-1.0.5':
        return compute()
    pack.verify(expected_ref=expected_pack_ref)
    if pack._payload is not scope.payload or pack._blobs is not scope.blobs:
        raise EvidenceError('RULE_REPLAY_SCOPE_CHANGED')
    if scope.execution is None:
        result = compute()
        raw = json.dumps(result, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False).encode()
        if len(raw) <= 8_000_000:
            scope.execution = raw
        return result
    # A caller mutating a returned execution cannot poison later verification.
    return json.loads(scope.execution)
