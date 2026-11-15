"""Versioned signed generated-result read, actual B4 DB profile, no old shim.

Issuer/keys, subject-to-role/job assignments, connection factory and nonce are
trusted server provisioning. The caller supplies no DB identity or source bytes.
Crypto primitives and exact EdDSA encoding reuse the accepted identity module.
Replay state is process-local; restart requires a new issuer key/challenge.
"""

from dataclasses import dataclass, field
import hashlib
import math
import threading
import time
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from vrae.identity.boundary import TrustAnchor, decode, document, IdentityDenied
from .producer import Output, replay


def deny():
    raise IdentityDenied("M1_SIGNED_RESULT_DENIED") from None


@dataclass(frozen=True)
class JobAssignment:
    issuer: str
    subject: str
    db_role: str
    tenant: str
    job_id: str
    expires: int
    active: bool = True


@dataclass(frozen=True)
class GeneratedReport:
    locator: dict
    source: bytes = field(repr=False)
    report: bytes = field(repr=False)
    html: bytes = field(repr=False)

    @property
    def editorial_selection(self):
        import json

        d = json.loads(self.source)["editorial_selection"]
        return {
            "version": d["version"],
            "full_fact_count": len(json.loads(d["full_catalog_json"])),
            "selected_fact_count": len(d["selected_facts"]),
            "omitted_positive_facts": d["omitted_positive_facts"],
            "full_evidence_retained": True,
        }


class SignedGeneratedReader:
    def __init__(self, *, anchor, assignments, connect, clock=time.time):
        self.anchor = anchor
        self.assignments = tuple(assignments)
        self.connect = connect
        self.clock = clock
        self.seen = {}
        self.last = 0
        self.lock = threading.Lock()

    def read(self, bearer, tenant, job_id, *, nonce):
        try:
            with self.lock:
                assignment = self._authenticate(bearer, tenant, job_id, nonce)
            with self.connect(assignment.db_role) as c:
                if (
                    not c.autocommit
                    or c.info.host not in ("127.0.0.1", "localhost")
                    or c.info.dbname != "vrae_ra4a_p1"
                ):
                    deny()
                row = c.execute(
                    "SELECT session_user,current_user,current_setting('server_version_num')::int,"
                    "rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,pg_has_role(session_user,'p2b1_review','MEMBER') "
                    "FROM pg_roles WHERE rolname=session_user"
                ).fetchone()
                if (
                    not row
                    or row[:2] != (assignment.db_role, assignment.db_role)
                    or not 160000 <= row[2] < 170000
                    or any(row[3:7])
                    or row[7] is not True
                ):
                    deny()
                with c.transaction():
                    raw = c.execute(
                        "SELECT * FROM ra4b_p2.m1_read_assigned(%s,%s)", (tenant, job_id)
                    ).fetchone()
                    if not raw:
                        deny()
                    locator = raw[0]
                    source, report, html = (bytes(v) for v in raw[1:])
                    for key, value in (("source", source), ("report", report), ("html", html)):
                        if hashlib.sha256(value).hexdigest() != locator[key + "_sha256"]:
                            deny()
                    d = replay(Output(source, report, html, b""))
                    if (
                        d["scope"]["tenant_id"] != tenant
                        or locator["job_id"] != job_id
                        or d["metadata"]["report_id"] != locator["report_id"]
                        or d["metadata"]["version"] != locator["report_version"]
                        or d["approval_status"] != "NOT_APPROVED"
                        or d["shareable"]
                    ):
                        deny()
                return GeneratedReport(locator, source, report, html)
        except Exception:
            deny()

    def _authenticate(self, bearer, tenant, job_id, nonce):
        now = self.clock()
        a = self.anchor
        if type(now) not in (int, float) or not math.isfinite(now) or now <= 0 or now < self.last:
            deny()
        self.last = now
        if (
            type(a) is not TrustAnchor
            or not a.available
            or type(a.expires) is not int
            or a.expires <= now
            or not a.issuer
            or not a.audience
            or type(a.jwks) is not bytes
            or not 0 < len(a.jwks) <= 16384
            or type(bearer) is not str
            or len(bearer) > 8192
            or not bearer.startswith("Bearer ")
            or type(nonce) is not str
            or not 16 <= len(nonce) <= 128
            or type(job_id) is not str
            or str(UUID(job_id)) != job_id
        ):
            deny()
        token = bearer[7:]
        if token.count(".") != 2:
            deny()
        h, p, s = token.split(".")
        header = document(decode(h))
        claims = document(decode(p))
        if (
            set(header) != {"alg", "kid", "typ"}
            or header["alg"] != "EdDSA"
            or header["typ"] != "vrae-test-identity+jwt"
            or type(header["kid"]) is not str
            or not 1 <= len(header["kid"]) <= 64
        ):
            deny()
        jwks = document(a.jwks)
        if set(jwks) != {"keys"} or type(jwks["keys"]) is not list:
            deny()
        keys = {}
        for k in jwks["keys"]:
            if (
                type(k) is not dict
                or set(k) != {"kty", "crv", "use", "alg", "kid", "x"}
                or (k["kty"], k["crv"], k["use"], k["alg"]) != ("OKP", "Ed25519", "sig", "EdDSA")
                or type(k["kid"]) is not str
                or k["kid"] in keys
            ):
                deny()
            keys[k["kid"]] = Ed25519PublicKey.from_public_bytes(decode(k["x"]))
        kid = header["kid"]
        if kid not in keys or kid in a.revoked:
            deny()
        sig = decode(s)
        if len(sig) != 64:
            deny()
        keys[kid].verify(sig, (h + "." + p).encode("ascii"))
        if (
            set(claims) != {"iss", "aud", "sub", "iat", "nbf", "exp", "jti", "nonce"}
            or (claims["iss"], claims["aud"]) != (a.issuer, a.audience)
            or any(type(claims[k]) is not int for k in ("iat", "nbf", "exp"))
            or any(
                type(claims[k]) is not str or not 1 <= len(claims[k]) <= 128
                for k in ("sub", "jti", "nonce")
            )
            or claims["nonce"] != nonce
            or not 0 <= claims["iat"] <= claims["nbf"] < claims["exp"]
            or claims["exp"] - claims["iat"] > 300
            or claims["exp"] <= now - 5
            or claims["nbf"] > now + 5
            or claims["iat"] > now + 5
        ):
            deny()
        self.seen = {k: v for k, v in self.seen.items() if v > now}
        digest = hashlib.sha256((a.issuer + "\0" + claims["jti"]).encode()).digest()
        if digest in self.seen or len(self.seen) >= 4096:
            deny()
        self.seen[digest] = claims["exp"] + 5
        matches = [
            x
            for x in self.assignments
            if type(x) is JobAssignment
            and x.active
            and type(x.expires) is int
            and x.expires > now
            and (x.issuer, x.subject, x.tenant, x.job_id)
            == (a.issuer, claims["sub"], tenant, job_id)
            and x.db_role in ("p2b1_test_a_reviewer", "p2b1_test_a_peer", "p2b1_test_b_reviewer")
        ]
        if len(matches) != 1:
            deny()
        return matches[0]
