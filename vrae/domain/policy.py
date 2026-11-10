"""Syntax-only URL gate and versioned source authorization.

This is NOT SSRF protection: RA-1 must independently enforce DNS binding,
redirect validation, browser subresource egress and network-layer denial.
"""

import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

from .errors import DomainError


_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_FORBIDDEN_SUFFIXES = (".localhost", ".local", ".internal", ".invalid", ".arpa")


def parse_time(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timezone required")
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError) as exc:
        raise DomainError("SOURCE_NOT_ALLOWED", "Invalid timezone-aware timestamp") from exc


def syntax_host(url: str) -> str:
    """Conservatively validate literal URL syntax without any network resolution."""
    if not isinstance(url, str) or len(url) > 2048:
        raise DomainError("INVALID_URL", "Invalid URL length or type")
    if any(ord(c) <= 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise DomainError("INVALID_URL", "URL contains unsafe characters")
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise DomainError("INVALID_URL", "Only HTTP(S) with a host is supported")
        if parts.username is not None or parts.password is not None:
            raise DomainError("INVALID_URL", "Credential-bearing URL refused")
        host = (parts.hostname or "").rstrip(".").lower()
        if not host or "%" in parts.netloc or "@" in parts.netloc:
            raise DomainError("INVALID_URL", "Encoded or ambiguous authority")
        port = parts.port
        if port is not None and port != (443 if parts.scheme == "https" else 80):
            raise DomainError("INVALID_URL", "Non-default port is refused")
        if parts.fragment:
            raise DomainError("INVALID_URL", "Fragments are not audit targets")
        path = unquote(parts.path).lower()
        if any(x in parts.path.lower() for x in ("%00", "%2f", "%5c", "%2e")):
            raise DomainError("INVALID_URL", "Encoded path ambiguity refused")
        if "/../" in path or path.endswith("/..") or "/./" in path:
            raise DomainError("INVALID_URL", "Path traversal refused")
        host = host.encode("idna").decode("ascii")
        if len(host) > 253 or "." not in host:
            raise DomainError("SSRF_BLOCKED", "Non-public-looking hostname")
        if host == "localhost" or host.endswith(_FORBIDDEN_SUFFIXES):
            raise DomainError("SSRF_BLOCKED", "Special-use hostname")
        labels = host.split(".")
        if any(not _HOST_LABEL.fullmatch(x) for x in labels):
            raise DomainError("INVALID_URL", "Malformed hostname")
        if all(label.isdigit() for label in labels):
            raise DomainError("SSRF_BLOCKED", "Numeric address candidate")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise DomainError("SSRF_BLOCKED", "Literal IP target not allowed")
        # IPv6 has already been rejected by hostname label checks above.
        return host
    except DomainError:
        raise
    except (ValueError, UnicodeError) as exc:
        raise DomainError("INVALID_URL", "Malformed URL") from exc


def authorize_source(
    request: dict, policy: dict | None, now: datetime
) -> None:
    if policy is None:
        raise DomainError("POLICY_REQUIRED", "Source policy is mandatory")
    if now.tzinfo is None:
        raise DomainError("SOURCE_NOT_ALLOWED", "Aware UTC clock is required")
    if request["tenant_id"] != policy["tenant_id"]:
        raise DomainError("FORBIDDEN_TENANT", "Tenant mismatch")
    if (request["source_policy_ref"] != policy["policy_id"]
            or request["source_policy_version"] != policy["policy_version"]):
        raise DomainError("SOURCE_NOT_ALLOWED", "Policy identity/version mismatch")
    if policy["revoked_at"] is not None:
        raise DomainError("POLICY_REVOKED", "Authorization was revoked")
    if policy["expires_at"] is not None and parse_time(policy["expires_at"]) <= now:
        raise DomainError("POLICY_EXPIRED", "Authorization expired")
    mode = request["audit_mode"]
    if mode not in ("L0", "L1", "L2"):
        raise DomainError("SOURCE_NOT_ALLOWED", "Unknown audit level")
    policy_mode = policy["mode"]
    if mode == "L2":
        if (policy_mode != "OWNER_AUTHORIZED_DEEP"
                or not policy["authorization_reference"]
                or policy["expires_at"] is None):
            raise DomainError("SOURCE_NOT_ALLOWED", "L2 requires bounded owner consent")
    elif policy_mode not in ("PUBLIC_READONLY_RESEARCH", "OWNER_AUTHORIZED_DEEP"):
        raise DomainError("SOURCE_NOT_ALLOWED", "Unknown policy mode")
    target = syntax_host(request["site_url"])
    hosts = {syntax_host("https://" + host) for host in policy["permitted_hosts"]}
    if target not in hosts:
        raise DomainError("SOURCE_NOT_ALLOWED", "Host not explicitly permitted")
    path = urlsplit(request["site_url"]).path or "/"
    scopes = policy["scope_paths"]
    if not scopes or not any(
        path == scope or scope == "/"
        or path.startswith(scope.rstrip("/") + "/")
        for scope in scopes
    ):
        raise DomainError("SOURCE_NOT_ALLOWED", "URL outside permitted scope")
