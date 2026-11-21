"""Diagnosis-only mTLS readback by the SINGLE authorized private-volume operator.

Codex1 must not invoke this against Codex3's volume. No invitation, report, model,
registry mutation or credential export occurs. Only non-secret receipts print.
"""
import argparse
import hashlib
import http.client
import json
import re
import socket
import ssl

if __package__:
    from integration.vf_preview_handoff.stage_identity import guarded
else:
    # Allow reviewed standalone scripts in the operator context, without
    # changing the PR172 runtime image, checkout or module search path.
    from stage_identity import guarded

HOST = "dong.tail27555e.ts.net"
API = "vrae.diagnosis-api.v1"
MEDIA = 'application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"'


class Connection(http.client.HTTPSConnection):
    def __init__(self, host, port, context, connect_host=None):
        super().__init__(host, port, context=context, timeout=8)
        self.connect_host = connect_host

    def connect(self):
        sock = socket.create_connection((self.connect_host or self.host, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def run(bundle, control_config, *, _test_port=None, _test_connect_host=None):
    events = []
    result = {"contract": "vrae.vf-preview-identity-readback.v1", "passed": False,
              "events": events, "vercel_egress_proven": False, "diagnosis_submitted": False}
    try:
        bundle = guarded(bundle, True)
        read = lambda name: guarded(bundle / name).read_bytes()
        cfg = json.loads(guarded(control_config).read_bytes())
        sha = read("VRAE_DIAGNOSIS_SOURCE_SHA").decode()
        receipt = json.loads(read("receipt.json"))
        if cfg["host"] != HOST or cfg["source_sha"] != sha or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("EXACT_HOST_AND_RUNNING_SHA_REQUIRED")
        new_cert = guarded(bundle / "VRAE_DIAGNOSIS_CLIENT_CERT_PEM")
        new_key = guarded(bundle / "VRAE_DIAGNOSIS_CLIENT_KEY_PEM")
        ca = guarded(bundle / "VRAE_DIAGNOSIS_CA_PEM")
        old_cert = guarded(cfg["certificate"])
        old_key = guarded(cfg["key"])
        new_bearer = read("VRAE_DIAGNOSIS_BEARER").decode()
        old_bearer = cfg["api_bearer"]
        if new_bearer == old_bearer or new_cert.read_bytes() == old_cert.read_bytes():
            raise ValueError("DEDICATED_PAIR_REQUIRED")
        der = ssl.PEM_cert_to_DER_cert(new_cert.read_text())
        fingerprint = hashlib.sha256(der).hexdigest()
        if fingerprint != receipt["client_certificate_sha256"] or receipt["source_sha"] != sha:
            raise ValueError("ISSUANCE_RECEIPT_MISMATCH")
        result.update(source_sha=sha, client_certificate_sha256=fingerprint,
                      not_before=receipt["not_before"], expires_at=receipt["expires_at"])
        # Existing control identity is used ONLY for comparison, never exported
        # or installed as Preview. GH's temporary health identity is unsuitable.
        cases = [
            ("preview_ready", new_cert, new_key, new_bearer, "/health/ready", 200),
            ("preview_openapi", new_cert, new_key, new_bearer, "/v1/openapi.json", 200),
            ("control_ready", old_cert, old_key, old_bearer, "/health/ready", 200),
            ("preview_cert_control_bearer", new_cert, new_key, old_bearer, "/health/ready", 403),
            ("control_cert_preview_bearer", old_cert, old_key, new_bearer, "/health/ready", 403),
            ("invalid_bearer", new_cert, new_key, "invalid-preview-check", "/health/ready", 403),
            ("no_certificate", None, None, new_bearer, "/health/ready", None),
        ]
        for name, cert, key, bearer, path, expected in cases:
            event = {"case": name, "path": path, "passed": False}
            events.append(event)
            ctx = ssl.create_default_context(cafile=str(ca))
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            if cert is not None:
                ctx.load_cert_chain(cert, key)
            conn = Connection(HOST, _test_port or 443, ctx, _test_connect_host)
            try:
                conn.request("GET", path, headers={"Accept": "application/json", "Authorization": "Bearer " + bearer})
                response = conn.getresponse()
                raw = response.read(262145)
                event.update(status=response.status, response_sha256=hashlib.sha256(raw).hexdigest())
                if (len(raw) > 262144 or response.status != expected or
                    response.getheader("X-VRAE-API-Version") != API or
                    response.getheader("X-VRAE-Source-SHA") != sha or
                    response.getheader("Content-Type") != (MEDIA if expected == 403 else "application/json") or
                    "no-store" not in response.getheader("Cache-Control", "").split(", ")):
                    raise ValueError("RESPONSE_CHECK_REFUSED")
                if expected == 200:
                    doc = json.loads(raw)
                    if path == "/health/ready" and (doc.get("status"), doc.get("source_sha")) != ("READY", sha):
                        raise ValueError("READY_BODY_REQUIRED")
                    if path == "/v1/openapi.json" and not all(p in doc.get("paths", {}) for p in
                            ("/v1/target-applications", "/v1/target-applications/authorize", "/v1/diagnoses")):
                        raise ValueError("DYNAMIC_PREVIEW_REQUIRED")
                event["passed"] = True
            except ssl.SSLError as error:
                # Only a concrete server TLS client-certificate alert counts;
                # timeouts, EOFs, resets and server-verification errors do not.
                if name != "no_certificate" or error.reason not in (
                        "TLSV13_ALERT_CERTIFICATE_REQUIRED", "SSLV3_ALERT_HANDSHAKE_FAILURE",
                        "TLSV1_ALERT_UNKNOWN_CA", "SSLV3_ALERT_BAD_CERTIFICATE"):
                    raise
                event.update(tls_rejected=True, tls_alert=error.reason, passed=True)
            finally:
                conn.close()
        result["passed"] = True
    except Exception as error:
        result["failure"] = "PRIVATE_OPERATOR_READBACK_REQUIRED"
        result["failure_type"] = type(error).__name__
        if isinstance(error, ssl.SSLError):
            result["tls_reason"] = error.reason
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", required=True)
    p.add_argument("--control-config", required=True)
    args = p.parse_args()
    # Force use inside the same protected root context as staging.
    import os
    if os.name != "posix" or os.geteuid() != 0:
        print('{"passed":false,"failure":"AUTHORIZED_ROOT_OPERATOR_REQUIRED"}')
        raise SystemExit(1)
    result = run(args.bundle, args.control_config)
    print(json.dumps(result))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
