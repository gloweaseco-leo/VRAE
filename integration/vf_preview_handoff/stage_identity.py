"""Root-only OFFLINE staging; never registers actors or changes a running service.

Execute only by the single authorized operator, inside the existing private ext4
volume. A staged binding is NOT a usable service identity until registered.
"""
import argparse
from datetime import datetime, UTC, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization as ser
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def guarded(path, directory=False):
    path = Path(path)
    # Check all ancestors too: no traversal through symlink or writable parent.
    for parent in [*reversed(path.parents), path]:
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise PermissionError("ROOT_PRIVATE_PATH_REQUIRED")
    info = path.stat()
    if info.st_mode & 0o077 or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise PermissionError("ROOT_PRIVATE_INPUT_REQUIRED")
    return path


def stage(root, server_ca, expected_sha, role, hours=1):
    if os.name != "posix" or os.geteuid() != 0:
        raise PermissionError("AUTHORIZED_ROOT_EXT4_OPERATOR_REQUIRED")
    if not re.fullmatch(r"[a-f0-9]{40}", expected_sha) or not re.fullmatch(r"vf_preview_[a-z0-9_]{4,40}", role):
        raise ValueError("EXACT_SHA_AND_NEW_PREVIEW_ROLE_REQUIRED")
    if not 0 < hours <= 2:
        raise ValueError("BOUNDED_LIFETIME_REQUIRED")
    root = guarded(root, True)
    def read(name):
        return guarded(root / name).read_bytes()
    api = json.loads(read("api.json"))
    manifest = json.loads(read("manifest.json"))
    intent = json.loads(read("deployment-intent.json"))["document"]
    if api["source_sha"] != expected_sha or manifest["source_sha"] != expected_sha:
        raise ValueError("OPERATOR_MUST_VERIFY_RUNNING_SHA_FIRST")
    if not api.get("target_intake_enabled") or any(b["role"] == role for b in api["bindings"]):
        raise ValueError("NEW_ROLE_AND_CURRENT_INTAKE_REQUIRED")
    originals = [b for b in api["bindings"] if b["kind"] == "APP" and not b.get("port")]
    if len(originals) != 1:
        raise ValueError("SELECT_EXISTING_TENANT_EXPLICITLY_BEFORE_STAGING")
    original = originals[0]
    ca = x509.load_pem_x509_certificate(read("client-ca.pem"))
    ca_key = ser.load_pem_private_key(read("client-ca-key.pem"), password=None)
    public = lambda k: k.public_bytes(ser.Encoding.DER, ser.PublicFormat.SubjectPublicKeyInfo)
    if (not ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        or public(ca.public_key()) != public(ca_key.public_key())):
        raise ValueError("CURRENT_CLIENT_CA_KEY_REQUIRED")
    now = datetime.now(UTC)
    end = min(now + timedelta(hours=hours), ca.not_valid_after_utc, datetime.fromisoformat(intent["expires_at"]))
    if ca.not_valid_before_utc > now or datetime.fromisoformat(intent["not_before"]) > now or end <= now + timedelta(minutes=5):
        raise ValueError("CURRENT_AUTHORITY_WITH_FIVE_MINUTES_REMAINING_REQUIRED")
    # This is the server verification chain, NOT the client-issuing CA.
    server_ca_bytes = guarded(server_ca).read_bytes()
    x509.load_pem_x509_certificate(server_ca_bytes)
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, role)]))
            .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(max(now - timedelta(minutes=1), ca.not_valid_before_utc)).not_valid_after(end)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), False)
            .sign(ca_key, hashes.SHA256()))
    bearer = secrets.token_urlsafe(32)
    fingerprint = cert.fingerprint(hashes.SHA256()).hex()
    binding = {"role": role, "password": secrets.token_urlsafe(32), "kind": "APP",
               "tenant_id": original["tenant_id"], "verification_keys": original["verification_keys"],
               "service_sha256": hashlib.sha256(bearer.encode()).hexdigest(),
               "client_certificate_sha256": fingerprint}
    receipt = {"state": "STAGED_NOT_REGISTERED", "role": role, "source_sha": expected_sha,
               "client_certificate_sha256": fingerprint, "not_before": cert.not_valid_before_utc.isoformat(),
               "expires_at": end.isoformat(), "branch": "feature/vf-b-offline-g1-adapter"}
    output = root / role
    output.mkdir(mode=0o700)  # exclusive, never overwrite an earlier issuance
    def write(name, value):
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(value)
            f.flush()
            os.fsync(f.fileno())
    values = {"VRAE_DIAGNOSIS_CA_PEM": server_ca_bytes,
              "VRAE_DIAGNOSIS_CLIENT_CERT_PEM": cert.public_bytes(ser.Encoding.PEM),
              "VRAE_DIAGNOSIS_CLIENT_KEY_PEM": key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption()),
              "VRAE_DIAGNOSIS_BEARER": bearer.encode(), "VRAE_DIAGNOSIS_SOURCE_SHA": expected_sha.encode()}
    for name, value in values.items():
        write(name, value)
    write("binding.private.json", json.dumps(binding).encode())
    write("receipt.json", json.dumps(receipt).encode())
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--server-ca", required=True)
    p.add_argument("--expected-source-sha", required=True)
    p.add_argument("--role", required=True)
    a = p.parse_args()
    try:
        print(json.dumps(stage(a.root, a.server_ca, a.expected_source_sha, a.role)))
    except Exception:
        # Paths, config, exceptions and credential values are never printed.
        print('{"state":"STAGING_REFUSED","details":"operator_private_review_required"}')
        raise SystemExit(1)


if __name__ == "__main__":
    main()
