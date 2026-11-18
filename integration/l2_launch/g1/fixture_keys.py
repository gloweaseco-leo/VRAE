"""Controlled G0 fixture assertions. Private signer only in trusted supervisor."""

from datetime import datetime, UTC, timedelta
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from contracts.l2_launch.contract import canonical, digest, FixtureVerifier, TrustedFixtureKey

ROLES = {
    "permission": ("PERMISSION_AUTHORITY", "g1-synthetic-permission-authority"),
    "owner": ("OWNER", "g1-synthetic-owner-not-human"),
    "storage": ("VF_STORAGE_SERVICE", "g1-synthetic-vf-storage-not-real-receipt"),
}


class FixtureAuthority:
    def __init__(self):
        self.keys = {name: Ed25519PrivateKey.generate() for name in ROLES}

    def public(self):
        return {
            name: {
                "public": key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
                "tenant": "tenant-test",
                "role": ROLES[name][0],
                "subject": ROLES[name][1],
                "revoked": False,
            }
            for name, key in self.keys.items()
        }

    def sign(self, key, purpose, document, *, seconds=900):
        now = datetime.now(UTC)
        value = {
            "alg": "Ed25519",
            "key_id": key,
            "claim": {
                "audience": "vrae-launch-r0-contract",
                "purpose": purpose,
                "tenant_id": "tenant-test",
                "subject_ref": ROLES[key][1],
                "document_sha256": digest(document),
                "issued_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=seconds)).isoformat(),
            },
        }
        return {**value, "signature": self.keys[key].sign(canonical(value)).hex()}


def verifier(public):
    return FixtureVerifier(
        {
            key: TrustedFixtureKey(
                bytes.fromhex(row["public"]),
                row["tenant"],
                row["subject"],
                row["role"],
                row["revoked"],
            )
            for key, row in public.items()
        }
    )
