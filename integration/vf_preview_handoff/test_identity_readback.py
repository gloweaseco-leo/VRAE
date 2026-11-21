"""Actual local TLS, synthetic HTTP authority only; never a Vercel/PG receipt."""
from contextlib import contextmanager
from datetime import datetime, UTC, timedelta
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socket
import ssl
from threading import Thread

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization as ser
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from integration.vf_preview_handoff.check_identity import run, HOST, API, MEDIA
from integration.vf_preview_handoff.test_stage_identity import private, issue, SHA  # noqa: F401


@contextmanager
def mock_tls(root, *, health_only=False, source_sha=SHA):
    issue(root, role="vf_preview_control")
    issue(root)
    control = root / "vf_preview_control"
    preview = root / "vf_preview_173test"
    def load(folder, name):
        return (folder / name).read_bytes()
    def pair(folder):
        cert = x509.load_pem_x509_certificate(load(folder, "VRAE_DIAGNOSIS_CLIENT_CERT_PEM"))
        return cert.fingerprint(hashes.SHA256()).hex(), load(folder, "VRAE_DIAGNOSIS_BEARER").decode()
    allowed = [pair(control), pair(preview)]
    control_config = root / "control.private.json"
    control_config.write_text(json.dumps({"host": HOST, "source_sha": SHA,
        "certificate": str(control / "VRAE_DIAGNOSIS_CLIENT_CERT_PEM"),
        "key": str(control / "VRAE_DIAGNOSIS_CLIENT_KEY_PEM"),
        "api_bearer": load(control, "VRAE_DIAGNOSIS_BEARER").decode()}))
    control_config.chmod(0o600)
    ca = x509.load_pem_x509_certificate((root / "client-ca.pem").read_bytes())
    key = ser.load_pem_private_key((root / "client-ca-key.pem").read_bytes(), None)
    now = datetime.now(UTC)
    server_key = ec.generate_private_key(ec.SECP256R1())
    server_cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOST)]))
        .issuer_name(ca.subject).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(minutes=30))
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(HOST)]), False).sign(key, hashes.SHA256()))
    server_path = root / "server.pem"
    server_path.write_bytes(server_cert.public_bytes(ser.Encoding.PEM))
    server_path.chmod(0o600)
    server_key_path = root / "server-key.pem"
    server_key_path.write_bytes(server_key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption()))
    server_key_path.chmod(0o600)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # never log any request or peer credentials

        def do_GET(self):
            cert_hash = hashlib.sha256(self.connection.getpeercert(binary_form=True)).hexdigest()
            auth = self.headers.get("Authorization", "")[7:]
            authorized = (cert_hash, auth) in allowed
            if health_only and self.path == "/v1/openapi.json" and cert_hash == allowed[1][0]:
                authorized = False
            status = 200 if authorized else 403
            body = ({"status": "READY", "source_sha": source_sha} if self.path == "/health/ready" else
                    {"paths": {p: {} for p in ("/v1/target-applications", "/v1/target-applications/authorize", "/v1/diagnoses")}})
            raw = json.dumps(body if authorized else {"error": "DENIED"}).encode()
            self.send_response(status)
            for key, value in {"Content-Type": "application/json" if authorized else MEDIA,
                               "Content-Length": str(len(raw)), "X-VRAE-API-Version": API,
                               "X-VRAE-Source-SHA": source_sha, "Cache-Control": "no-store"}.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(raw)

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(server_path, server_key_path)
    ctx.load_verify_locations(root / "client-ca.pem")
    ctx.verify_mode = ssl.CERT_REQUIRED
    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield preview, control_config, server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_actual_tls_pairs_cross_pairs_and_missing_cert(private):
    with mock_tls(private) as (bundle, control, port):
        result = run(bundle, control, _test_port=port, _test_connect_host="127.0.0.1")
    assert result["passed"] is True, result
    assert len(result["events"]) == 7
    assert all(e["passed"] for e in result["events"])
    assert result["events"][-1]["tls_rejected"] is True
    assert result["vercel_egress_proven"] is False
    serialized = json.dumps(result)
    for folder in (private / "vf_preview_control", private / "vf_preview_173test"):
        assert (folder / "VRAE_DIAGNOSIS_BEARER").read_text() not in serialized
        assert "PRIVATE KEY" not in serialized
    print(json.dumps({"evidence_kind": "ISOLATED_SYNTHETIC_TLS_NOT_RUNTIME_OR_VERCEL", "readback": result}))


def test_health_only_registration_cannot_pass_preview_readback(private):
    with mock_tls(private, health_only=True) as (bundle, control, port):
        result = run(bundle, control, _test_port=port, _test_connect_host="127.0.0.1")
    assert result["passed"] is False
    assert result["events"][-1]["case"] == "preview_openapi"
    assert result["events"][-1]["status"] == 403


def test_runtime_sha_drift_is_a_failed_readback(private):
    with mock_tls(private, source_sha="b" * 40) as (bundle, control, port):
        result = run(bundle, control, _test_port=port, _test_connect_host="127.0.0.1")
    assert result["passed"] is False
    assert result["events"][-1]["passed"] is False


def test_connection_refused_is_never_counted_as_tls_denial(private):
    with mock_tls(private) as (bundle, control, _port):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))  # reserve a port without listening
            result = run(bundle, control, _test_port=reservation.getsockname()[1], _test_connect_host="127.0.0.1")
    assert result["passed"] is False
    assert not any(e.get("tls_rejected") for e in result["events"])
