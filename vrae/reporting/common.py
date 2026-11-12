"""Bounded canonical data and non-reflective errors."""
import hashlib
import json
from typing import NoReturn

VERSION = 'ra3c-1.0.0'
MAX_BYTES = 8_000_000


class ReportError(ValueError):
    """Fixed safe codes only; no URL, source, model text or supplied ID in errors."""


def fail(code='REPORT_INTEGRITY') -> NoReturn:
    raise ReportError(code)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8', errors='strict')


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def detach(value):
    raw = encode(value)
    if len(raw) > MAX_BYTES:
        fail('REPORT_BOUND')
    return json.loads(raw)


def display_text(value, bound=4096):
    if (not isinstance(value, str) or len(value) > bound or
            any(ord(c) in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)) or
                (ord(c) < 32 and c not in '\n\r\t') for c in value)):
        fail('REPORT_DISPLAY_TEXT')
    value.encode('utf-8', errors='strict')
    return value
