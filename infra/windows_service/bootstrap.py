"""Fresh operator-owned configuration; no customer grants or human identity fabricated."""
import argparse
import base64
from datetime import datetime, UTC, timedelta
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization as ser
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from contracts.l2_launch.contract import canonical
from integration.authorized_targets.authority import token_hash


def generate(root, hostname, image):
    if os.geteuid() != 0 or root.is_symlink():
        raise PermissionError("ROOT_EXT4_OPERATOR_REQUIRED")
    root.chmod(0o700)
    if (root / "manifest.json").exists():
        raise PermissionError("NEVER_OVERWRITE_EXISTING_DEPLOYMENT")
    now = datetime.now(UTC)
    end = now + timedelta(days=1)
    expiry = end.isoformat()
    tenant = "vrae-invited"
    source_class = "EXPLICIT_CUSTOMER_AUTHORIZATION"
    sha = Path("/work/infra/linux_service/source-sha").read_text().strip()

    def save(name, data):
        fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data if isinstance(data, bytes) else canonical(data))

    def public(key):
        return key.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw).hex()

    def sign(key, kid, doc):
        return {"key_id": kid, "document": doc, "signature": key.sign(canonical(doc)).hex()}

    def key_pem(key):
        return key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption())

    keys = {n: ed25519.Ed25519PrivateKey.generate() for n in ("source", "deployment", "permission", "report", "identity")}
    for name, key in keys.items():
        save(name + "-key", key.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption()).hex().encode())
    # The deployment key was already stored by the loop; do not duplicate it.
    save("trust.json", {"keys": {name: {"role": role, "source_class": source_class,
        "public": public(keys[name]), "revoked": False}
        for name, role in (("source", "SOURCE_ADMIN"), ("deployment", "DEPLOYMENT_OWNER"))}})
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "VRAE Windows service client CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(end)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), True).sign(ca_key, hashes.SHA256()))
    save("client-ca.pem", ca.public_bytes(ser.Encoding.PEM))
    save("client-ca-key.pem", key_pem(ca_key))
    fingerprints = {}
    for name in ("client", "other-client"):
        key = ec.generate_private_key(ec.SECP256R1())
        cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "VRAE " + name)]))
            .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(end)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), False)
            .sign(ca_key, hashes.SHA256()))
        save(name + ".pem", cert.public_bytes(ser.Encoding.PEM))
        save(name + "-key.pem", key_pem(key))
        fingerprints[name] = hashlib.sha256(cert.public_bytes(ser.Encoding.DER)).hexdigest()
    verification = {"permission": {"public": public(keys["permission"]), "tenant": tenant,
        "role": "PERMISSION_AUTHORITY", "subject": "vrae-operator-permission", "revoked": False}}
    bindings, bearers = {}, {}
    for name, port in (("api", None), ("worker", None), ("review", "REVIEW"), ("ai", "AI")):
        b = {"role": "vrae_windows_" + name, "password": secrets.token_urlsafe(32),
             "kind": "WORKER" if name == "worker" else "APP", "tenant_id": tenant}
        if port:
            b["port"] = port
        if name in ("api", "review"):
            bearers[name] = secrets.token_urlsafe(32)
            b.update(service_sha256=token_hash(bearers[name]), client_certificate_sha256=fingerprints["client"])
        if name == "api":
            b["verification_keys"] = verification
        bindings[name] = b
    base = {"kind": "APP", "authority": "AUTHORIZED_TARGET_V1", "source_sha": sha}
    for name, port in (("api", 8769), ("review", 8770)):
        cfg = {**base, "bindings": [bindings[name]], "certificate": "server.pem",
            "certificate_key": "server-key.pem", "max_inflight": 4,
            "transport": {"bind": "0.0.0.0", "port": port,
                "hosts": [hostname, hostname + (":8443" if name == "review" else ":443")],
                "origins": [], "mtls": True, "client_ca": "client-ca.pem"}}
        if name == "review":
            cfg.update(report_profile="VERIFIED_HUMAN_CUSTOMER_REPORT", ledger_root="/ledger")
        save(name + ".json", cfg)
    save("worker.json", {"kind": "WORKER", "authority": "AUTHORIZED_TARGET_V1",
        "bindings": [bindings["worker"]], "workload": {"kind": "AUTHORIZED_EGRESS_V2"}})
    save("ai.json", {**base, "bindings": [bindings["ai"]]})
    save("pg-password", secrets.token_urlsafe(40).encode())
    save("provision.json", [{"tenant_id": tenant, "expires_at": expiry, "max_pending": 8,
        "actors": list(bindings.values()), "plans": [], "invitations": []}])
    save("authorizations.json", [])
    intent = {"contract": "vrae.linux-service-intent.v1", "source_class": source_class,
        "purpose": "READONLY_DIAGNOSIS", "not_before": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": expiry, "authorization_hashes": [], "destination_ips": [],
        "nameservers": ["1.1.1.1", "8.8.8.8"], "deployment_go": "GRANTED",
        "source_network_fee_go": "GRANTED", "model_fee_go": "NOT_GRANTED"}
    save("deployment-intent.json", sign(keys["deployment"], "deployment", intent))
    save("source-ca.pem", Path("/etc/ssl/certs/ca-certificates.crt").read_bytes())
    identity_public = base64.urlsafe_b64encode(bytes.fromhex(public(keys["identity"]))).decode().rstrip("=")
    directory = {"issuer": "https://" + hostname + "/local-verified-identity", "audience": "vrae-verified-reports",
        "jwks": {"keys": [{"kty": "OKP", "crv": "Ed25519", "use": "sig", "alg": "EdDSA",
            "kid": "windows-identity", "x": identity_public}]},
        "mode": "VERIFIED_DIRECTORY", "expires": int(time.time()) + 86390, "people": []}
    report = {"contract": "vrae.verified-report-authority.v1", "profile": "VERIFIED_HUMAN_CUSTOMER_REPORT",
        "reference": "WINDOWS_OPERATOR_AUTHORITY_PENDING_VERIFIED_PERSON_ENROLLMENT",
        "allowed_source_classes": [source_class], "not_before": intent["not_before"],
        "expires_at": expiry, "directory": directory}
    save("report-trust.json", {"keys": {"report": {"role": "REPORT_AUTHORITY", "revoked": False,
                                                 "public": public(keys["report"])}}})
    save("report-authority.json", sign(keys["report"], "report", report))
    save("caller.json", {"host": hostname, "source_sha": sha, "api_bearer": bearers["api"],
        "review_bearer": bearers["review"], "certificate": str(root / "client.pem"),
        "key": str(root / "client-key.pem"), "other_certificate": str(root / "other-client.pem"),
        "other_key": str(root / "other-client-key.pem")})
    save("manifest.json", {"contract": "vrae.linux-service.v1", "source_sha": sha, "image": image,
        "source_class": source_class, "network_mode": "isolated-egress",
        "publish": ["127.0.0.1:28769:8769", "127.0.0.1:28770:8770"]})
    return {"source_sha": sha, "single_worker": True, "max_pending_per_tenant": 8,
        "customer_identity_enrolled": False, "source_targets_authorized": 0,
        "model_dispatch_enabled": False, "public_acceptance": "NOT_READY"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hostname", required=True)
    p.add_argument("--image", required=True)
    a = p.parse_args()
    print(json.dumps(generate(Path(os.environ["VRAE_PRIVATE_ROOT"]), a.hostname, a.image)))


if __name__ == "__main__":
    main()

