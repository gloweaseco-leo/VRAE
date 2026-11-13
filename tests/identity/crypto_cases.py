"""Actual Ed25519 negative matrix. No network or mocked signature verification."""

from dataclasses import replace
import json

import pytest

from tests.identity.issuer import AUDIENCE, ISSUER, NONCE, NOW, Issuer, encode, raw
from vrae.identity import Assignment, IdentityBoundary, IdentityDenied, TrustAnchor
from vrae.identity.boundary import production_port
from vrae.persistence.private_bytes import Locator

LOC = Locator(tenant="tenant-test", source_run="run", report="report", version=1,
              ref_id="ref", target_digest="0" * 64)


def no_database(role):
    pytest.fail("Rejected credential reached the database")


def boundary(issuer, **overrides):
    args = dict(anchor=TrustAnchor(ISSUER, AUDIENCE, issuer.jwks(), NOW + 600),
                assignments=(Assignment(ISSUER, "synthetic-reviewer-1", "test-role", LOC,
                                        NOW + 600),), connect=no_database, clock=lambda: NOW)
    args.update(overrides)
    return IdentityBoundary(**args)


@pytest.mark.parametrize("changes", [
    {"iss": "https://evil.invalid"}, {"aud": "other"}, {"aud": [AUDIENCE]},
    {"exp": NOW - 5}, {"nbf": NOW + 6}, {"iat": NOW + 6},
    {"iat": NOW - 400}, {"exp": True}, {"nbf": None}, {"iat": 1.5},
    {"sub": ""}, {"sub": 4}, {"jti": ""}, {"nonce": "wrong"},
    {"nbf": NOW - 1, "iat": NOW},
    {"iss": None}, {"aud": None}, {"sub": None},
])
def test_claims(changes):
    issuer = Issuer()
    with pytest.raises(IdentityDenied):
        boundary(issuer).check(issuer.token(changes), LOC, nonce=NONCE)


@pytest.mark.parametrize("name", ["iss", "aud", "sub", "exp", "nbf", "iat", "jti", "nonce"])
def test_missing_claim(name):
    issuer = Issuer()
    claims = json.loads(__import__("base64").urlsafe_b64decode(
        issuer.token().split(".")[1] + "=="))
    del claims[name]
    with pytest.raises(IdentityDenied):
        boundary(issuer).check(issuer.token(payload=raw(claims)), LOC, nonce=NONCE)


@pytest.mark.parametrize("patch", [
    {"alg": "none"}, {"alg": "HS256"}, {"alg": "RS256"}, {"kid": "unknown"},
    {"jku": "https://evil.invalid/jwks"}, {"x5u": "file:///secret"},
    {"jwk": {}}, {"crit": ["custom"]}, {"b64": False}, {"typ": "JWT"},
    {"kid": None}, {"alg": None},
])
def test_header(patch):
    issuer = Issuer()
    header = {"alg": "EdDSA", "kid": "old", "typ": "vrae-test-identity+jwt"} | patch
    with pytest.raises(IdentityDenied):
        boundary(issuer).check(issuer.token(header=header), LOC, nonce=NONCE)


@pytest.mark.parametrize("payload", [
    b'{"sub":"a","sub":"b"}', b'{"x":{"a":1,"a":2}}', b'[]', b'null',
    b'{"x":NaN}', b'{"x":Infinity}', b'{', b'\xff', b'[' * 1100,
    b'{"sub":"' + b'x' * 9000 + b'"}',
])
def test_json(payload):
    issuer = Issuer()
    with pytest.raises(IdentityDenied):
        boundary(issuer).check(issuer.token(payload=payload), LOC, nonce=NONCE)


@pytest.mark.parametrize("bearer", [None, "", "bearer a.b.c", "Bearer  a.b.c", "Bearer a.b",
                                    "Bearer a.b.c.d", "Bearer a=.b.c", "Bearer a.b.c\n"])
def test_bearer(bearer):
    with pytest.raises(IdentityDenied):
        boundary(Issuer()).check(bearer, LOC, nonce=NONCE)


@pytest.mark.parametrize("kind", ["tamper", "signature", "key", "duplicate-header"])
def test_signature_and_duplicate_header(kind):
    issuer = Issuer()
    token = issuer.token()
    h, p, s = token[7:].split(".")
    if kind == "tamper":
        claims = json.loads(__import__("base64").urlsafe_b64decode(p + "=="))
        p = encode(raw(claims | {"role": "postgres"}))
    elif kind == "signature":
        s = encode(b"\0" * 64)
    elif kind == "key":
        token = Issuer().token()
        h, p, s = token[7:].split(".")
    else:
        h = encode(b'{"alg":"EdDSA","alg":"none","kid":"old"}')
    with pytest.raises(IdentityDenied):
        boundary(issuer).check("Bearer " + ".".join((h, p, s)), LOC, nonce=NONCE)


@pytest.mark.parametrize("change", [
    {"expires": NOW}, {"available": False}, {"revoked": frozenset({"old"})},
    {"jwks": b'{"keys":[]}'}, {"jwks": b'{}'}, {"jwks": b'{"keys":[],"keys":[]}'},
    {"jwks": b"x" * 17000}, {"jwks": b'{"keys":[{"kty":"RSA"}]}'},
])
def test_trust(change):
    issuer = Issuer()
    anchor = replace(TrustAnchor(ISSUER, AUDIENCE, issuer.jwks(), NOW + 600), **change)
    with pytest.raises(IdentityDenied):
        boundary(issuer, anchor=anchor).check(issuer.token(), LOC, nonce=NONCE)


@pytest.mark.parametrize("clock", [lambda: float("nan"), lambda: float("inf"), lambda: -1])
def test_clock(clock):
    issuer = Issuer()
    with pytest.raises(IdentityDenied):
        boundary(issuer, clock=clock).check(issuer.token(), LOC, nonce=NONCE)


def test_no_credential_in_exception(capsys):
    issuer = Issuer()
    credential = issuer.token({"sub": "private-identity-marker"})
    with pytest.raises(IdentityDenied) as caught:
        boundary(issuer).check(credential, LOC, nonce=NONCE)
    assert str(caught.value) == "P2B2A_IDENTITY_DENIED"
    assert caught.value.__suppress_context__
    assert capsys.readouterr() == ("", "")
    with pytest.raises(IdentityDenied):
        production_port(credential)


def test_missing_anchor_and_duplicate_key_ids():
    issuer = Issuer()
    with pytest.raises(IdentityDenied):
        boundary(issuer, anchor=None).check(issuer.token(), LOC, nonce=NONCE)
    keys = json.loads(issuer.jwks())
    keys["keys"].append(keys["keys"][0])
    anchor = TrustAnchor(ISSUER, AUDIENCE, raw(keys), NOW + 600)
    with pytest.raises(IdentityDenied):
        boundary(issuer, anchor=anchor).check(issuer.token(), LOC, nonce=NONCE)
