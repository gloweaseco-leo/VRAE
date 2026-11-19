"""Explicit HTTPS endpoint configuration; non-loopback requires bound mTLS."""

import hashlib
import hmac
from ipaddress import ip_address
from urllib.parse import urlsplit
from contracts.l2_launch.contract import Refused


def endpoint(cfg):
    transport = cfg.get("transport")
    if transport is None:
        return {
            "bind": "127.0.0.1",
            "port": 8769,
            "hosts": ["127.0.0.1:8769"],
            "origins": ["https://127.0.0.1:8769"],
            "mtls": False,
        }
    d = dict(transport)
    if (
        not d.get("mtls")
        or not d.get("client_ca")
        or not d.get("hosts")
        or d["port"] < 1
        or d["port"] > 65535
    ):
        raise ValueError("EXPLICIT_MTLS_ENDPOINT_REQUIRED")
    ip_address(d["bind"])
    for origin in d["origins"]:
        u = urlsplit(origin)
        if u.scheme != "https" or u.netloc not in d["hosts"] or u.path or u.query or u.fragment:
            raise ValueError("HTTPS_ORIGIN_REQUIRED")
    for b in cfg["bindings"]:
        if len(b.get("client_certificate_sha256", "")) != 64:
            raise ValueError("BOUND_SERVICE_CERT_REQUIRED")
    return d


def check_headers(handler, cfg):
    d = endpoint(cfg)
    if handler.headers.get("Host") not in d["hosts"]:
        raise Refused("FORBIDDEN_ROLE")
    origin = handler.headers.get("Origin")
    if origin is not None and origin not in d["origins"]:
        raise Refused("FORBIDDEN_ROLE")
    if origin is None and not d["mtls"]:
        raise Refused("FORBIDDEN_ROLE")
    return d


def bind_peer(handler, binding, transport):
    if transport["mtls"]:
        cert = handler.connection.getpeercert(binary_form=True)
        if not cert or not hmac.compare_digest(
            hashlib.sha256(cert).hexdigest(), binding["client_certificate_sha256"]
        ):
            raise Refused("FORBIDDEN_ROLE")
