"""Actual HTTP fixture, out-of-band signer, admin-only negative injection."""

from dataclasses import asdict
from http.client import HTTPConnection
from http.cookies import SimpleCookie
from html.parser import HTMLParser
import json
import re
import threading
import time
from urllib.parse import urlencode, urlsplit

from apps.operator_console.b5a_http import Application, server, PREFIX
from apps.operator_console.b5a_sessions import SessionStore
from tests.identity.issuer import Issuer, ISSUER, AUDIENCE
from vrae.identity.boundary import Assignment, TrustAnchor
from vrae.persistence.private_bytes import locator

from .lab import Lab
from .probe import provision


class Forms(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.forms, self.current = {}, None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form":
            self.current = values.get("action", "")
            self.forms[self.current] = {}
        if tag == "input" and self.current is not None and values.get("name"):
            self.forms[self.current][values["name"]] = values.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


class Client:
    def __init__(self, origin):
        self.origin = origin
        self.port = urlsplit(origin).port
        self.cookies = {}
        self.tokens = []

    def request(self, method, path, data=b"", headers=None, *, cookies=True):
        h = {"Origin": self.origin} if method == "POST" else {}
        if cookies and self.cookies:
            h["Cookie"] = "; ".join(k + "=" + v for k, v in self.cookies.items())
        h.update(headers or {})
        c = HTTPConnection("127.0.0.1", self.port, timeout=25)
        try:
            c.request(method, path, body=data, headers=h)
            r = c.getresponse()
            raw = r.read()
            hs = r.getheaders()
            for k, v in hs:
                if k.lower() == "set-cookie":
                    jar = SimpleCookie(v)
                    for name, value in jar.items():
                        if value["max-age"] == "0":
                            self.cookies.pop(name, None)
                        else:
                            self.cookies[name] = value.value
            for token in self.tokens:
                assert token.encode() not in raw and token[7:].encode() not in raw
            assert dict(hs).get("Cache-Control") == "no-store"
            return r.status, raw, hs
        finally:
            c.close()

    def challenge(self, task="task-404"):
        status, raw, _ = self.request("GET", PREFIX + "login")
        assert status == 200
        csrf = re.search(r'name="_bootstrap_csrf" value="([A-Za-z0-9_-]+)"', raw.decode())[1]
        body = urlencode({"task": task, "_csrf": csrf}).encode()
        status, raw, _ = self.request(
            "POST",
            PREFIX + "challenge",
            body,
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert status == 200
        return json.loads(raw)

    def login(self, issuer, task="task-404", *, changes=None, header=None, alter=None):
        challenge = self.challenge(task)
        now = int(time.time())
        fields = {"iat": now, "nbf": now, "exp": now + 90, "nonce": challenge["nonce"]}
        fields.update(changes or {})
        token = issuer.token(fields, header=header)
        token = alter(token) if alter else token
        self.tokens.append(token)
        response = self.request(
            "POST",
            PREFIX + "session",
            b"{}",
            {
                "Content-Type": "application/json",
                "Authorization": token,
                "X-B5A-CSRF": challenge["csrf"],
            },
        )
        return response, token, challenge


class Runtime:
    def __init__(self, name):
        self.lab = Lab(name)
        self.events = []
        self.secrets = []
        self.http = None
        self.thread = None

    def bootstrap(self):
        self.lab.start()
        self.reader, self.tasks = provision(self.lab, self.events.append)
        self.issuer = Issuer()
        now = int(time.time())
        self.bindings = {
            "task-" + case: Assignment(
                ISSUER,
                "synthetic-reviewer-1",
                self.reader.settings.user,
                locator(graph),
                now + 1800,
            )
            for case, graph in self.lab.graphs.items()
        }
        self.store = SessionStore(
            anchor=TrustAnchor(ISSUER, AUDIENCE, self.issuer.jwks(), now + 1800),
            bindings=self.bindings,
            readers={self.reader.settings.user: self.reader},
        )
        return self

    def start(self):
        self.bootstrap()
        self.app = Application(self.store, self.tasks)
        self.http = server(self.app)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.origin = self.app.origin
        return self

    def client(self):
        value = Client(self.origin)
        value.tokens = self.secrets
        return value

    def review_path(self, case="404", endpoint="review"):
        task = self.tasks[case]
        q = {"version": 1, "draft": task["report_pins"]["expected_draft_ref"]}
        if endpoint in ("target", "proposal") or endpoint.startswith("evidence/"):
            q["target"] = self.bindings["task-" + case].location.target_digest
        return PREFIX + "tasks/task-" + case + "/" + endpoint + "?" + urlencode(q)

    def original_reads(self):
        return sum(e["event"] == "actual_load_target_returned" for e in self.events)

    def stop(self):
        if self.http:
            self.http.shutdown()
            self.http.server_close()
        if self.thread:
            self.thread.join(timeout=10)
        self.lab.stop()

    def profile(self):
        """Restricted child-server input; no admin/APP/writer keys or raw bytes."""
        return {
            "version": "B5A_TEST_ONLY_PROFILE_1",
            "settings": asdict(self.reader.settings),
            "schema_pin": self.reader.schema_pin,
            "pins": [
                {
                    "case": p.case,
                    "location": asdict(p.location),
                    "target_sha256": p.target_sha256,
                    "manifest_sha256": p.manifest_sha256,
                    "descriptors": list(p.descriptors),
                }
                for p in self.reader.pins.values()
            ],
            "tasks": self.tasks,
            "anchor": {
                "issuer": ISSUER,
                "audience": AUDIENCE,
                "jwks": json.loads(self.issuer.jwks()),
                "expires": self.store.boundary.anchor.expires,
                "revoked": [],
                "available": True,
            },
            "bindings": {k: asdict(v) for k, v in self.bindings.items()},
        }
