"""Exercise raw mTLS, certificate binding and safe host/Funnel controls."""
import hashlib
import http.server
import ssl
import threading
import pytest
from infra.windows_service import external_probe, funnel, host
from integration.authorized_targets.checks.api_tls import create


def test_probe_requires_actual_mtls_bearer_profile_and_hostname(tmp_path):
    import json
    pki = create(tmp_path / "pki")
    correct = pki["client"]["der_sha256"]

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            peer = hashlib.sha256(self.connection.getpeercert(binary_form=True)).hexdigest()
            allowed = peer == correct and self.headers.get("Authorization") == "Bearer valid"
            data = {"status": "READY", "ready": True, "customer_release": True}
            raw = json.dumps(data if allowed else {"denied": True}).encode()
            self.send_response(200 if allowed else 403)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("X-VRAE-Source-SHA", "a" * 40)
            self.send_header("X-VRAE-Scope", "VERIFIED_HUMAN_CUSTOMER_REPORT")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(pki["facade"]["certificate"], pki["facade"]["key"])
    context.load_verify_locations(pki["ca"])
    context.verify_mode = ssl.CERT_REQUIRED
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cfg = {
        "host": "localhost", "ca": pki["ca"], "source_sha": "a"*40,
        "certificate": pki["client"]["certificate"], "key": pki["client"]["key"],
        "other_certificate": pki["other-client"]["certificate"], "other_key": pki["other-client"]["key"],
        "api_bearer": "valid", "review_bearer": "valid",
        "api_port": server.server_port, "review_port": server.server_port,
    }
    try:
        result = external_probe.run(cfg)
        assert len(result["events"]) == 8
        assert all(e["passed"] for e in result["events"])
        assert result["external_network"] is False
        assert not any("valid" in str(e) for e in result["events"])
        with pytest.raises(ssl.SSLCertVerificationError):
            external_probe.run({**cfg,"host":"not-this-server.invalid"},connect_host="127.0.0.1")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_existing_tls_terminated_or_unrelated_funnel_is_never_overwritten(monkeypatch):
    monkeypatch.setattr(funnel,"settings",lambda:{"TCP":{"443":{"HTTPS":True}}})
    changed=[]
    monkeypatch.setattr(funnel,"invoke",lambda *a:changed.append(a))
    with pytest.raises(PermissionError,match="EXISTING_FUNNEL_LISTENER_CONFLICT"):
        funnel.expose("actual.example.ts.net",28769,28770)
    assert not changed


@pytest.mark.parametrize("directory",["/mnt/c/secret","/","/etc","/etc/vrae-service/../other","C:/config"])
def test_private_keys_cannot_be_written_to_shared_windows_paths(directory):
    with pytest.raises(ValueError,match="ROOT_EXT4_CONFIG_PATH_REQUIRED"):
        host.private_path(directory)


def test_certificate_injection_passes_private_material_only_on_stdin(monkeypatch):
    calls=[]
    monkeypatch.setattr(host,"wsl",lambda *a,**kw:calls.append((a,kw)))
    secret=b"private-test-key"
    host.put_private("VRAE-Local","/etc/vrae-service","server-key.pem",secret)
    assert secret.decode() not in str(calls[0][0])
    assert calls[0][1]["data"]==secret
