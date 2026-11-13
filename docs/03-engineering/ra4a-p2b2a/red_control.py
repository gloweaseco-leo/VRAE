"""Explicit RED mutation control: disabling verification MUST fail security tests.

This deliberately broken in-memory verifier is NOT real signature evidence.
Normal green suites always use the cryptography implementation without patching.
No source file, accepted test, or persistent DB is changed.
"""

import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

pytest = importlib.import_module("pytest")
boundary = importlib.import_module("vrae.identity.boundary")


class DisabledSignatureVerification:
    @staticmethod
    def from_public_bytes(raw):
        return DisabledSignatureVerification()

    def verify(self, signature, data):
        return None


if __name__ == "__main__":
    boundary.Ed25519PublicKey = DisabledSignatureVerification
    raise SystemExit(pytest.main([
        "-q", "tests/identity/crypto_cases.py", "-k", "signature_and_duplicate_header",
        "--junitxml=" + sys.argv[1],
    ]))
