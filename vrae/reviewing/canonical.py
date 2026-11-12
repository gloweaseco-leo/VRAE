"""Bounded sidecar serialization; digests bind bytes, never human authority."""

import hashlib
import json
from typing import NoReturn

TARGET_LIMIT = 65_536
COMMAND_LIMIT = 131_072
SOURCE_LIMIT = 8_000_000


class ReviewError(ValueError):
    """Internal sidecar refusal; not an extension of native ErrorCode."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def refuse(code: str) -> NoReturn:
    raise ReviewError(code)


def _check(value, depth=0):
    if depth > 32:
        refuse("D_JSON_BOUND")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if abs(value) > 9_007_199_254_740_991:
            refuse("D_JSON_BOUND")
    elif type(value) is str:
        value.encode("utf-8", errors="strict")
    elif type(value) is list:
        for item in value:
            _check(item, depth + 1)
    elif type(value) is dict:
        if any(type(k) is not str for k in value):
            refuse("D_JSON_TYPE")
        for k, v in value.items():
            _check(k, depth + 1)
            _check(v, depth + 1)
    else:
        # Floats are outside this integer/string sidecar contract, even finite.
        refuse("D_JSON_TYPE")


def canonical(value, *, limit=TARGET_LIMIT) -> bytes:
    try:
        _check(value)
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
        if len(raw) > limit:
            refuse("D_JSON_BOUND")
        return raw
    except ReviewError:
        raise
    except (ValueError, TypeError, RecursionError, UnicodeError):
        refuse("D_JSON_INVALID")


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            refuse("D_JSON_DUPLICATE_KEY")
        result[k] = v
    return result


def parse(raw: bytes, *, limit=TARGET_LIMIT):
    if type(raw) is not bytes:
        refuse("D_JSON_TYPE")
    if len(raw) > limit:
        refuse("D_JSON_BOUND")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _: refuse("D_JSON_NONFINITE"),
        )
        canonical(value, limit=limit)
        return value
    except ReviewError:
        raise
    except (ValueError, TypeError, RecursionError, UnicodeError):
        refuse("D_JSON_INVALID")


def sha(raw: bytes) -> str:
    if type(raw) is not bytes:
        refuse("D_BYTES_REQUIRED")
    return hashlib.sha256(raw).hexdigest()


def digest(kind: str, payload, *, limit=TARGET_LIMIT) -> str:
    return sha(
        ("vrae.ra3d." + kind + ".offline-v1\n").encode("utf-8") + canonical(payload, limit=limit)
    )


def shape(value, keys, code="D_SHAPE"):
    if type(value) is not dict or set(value) != set(keys):
        refuse(code)


def text(value, maximum=2000, *, allow_empty=False):
    if (
        type(value) is not str
        or len(value) > maximum
        or (not allow_empty and not value.strip())
        or any(
            ord(c) < 32 or ord(c) in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)) for c in value
        )
    ):
        refuse("D_UNTRUSTED_TEXT")
    value.encode("utf-8", errors="strict")
    return value
