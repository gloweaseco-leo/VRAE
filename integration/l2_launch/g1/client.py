"""Actual fixed-endpoint HTTPS client; no redirects or credential-bearing logs."""

import hashlib
import http.client
import json
import ssl

from contracts.l2_launch.contract import canonical
from integration.l2_launch.g1.http_server import MEDIA


class Client:
    def __init__(
        self, port, ca, certificate_hash, *, service_token=None, owner_token=None, origin=None
    ):
        self.port, self.context, self.pin = (
            port,
            ssl.create_default_context(cafile=ca),
            certificate_hash,
        )
        self.service_token, self.owner_token, self.origin = service_token, owner_token, origin
        self.cookies = {}
        self.csrf = None
        self.trace = []

    def request(self, method, path, body=None, *, owner=False, headers=None, remember=True):
        supplied = {
            "Host": "127.0.0.1:" + str(self.port),
            "Accept": MEDIA,
            "Origin": self.origin or "https://127.0.0.1:" + str(self.port),
        }
        if self.service_token:
            supplied["Authorization"] = "Bearer " + self.service_token
        if owner and self.owner_token:
            supplied["X-G1-Fixture-Owner"] = self.owner_token
        if self.cookies:
            supplied["Cookie"] = "; ".join(k + "=" + v for k, v in self.cookies.items())
        if self.csrf:
            supplied["X-G1-CSRF"] = self.csrf
        if body is not None:
            supplied["Content-Type"] = MEDIA
        supplied.update(headers or {})
        connection = http.client.HTTPSConnection(
            "127.0.0.1", self.port, timeout=45, context=self.context
        )
        try:
            connection.connect()
            if (
                hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
                != self.pin
            ):
                raise ValueError("G1_LOCAL_CERTIFICATE_PIN")
            connection.request(
                method, path, body=canonical(body) if body is not None else None, headers=supplied
            )
            response = connection.getresponse()
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("G1_RESPONSE_BOUND")
            value = json.loads(raw)
            pairs = response.getheaders()
            self.last_response_headers = pairs
            if remember:
                from http.cookies import SimpleCookie

                for key, content in pairs:
                    if key.lower() == "set-cookie":
                        parsed = SimpleCookie()
                        parsed.load(content)
                        for name, item in parsed.items():
                            if item["max-age"] == "0":
                                self.cookies.pop(name, None)
                            else:
                                self.cookies[name] = item.value
                    elif key.lower() == "x-g1-csrf":
                        self.csrf = content
            event = {
                "method": method,
                "route": path.replace(path.split("/")[3], "{audit_ref}")
                if "/audits/" in path
                else path,
                "status": response.status,
                "profile": response.getheader("Content-Type"),
                "cache_control": response.getheader("Cache-Control"),
                "source_sha": response.getheader("X-VRAE-Source-SHA"),
                "ai_state": response.getheader("X-G1-AI-State"),
                "body_sha256": hashlib.sha256(raw).hexdigest(),
                "set_cookie_attributes": [
                    {
                        flag: flag.lower() in v.lower()
                        for flag in ("HttpOnly", "Secure", "SameSite=Strict", "Path=/")
                    }
                    for k, v in pairs
                    if k.lower() == "set-cookie"
                ],
            }
            self.trace.append(event)
            return response.status, value, dict(pairs)
        finally:
            connection.close()
