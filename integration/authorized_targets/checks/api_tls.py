"""Owned test service/client PKI for actual cross-container mutual TLS."""

from datetime import datetime, UTC, timedelta
import hashlib
from ipaddress import ip_address
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID


def create(directory, validity_hours=2):
    root = Path(directory)
    root.mkdir(mode=0o700, exist_ok=True)
    now = datetime.now(UTC)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CONTROLLED VRAE API CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=validity_hours + 2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
        .add_extension(
            x509.KeyUsage(True, False, False, False, False, True, True, None, None), True
        )
        .sign(key, hashes.SHA256())
    )
    (root / "ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    out = {"ca": str(root / "ca.pem")}
    for role in ("facade", "client", "other-client"):
        leaf = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "controlled-vrae-" + role)])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(name)
            .public_key(leaf.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=validity_hours))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf.public_key()), False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False
            )
            .add_extension(
                x509.ExtendedKeyUsage(
                    [
                        ExtendedKeyUsageOID.SERVER_AUTH
                        if role == "facade"
                        else ExtendedKeyUsageOID.CLIENT_AUTH
                    ]
                ),
                False,
            )
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("vrae-api"),
                        x509.DNSName("localhost"),
                        x509.IPAddress(ip_address("127.0.0.1")),
                    ]
                ),
                False,
            )
            .sign(key, hashes.SHA256())
        )
        cp = root / (role + ".pem")
        kp = root / (role + "-key.pem")
        cp.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        kp.write_bytes(
            leaf.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        kp.chmod(0o600)
        out[role] = {
            "certificate": str(cp),
            "key": str(kp),
            "der_sha256": hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest(),
        }
    return out
