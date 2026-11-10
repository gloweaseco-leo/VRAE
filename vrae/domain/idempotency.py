"""Offline idempotency reference behavior. RA-4 must persist atomically."""

import hashlib
import json

from .errors import DomainError


def accept_once(
    records: dict[str, tuple[str, str]], tenant_id: str,
    key: str, payload: dict, request_id: str,
) -> str:
    if not tenant_id or len(key) < 8:
        raise DomainError("SOURCE_NOT_ALLOWED", "Invalid idempotency scope")
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    scoped_key = tenant_id + ":" + key
    existing = records.get(scoped_key)
    if existing is not None:
        if existing[0] != fingerprint:
            raise DomainError("IDEMPOTENCY_CONFLICT", "Same key, different payload")
        return existing[1]
    records[scoped_key] = (fingerprint, request_id)
    return request_id
