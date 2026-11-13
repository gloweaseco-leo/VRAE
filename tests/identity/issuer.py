"""Disposable signer exclusively in test code, never in the request boundary."""

import base64
import json
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ISSUER = "https://local-issuer.test.invalid"
AUDIENCE = "vrae-p2b2a-test-only"
NOW = 1800000000
NONCE = "server-held-challenge-0001"


def encode(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def raw(value):
    return json.dumps(value, separators=(",", ":")).encode()


class Issuer:
    def __init__(self):
        self.keys = {k: Ed25519PrivateKey.generate() for k in ("old", "new")}

    def jwks(self):
        return raw({"keys": [
            {"kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "use": "sig",
             "kid": kid, "x": encode(key.public_key().public_bytes_raw())}
            for kid, key in self.keys.items()
        ]})

    def token(self, changes=None, header=None, payload=None, kid="old"):
        claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "synthetic-reviewer-1",
                  "iat": NOW, "nbf": NOW, "exp": NOW + 120,
                  "jti": uuid.uuid4().hex, "nonce": NONCE}
        claims.update(changes or {})
        h = encode(raw(header or {"alg": "EdDSA", "kid": kid,
                                  "typ": "vrae-test-identity+jwt"}))
        p = encode(payload if payload is not None else raw(claims))
        data = (h + "." + p).encode()
        return "Bearer " + h + "." + p + "." + encode(self.keys[kid].sign(data))
