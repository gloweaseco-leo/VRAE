"""Synthetic keys only, inside /private tmpfs in a disposable network-none container."""
from datetime import datetime, UTC, timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization as ser
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

from integration.vf_preview_handoff.stage_identity import stage

SHA = "a" * 40


@pytest.fixture
def private():
    with tempfile.TemporaryDirectory(dir="/private") as directory:
        root = Path(directory)
        root.chmod(0o700)
        def save(name, value):
            p = root / name
            p.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
            p.chmod(0o600)
        now = datetime.now(UTC)
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SYNTHETIC ONLY")])
        ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
              .not_valid_after(now + timedelta(hours=2)).add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
              .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                  data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
                  encipher_only=None, decipher_only=None), True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
              .sign(key, hashes.SHA256()))
        save("client-ca.pem", ca.public_bytes(ser.Encoding.PEM))
        save("client-ca-key.pem", key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption()))
        save("server-ca.pem", ca.public_bytes(ser.Encoding.PEM))
        save("api.json", {"source_sha": SHA, "target_intake_enabled": True, "bindings": [
            {"kind": "APP", "role": "existing_api", "tenant_id": "synthetic", "verification_keys": {}}]})
        save("manifest.json", {"source_sha": SHA})
        save("deployment-intent.json", {"document": {"not_before": (now - timedelta(minutes=1)).isoformat(),
              "expires_at": (now + timedelta(minutes=45)).isoformat()}})
        yield root


def issue(root, sha=SHA, role="vf_preview_173test"):
    return stage(root, root / "server-ca.pem", sha, role)


def test_unique_bound_pair_and_no_registration(private):
    before = (private / "api.json").read_bytes()
    receipt = issue(private)
    output = private / "vf_preview_173test"
    cert = x509.load_pem_x509_certificate((output / "VRAE_DIAGNOSIS_CLIENT_CERT_PEM").read_bytes())
    key = ser.load_pem_private_key((output / "VRAE_DIAGNOSIS_CLIENT_KEY_PEM").read_bytes(), None)
    assert cert.public_key().public_numbers() == key.public_key().public_numbers()
    assert ExtendedKeyUsageOID.CLIENT_AUTH in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    binding = json.loads((output / "binding.private.json").read_bytes())
    assert binding["service_sha256"] == hashlib.sha256((output / "VRAE_DIAGNOSIS_BEARER").read_bytes()).hexdigest()
    assert binding["client_certificate_sha256"] == receipt["client_certificate_sha256"]
    assert receipt["expires_at"] == cert.not_valid_after_utc.isoformat()
    assert cert.not_valid_after_utc <= datetime.now(UTC) + timedelta(minutes=45)
    assert (private / "api.json").read_bytes() == before
    assert receipt["state"] == "STAGED_NOT_REGISTERED"
    assert not any(secret in json.dumps(receipt) for secret in (binding["password"], (output / "VRAE_DIAGNOSIS_BEARER").read_text()))
    assert all(p.stat().st_mode & 0o077 == 0 for p in output.iterdir())


def test_wrong_sha_denied_without_output(private):
    with pytest.raises(ValueError):
        issue(private, "b" * 40)
    assert not (private / "vf_preview_173test").exists()


def test_world_readable_key_denied(private):
    (private / "client-ca-key.pem").chmod(0o644)
    with pytest.raises(PermissionError):
        issue(private)


def test_symlink_ca_denied(private):
    (private / "client-ca.pem").rename(private / "real.pem")
    (private / "client-ca.pem").symlink_to(private / "real.pem")
    with pytest.raises(PermissionError):
        issue(private)


def test_expired_authority_denied(private):
    p = private / "deployment-intent.json"
    doc = json.loads(p.read_bytes())
    doc["document"]["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    p.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        issue(private)


def test_no_overwrite_of_existing_bundle(private):
    issue(private)
    before = (private / "vf_preview_173test/VRAE_DIAGNOSIS_CLIENT_KEY_PEM").read_bytes()
    with pytest.raises(FileExistsError):
        issue(private)
    assert (private / "vf_preview_173test/VRAE_DIAGNOSIS_CLIENT_KEY_PEM").read_bytes() == before


def test_no_nonroot_issuance(private, monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 10001)
    with pytest.raises(PermissionError):
        issue(private)


def add_binding(root, binding):
    p = root / "api.json"
    cfg = json.loads(p.read_bytes())
    cfg["bindings"].append(binding)
    p.write_text(json.dumps(cfg))


def test_health_only_binding_is_never_selected_or_copied(private):
    add_binding(private, {"kind": "APP", "role": "temporary_probe", "tenant_id": "synthetic",
                         "health_probe": {"expires_at": "2099-01-01T00:00:00+00:00"}})
    receipt = issue(private)
    assert receipt["source_role"] == "existing_api"
    b = json.loads((private / "vf_preview_173test/binding.private.json").read_bytes())
    assert "health_probe" not in b


def test_explicit_business_source_role_allows_safe_rotation(private):
    add_binding(private, {"kind": "APP", "role": "prior_preview", "tenant_id": "synthetic",
                         "verification_keys": {}})
    with pytest.raises(ValueError):
        issue(private)
    receipt = stage(private, private / "server-ca.pem", SHA, "vf_preview_rotate", source_role="existing_api")
    assert receipt["source_role"] == "existing_api"


def test_health_source_role_explicitly_requested_still_denied(private):
    add_binding(private, {"kind": "APP", "role": "temporary_probe", "tenant_id": "synthetic",
                         "health_probe": {"expires_at": "2099-01-01T00:00:00+00:00"}})
    with pytest.raises(ValueError):
        stage(private, private / "server-ca.pem", SHA, "vf_preview_denied", source_role="temporary_probe")
