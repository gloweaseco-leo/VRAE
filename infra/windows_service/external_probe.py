"""Real end-to-end mTLS health probes. Never logs bodies, keys or bearers."""
import argparse
import errno
import hashlib
import http.client
import json
import ipaddress
import os
from pathlib import Path
import socket
import ssl


class Connection(http.client.HTTPSConnection):
    def __init__(self, host, port, context, connect_host=None):
        super().__init__(host, port, context=context, timeout=15)
        self.connect_host = connect_host

    def connect(self):
        sock = socket.create_connection((self.connect_host or self.host, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def run(cfg, connect_host=None):
    events = []
    authorized_peers = []
    for name, port, route, bearer, media in (
        ("diagnosis", cfg.get("api_port",443), "/health/ready", cfg["api_bearer"], "application/json"),
        ("review", cfg.get("review_port",8443), "/v1/report-authority/health", cfg["review_bearer"],
         'application/vnd.vrae.report+json; profile="vrae.report-authority.v1"'),
    ):
        for case in ("authorized", "wrong_bearer", "wrong_certificate", "no_certificate"):
            ctx = ssl.create_default_context(cafile=cfg.get("ca"))
            if case != "no_certificate":
                prefix = "other_" if case == "wrong_certificate" else ""
                ctx.load_cert_chain(cfg[prefix+"certificate"], cfg[prefix+"key"])
            c = Connection(cfg["host"], port, ctx, connect_host)
            headers = {"Accept": media, "Authorization": "Bearer " + ("invalid" if case == "wrong_bearer" else bearer)}
            if name == "review":
                headers["X-Report-Profile"] = "VERIFIED_HUMAN_CUSTOMER_REPORT"
            try:
                c.connect()
                peer = c.sock.getpeername()[0]
                certificate_sha256 = hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()
                c.request("GET", route, headers=headers)
                r = c.getresponse()
                raw = r.read(65537)
                if len(raw) > 65536:
                    raise AssertionError("BOUNDED_HEALTH_RESPONSE_REQUIRED")
                if case == "authorized":
                    doc = json.loads(raw)
                    assert r.status == 200
                    authorized_peers.append(peer)
                    assert doc.get("status") == "READY" or doc.get("ready") is True
                    assert r.getheader("X-VRAE-Source-SHA") == cfg["source_sha"]
                    assert "no-store" in r.getheader("Cache-Control","")
                    if name == "review":
                        assert r.getheader("X-VRAE-Scope") == "VERIFIED_HUMAN_CUSTOMER_REPORT"
                        assert doc["customer_release"] is True
                else:
                    assert r.status == 403, "INVALID_CLIENT_MUST_BE_DENIED"
                events.append({"service":name,"case":case,"status":r.status,
                               "response_sha256":hashlib.sha256(raw).hexdigest(),
                               "server_certificate_sha256":certificate_sha256,"passed":True})
            except (OSError, http.client.RemoteDisconnected) as error:
                negative_tls=case in ("wrong_certificate","no_certificate")
                closed=(isinstance(error,(ssl.SSLError,ConnectionResetError,http.client.RemoteDisconnected))
                        or getattr(error,"errno",None) in (errno.ENOTCONN,errno.ECONNRESET,errno.EPIPE))
                if not negative_tls or not closed:
                    raise
                events.append({"service":name,"case":case,"tls_rejected":True,
                               "exception_type":type(error).__name__,"passed":True})
            finally:
                c.close()
    return {"contract":"vrae.windows-public-mtls-probe.v1","host":cfg["host"],
            "source_sha":cfg["source_sha"],"passed":True,"events":events,
            "external_network": bool(os.environ.get("GITHUB_ACTIONS")=="true" and connect_host is None
                and cfg["host"].endswith(".ts.net") and len(authorized_peers)==2
                and all(ipaddress.ip_address(ip).is_global for ip in authorized_peers)),
            "customer_diagnosis_complete":False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config",required=True)
    p.add_argument("--connect-local",action="store_true")
    a = p.parse_args()
    path=Path(a.config)
    st=path.stat()
    if path.is_symlink() or (os.name=="posix" and (st.st_uid!=os.geteuid() or st.st_mode&0o077)):
        raise PermissionError("PRIVATE_CALLER_CONFIG_REQUIRED")
    cfg=json.loads(path.read_bytes())
    print(json.dumps(run(cfg,"127.0.0.1" if a.connect_local else None)))


if __name__ == "__main__":
    main()
