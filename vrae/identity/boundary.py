"""Closed Ed25519 JWS profile with out-of-band, expiring local trust/policy.

Trusted constructor inputs are provisioning, never request fields. No discovery,
network fetch, signing, native decisions, proposal submission or grants exist here.
"""

import base64
import hashlib
import json
import math
import re
import threading
import time
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from vrae.persistence.private_bytes import Locator


class IdentityDenied(ValueError):
    """Only constant error codes cross this boundary; never credentials."""


def deny():
    raise IdentityDenied("P2B2A_IDENTITY_DENIED") from None


def decode(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", raw):
        deny()
    data = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    if base64.urlsafe_b64encode(data).decode().rstrip("=") != raw:
        deny()
    return data


def document(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                deny()
            result[key] = value
        return result

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                       parse_constant=lambda _: deny())
    if type(value) is not dict:
        deny()
    return value


@dataclass(frozen=True)
class TrustAnchor:
    issuer: str
    audience: str
    jwks: bytes = field(repr=False)
    expires: int
    revoked: frozenset[str] = frozenset()
    available: bool = True


@dataclass(frozen=True)
class Assignment:
    issuer: str
    subject: str
    db_role: str
    location: Locator
    expires: int
    active: bool = True


@dataclass(frozen=True)
class IdentityCheck:
    """Observation only. This value is never accepted by any authority port."""

    subject: str = field(repr=False)
    tenant: str
    report: str
    version: int
    authority: str = "TEST_ONLY_IDENTITY_OBSERVATION"
    native_decision: None = None
    native_approval: None = None
    share_grant: None = None
    external_visibility: bool = False


class IdentityBoundary:
    def __init__(self, *, anchor, assignments, connect, clock=time.time, skew=5,
                 replay_capacity=4096):
        if type(skew) is not int or not 0 <= skew <= 30:
            deny()
        if type(replay_capacity) is not int or not 1 <= replay_capacity <= 100000:
            deny()
        self.anchor = anchor
        self.assignments = tuple(assignments)
        self.connect = connect
        self.clock = clock
        self.skew = skew
        self.capacity = replay_capacity
        self._seen = {}
        self._last_time = 0
        self._lock = threading.Lock()

    def check(self, bearer, location, *, nonce):
        """Consume a single-use token and check current PG authority read-only.

        nonce is a server-held challenge, not a nonce extracted from the token.
        Replay storage is process-local: process restart requires NEW issuer keys
        and a new boundary (no production or multi-worker support).
        """
        try:
            with self._lock:
                return self._check(bearer, location, nonce)
        except Exception:
            # Do not chain parser, driver, provider or signature diagnostics which
            # could contain a credential or a raw input fragment.
            deny()

    def _check(self, bearer, location, nonce):
        now = self.clock()
        if (type(now) not in (int, float) or not math.isfinite(now)
                or now < self._last_time or now <= 0):
            deny()
        self._last_time = now
        a = self.anchor
        if (type(a) is not TrustAnchor or a.available is not True
                or type(a.expires) is not int or a.expires <= now
                or not a.issuer or not a.audience or type(a.jwks) is not bytes
                or not 0 < len(a.jwks) <= 16384):
            deny()
        if (type(bearer) is not str or len(bearer) > 8192
                or not bearer.startswith("Bearer ") or type(location) is not Locator
                or type(nonce) is not str or not 16 <= len(nonce) <= 128):
            deny()
        token = bearer[7:]
        if token.count(".") != 2:
            deny()
        h, p, sig = token.split(".")
        header, claims = document(decode(h)), document(decode(p))
        if (set(header) != {"alg", "kid", "typ"} or header["alg"] != "EdDSA"
                or header["typ"] != "vrae-test-identity+jwt"
                or type(header["kid"]) is not str or not 1 <= len(header["kid"]) <= 64):
            deny()
        keyset = document(a.jwks)
        if set(keyset) != {"keys"} or type(keyset["keys"]) is not list:
            deny()
        keys = {}
        for k in keyset["keys"]:
            if (type(k) is not dict or set(k) != {"kty", "crv", "use", "alg", "kid", "x"}
                    or k["kty"] != "OKP" or k["crv"] != "Ed25519"
                    or k["use"] != "sig" or k["alg"] != "EdDSA"
                    or type(k["kid"]) is not str or k["kid"] in keys):
                deny()
            keys[k["kid"]] = Ed25519PublicKey.from_public_bytes(decode(k["x"]))
        kid = header["kid"]
        if kid not in keys or kid in a.revoked:
            deny()
        signature = decode(sig)
        if len(signature) != 64:
            deny()
        try:
            keys[kid].verify(signature, (h + "." + p).encode("ascii"))
        except InvalidSignature:
            deny()
        required = {"iss", "aud", "sub", "exp", "nbf", "iat", "jti", "nonce"}
        if not required <= set(claims):
            deny()
        if (claims["iss"] != a.issuer or claims["aud"] != a.audience
                or any(type(claims[k]) is not int for k in ("exp", "nbf", "iat"))
                or any(type(claims[k]) is not str or not 1 <= len(claims[k]) <= 128
                       for k in ("sub", "jti", "nonce"))
                or claims["nonce"] != nonce):
            deny()
        exp, nbf, iat = (claims[k] for k in ("exp", "nbf", "iat"))
        if (exp <= now - self.skew or nbf > now + self.skew or iat > now + self.skew
                or not 0 <= iat <= nbf < exp or exp - iat > 300):
            deny()
        # Hash identifiers, never retain raw tokens. Atomic consumption before DB
        # means a failed/unavailable provider also cannot cause token reuse.
        self._seen = {k: v for k, v in self._seen.items() if v > now}
        replay_key = hashlib.sha256((a.issuer + "\0" + claims["jti"]).encode()).digest()
        if replay_key in self._seen or len(self._seen) >= self.capacity:
            deny()
        self._seen[replay_key] = exp + self.skew
        matches = [x for x in self.assignments if type(x) is Assignment
                   and x.issuer == a.issuer and x.subject == claims["sub"]
                   and x.location == location and x.active is True
                   and type(x.expires) is int and x.expires > now]
        if len(matches) != 1:
            deny()
        binding = matches[0]
        # The factory and role come ONLY from separately held test provisioning.
        with self.connect(binding.db_role) as c:
            if (not c.autocommit or c.info.host not in ("127.0.0.1", "localhost")
                    or not re.fullmatch(r"vrae_p2b1_[0-9a-f]{12}", c.info.dbname)):
                deny()
            row = c.execute(
                "SELECT session_user,current_setting('server_version_num')::int,"
                "rolsuper,rolbypassrls,rolcreaterole,rolcreatedb "
                "FROM pg_roles WHERE rolname=session_user"
            ).fetchone()
            if (not row or row[0] != binding.db_role or not 160000 <= row[1] < 170000
                    or any(row[2:])):
                deny()
            with c.transaction():
                rows = c.execute(
                    "SELECT * FROM ra4a_review_test.load_target(%s,%s,%s,%s,%s,%s)",
                    (location.tenant, location.ref_id, location.source_run,
                     location.report, location.version, location.target_digest),
                ).fetchall()
                if not rows:
                    deny()
        return IdentityCheck(claims["sub"], location.tenant, location.report, location.version)


def production_port(*args, **kwargs):
    deny()
