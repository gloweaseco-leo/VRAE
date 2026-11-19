"""Controlled test permission issuer; never human/Owner approval."""

from datetime import datetime, UTC, timedelta
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from contracts.l2_launch.contract import canonical, digest


class Issuer:
    def __init__(self, tenant):
        self.tenant = tenant
        self.key = Ed25519PrivateKey.generate()

    def public(self):
        return {
            "permission": {
                "public": self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
                "tenant": self.tenant,
                "role": "PERMISSION_AUTHORITY",
                "subject": "controlled-permission-issuer",
                "revoked": False,
            }
        }

    def sign(self, key, purpose, document):
        now = datetime.now(UTC)
        d = {
            "alg": "Ed25519",
            "key_id": "permission",
            "claim": {
                "audience": "vrae-launch-r0-contract",
                "purpose": purpose,
                "tenant_id": self.tenant,
                "subject_ref": "controlled-permission-issuer",
                "document_sha256": digest(document),
                "issued_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=15)).isoformat(),
            },
        }
        return {**d, "signature": self.key.sign(canonical(d)).hex()}
