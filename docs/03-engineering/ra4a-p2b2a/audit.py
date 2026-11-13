"""Public-output privacy/scope gate and disposable Ed25519 integrity seal.

The seal is NOT a human signature, identity proof, approval or trusted timestamp.
The private evidence-signing key is generated in memory and discarded.
"""

import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = "a17d02f16a16acd7214815fce02747509c31f7bd"
ALLOWED = ("vrae/identity/", "tests/identity/", "integration/ra4a/p2b2a/",
           "docs/03-engineering/ra4a-p2b2a/")
EXACT = {"requirements-ra4a-p2b2a.lock", ".github/workflows/ra4a-p2b2a-identity.yml"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def main():
    changed = set(git("diff", "--name-only", BASE).splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    assert changed and all(p in EXACT or p.startswith(ALLOWED) for p in changed), "SCOPE_DENIED"
    patterns = (
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
        rb"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}",
        rb"AKIA[0-9A-Z]{16}",
        rb"[A-Za-z]:\\{1,2}Users\\{1,2}[A-Za-z0-9_.-]+\\{1,2}",
        rb"[A-Za-z]:/Users/[A-Za-z0-9_.-]+/",
    )
    files = []
    for name in sorted(changed):
        p = ROOT / name
        if not p.is_file() or p.name in ("INTEGRITY.json", "PUBLIC_GATE.json"):
            continue
        raw = p.read_bytes()
        assert not any(re.search(pattern, raw) for pattern in patterns), "PUBLIC_SECRET_SCAN_DENIED: " + name
        assert ".runtime" not in p.parts and "__pycache__" not in p.parts
        files.append({"path": name, "byte_sha256": hashlib.sha256(raw).hexdigest(),
                      "lf_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
                      "bytes": len(raw)})
    payload = {"base": BASE, "head": git("rev-parse", "HEAD"),
               "parents": git("show", "-s", "--format=%P", "HEAD").split(),
               "scope_gate": "PASS", "automated_secret_patterns": "PASS",
               "files": files, "authority": "TEST_ONLY_INTEGRITY_NOT_HUMAN_APPROVAL"}
    raw = (json.dumps(payload, indent=2) + "\n").encode()
    (HERE / "PUBLIC_GATE.json").write_bytes(raw)
    key = Ed25519PrivateKey.generate()
    signature = key.sign(raw)
    key.public_key().verify(signature, raw)
    seal = {"payload": "PUBLIC_GATE.json", "sha256": hashlib.sha256(raw).hexdigest(),
            "public_ed25519": base64.b64encode(key.public_key().public_bytes_raw()).decode(),
            "signature": base64.b64encode(signature).decode(),
            "meaning": "Disposable integrity seal only; no human or production authority"}
    (HERE / "INTEGRITY.json").write_text(json.dumps(seal, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scope": "PASS", "privacy_pattern_gate": "PASS", "files": len(files),
                      "bytes": sum(p["bytes"] for p in files), "manifest_sha256": seal["sha256"]}))


if __name__ == "__main__":
    main()
