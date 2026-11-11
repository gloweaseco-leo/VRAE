"""Authoritative policy provider is injected by trusted adapters, never remote HTML."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from jsonschema import ValidationError
from vrae.domain.contracts import validate_contract
from vrae.domain.errors import DomainError
from vrae.domain.policy import authorize_source, syntax_host
from .errors import CollectionError


def canonical_url(url: str) -> str:
    try:
        # Check the unmodified value first: urlsplit otherwise strips control characters.
        if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) >= 127 for c in url):
            raise CollectionError("INVALID_URL")
        parts = urlsplit(url)
        host = syntax_host(urlunsplit(parts._replace(fragment="")))
        path = parts.path or "/"
        # Strict first release: no query URLs, percent decoding or ambiguous separators.
        # This avoids query side effects, PII retention and multi-decoder disagreements.
        if parts.query or "%" in path or ";" in path or "//" in path:
            raise CollectionError("INVALID_URL")
        if any(segment in (".", "..") for segment in path.split("/")):
            raise CollectionError("INVALID_URL")
        return urlunsplit((parts.scheme, host, path, "", ""))
    except (DomainError, ValueError, UnicodeError) as exc:
        if isinstance(exc, CollectionError):
            raise
        raise CollectionError("INVALID_URL") from exc


class SourceAccess:
    def __init__(self, audit: dict, provider: Callable[[], dict], *, terms_reference: str,
                 now: Callable[[], datetime] | None = None):
        try:
            validate_contract("AuditRequest", audit)
        except (ValidationError, ValueError) as exc:
            raise CollectionError("INPUT_INVALID") from exc
        if audit["audit_mode"] not in ("L0", "L1") or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]{2,127}", terms_reference):
            raise CollectionError("SOURCE_NOT_ALLOWED")
        self.audit = deepcopy(audit)
        self.provider = provider
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.terms_reference = terms_reference
        self.start_url = canonical_url(audit["site_url"])
        self.host = urlsplit(self.start_url).hostname
        self._frozen_policy: str | None = None
        self.check(self.start_url)

    def check(self, url: str) -> str:
        normalized = canonical_url(url)
        if urlsplit(normalized).hostname != self.host:
            raise CollectionError("SOURCE_NOT_ALLOWED")
        if urlsplit(self.start_url).scheme == "https" and urlsplit(normalized).scheme != "https":
            raise CollectionError("SOURCE_NOT_ALLOWED")
        policy = deepcopy(self.provider())
        try:
            if policy is None:
                raise CollectionError("POLICY_REQUIRED")
            validate_contract("SourcePolicy", policy)
            authorize_source({**self.audit, "site_url": normalized}, policy, self.now())
        except DomainError as exc:
            raise CollectionError(exc.code) from exc
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, CollectionError):
                raise
            raise CollectionError("INPUT_INVALID") from exc
        fingerprint = json.dumps(policy, sort_keys=True, allow_nan=False)
        if self._frozen_policy is not None and fingerprint != self._frozen_policy:
            raise CollectionError("SOURCE_NOT_ALLOWED")
        self._frozen_policy = fingerprint
        return normalized
