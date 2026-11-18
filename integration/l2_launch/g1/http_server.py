"""Real loopback TLS facade, fixed service identity and frozen G0 profile.

Public/customer publication is always closed. Fixture operations are a separate
controlled Owner surface; they cannot issue real review or ShareGrant authority.
"""

from datetime import datetime, UTC
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import hmac
import json
import re
import socket
import ssl
from threading import BoundedSemaphore

import psycopg
from contracts.l2_launch.contract import Refused, canonical, validate
from contracts.l2_launch.vf_b import VERSION, HEADERS, safe_error, vf_status
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient, ConsumerDenied
from integration.l2_launch.g1.storage import TransportStore, REALM_LOCK

MEDIA = 'application/vnd.vrae.launch+json; profile="' + VERSION + '"'
COOKIE = "__Host-vrae-g1"
CHALLENGE = "__Host-vrae-g1-challenge"
REF = r"aref-[0-9a-f]{32}"


class TransportError(ValueError):
    def __init__(self, status):
        self.status = status


def decoded(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("DUPLICATE_KEY")
            result[key] = value
        return result

    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE")),
    )


class Application:
    def __init__(self, cfg, flow=None):
        if (
            cfg["mode"] != "OFFLINE_SYNTHETIC"
            or cfg["bind"] != "127.0.0.1"
            or cfg["live"] is not False
        ):
            raise ValueError("G1_PRIVATE_SYNTHETIC_REQUIRED")
        self.cfg, self.flow = cfg, flow
        self.client = TaskClient(
            AppEndpoint(cfg["app_bearer"], cfg["tenant"], frozenset(cfg["source_refs"]))
        )
        self.store = TransportStore(cfg, self.client)
        if self.flow is None:
            from integration.l2_launch.g1.report_flow import ReportFlow

            self.flow = ReportFlow(self.store)
        self.slots = BoundedSemaphore(4)

    def authenticated(self, headers, *, owner=False):
        name = "X-G1-Fixture-Owner" if owner else "Authorization"
        expected = self.cfg["owner_token"] if owner else "Bearer " + self.cfg["service_token"]
        actual = headers.get(name, "")
        if len(headers.get_all(name, [])) != 1 or not hmac.compare_digest(actual, expected):
            raise Refused("FORBIDDEN_ROLE")

    def status(self, c, record):
        task = self.store.task(record)
        native = self.client.status(task)
        state = "FAILED" if native["job_state"] == "DEAD_LETTER" else "QUEUED"
        if native["job_state"] == "TEST_ONLY_DONE":
            if self.flow is None:
                raise Refused("R0_STORAGE_UNAVAILABLE", 503, True)
            state = self.flow.state(record)
        run = {
            "schema_version": "1.0",
            "tenant_id": self.cfg["tenant"],
            "run_id": self.store.public_run(task),
            "audit_id": record["submission"]["command"]["request"]["audit_id"],
            "request_id": record["submission"]["command"]["request"]["request_id"],
            "status": state,
            "attempt": native["attempts"],
            "input_hash": record["intent_hash"],
            "rule_version": "ra2b6-1.0.0",
            "started_at": None,
            "finished_at": None,
            "error_code": None,
        }
        body = vf_status(record["audit_ref"], run, datetime.now(UTC), publication="UNPUBLISHED")
        validate("VFStatus", body)
        return body


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "G1Local"
    sys_version = ""

    def log_message(self, *args):
        pass

    @property
    def app(self):
        return self.server.app

    def cookies(self):
        value = SimpleCookie()
        try:
            value.load(self.headers.get("Cookie", ""))
        except Exception:
            raise Refused("FORBIDDEN_ROLE") from None
        return {k: v.value for k, v in value.items()}

    def body(self):
        if (
            self.headers.get("Transfer-Encoding") is not None
            or len(self.headers.get_all("Content-Length", [])) != 1
        ):
            raise TransportError(400)
        try:
            size = int(self.headers["Content-Length"])
        except ValueError:
            raise TransportError(400) from None
        if not 1 <= size <= 32768:
            raise TransportError(413)
        self.connection.settimeout(3)
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise TransportError(400)
        try:
            return decoded(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise Refused("R0_WRONG_CONTRACT") from None

    def send(self, status, body, extra=()):
        raw = canonical(body)
        self.send_response_only(status)
        self.send_header("Content-Type", MEDIA)
        self.send_header("Content-Length", str(len(raw)))
        for key, value in HEADERS.items():
            self.send_header(key, value)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-VRAE-Scope", "OFFLINE_SYNTHETIC_NO_RELEASE")
        self.send_header("X-G1-AI-State", "NO_MODEL")
        for key, value in extra:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()

    def route(self, method):
        path = self.path
        for name in (
            "Host",
            "Origin",
            "Accept",
            "Authorization",
            "X-G1-Fixture-Owner",
            "Content-Type",
            "Cookie",
            "X-G1-CSRF",
            "If-Match",
        ):
            if len(self.headers.get_all(name, [])) > 1:
                raise Refused("FORBIDDEN_ROLE")
        if len(path) > 256 or "?" in path or "%" in path or "\\" in path:
            raise Refused("FORBIDDEN_ROLE")
        owner = path.startswith("/__fixture__/")
        self.app.authenticated(self.headers, owner=owner)
        if self.headers.get("Host") != "127.0.0.1:" + str(self.server.server_port):
            raise Refused("FORBIDDEN_ROLE")
        if self.headers.get("Accept") != MEDIA:
            raise TransportError(406)
        if method == "POST" and self.headers.get("Content-Type") != MEDIA:
            raise TransportError(415)
        if self.headers.get("Origin") not in self.app.cfg["origins"]:
            raise Refused("FORBIDDEN_ROLE")
        if method == "GET" and path == "/__g1/health":
            with self.app.store.connect() as c:
                self.app.store.realm(c)
            return self.send(
                200,
                {
                    "mode": "OFFLINE_SYNTHETIC",
                    "local_service_ready": True,
                    "live_available": False,
                    "released_reports": False,
                },
            )
        if method == "POST" and path == "/v1/audit-requests":
            return self.send(202, self.app.store.submit(self.body()))
        if method == "GET" and path == "/v1/return-challenge":
            challenge, csrf = self.app.store.challenge()
            return self.send(
                200,
                {"challenge_ready": True},
                [
                    (
                        "Set-Cookie",
                        CHALLENGE
                        + "="
                        + challenge
                        + "; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=60",
                    ),
                    ("X-G1-CSRF", csrf),
                ],
            )
        match = re.fullmatch("/__fixture__/return-grants/(" + REF + ")", path)
        if method == "POST" and match:
            value = self.body()
            if set(value) != {"grant", "proof"}:
                raise Refused("FORBIDDEN_ROLE")
            self.app.store.install_return(match[1], value["grant"], value["proof"])
            return self.send(201, {"controlled_fixture_installed": True, "real_share_grant": False})
        match = re.fullmatch("/v1/audits/(" + REF + ")/return/exchange", path)
        if method == "POST" and match:
            value = self.body()
            cookies = self.cookies()
            if type(value) is not dict or set(value) != {"return_token"}:
                raise Refused("FORBIDDEN_ROLE")
            cookie, csrf, expiry = self.app.store.exchange(
                match[1],
                value["return_token"],
                cookies.get(CHALLENGE),
                self.headers.get("X-G1-CSRF"),
            )
            age = max(1, int((expiry - datetime.now(UTC)).total_seconds()))
            return self.send(
                200,
                {"restored": True},
                [
                    (
                        "Set-Cookie",
                        COOKIE
                        + "="
                        + cookie
                        + "; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age="
                        + str(age),
                    ),
                    (
                        "Set-Cookie",
                        CHALLENGE + "=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0",
                    ),
                    ("X-G1-CSRF", csrf),
                ],
            )
        match = re.fullmatch("/__fixture__/audits/(" + REF + ")/(pins|review|preview-permit)", path)
        if match:
            from integration.l2_launch.g1.preview import fixture

            return fixture(self, method, match[1], match[2])
        match = re.fullmatch("/__synthetic__/audits/(" + REF + ")/preview", path)
        if method == "GET" and match:
            from integration.l2_launch.g1.preview import preview

            return preview(self, match[1])
        match = re.fullmatch(
            "/v1/audits/(" + REF + ")(?:/(report|review-decisions|sales-handoffs))?", path
        )
        if match:
            cookies = self.cookies()
            with self.app.store.connect() as c, c.transaction():
                c.execute("SELECT pg_advisory_xact_lock_shared(%s)", (REALM_LOCK,))
                record = self.app.store.session(
                    c, match[1], cookies.get(COOKIE), self.headers.get("X-G1-CSRF")
                )
                if method == "GET" and match[2] is None:
                    return self.send(200, self.app.status(c, record))
                # The SERVICE identity never becomes human reviewer/Owner or a
                # customer release authority, even if a controlled fixture exists.
                raise Refused("REPORT_NOT_APPROVED")
        if re.fullmatch("/v1/reports/[^/]+/share-grants", path):
            raise Refused("FORBIDDEN_ROLE")
        raise TransportError(404)

    def handle(self):
        self.connection.settimeout(5)
        return super().handle()

    def dispatch(self, method):
        if not self.app.slots.acquire(blocking=False):
            return self.send(429, safe_error(Refused("QUOTA_EXCEEDED", 429, True)))
        try:
            self.route(method)
        except TransportError as error:
            self.close_connection = True
            self.send(error.status, {"transport_error": HTTPStatus(error.status).phrase})
        except ConsumerDenied:
            self.close_connection = True
            try:
                with socket.create_connection(("127.0.0.1", 8765), timeout=0.5):
                    pass
                refused = Refused("FORBIDDEN_ROLE")
            except OSError:
                refused = Refused("R0_STORAGE_UNAVAILABLE", 503, True)
            body = safe_error(refused)
            self.send(body["http_status"], body)
        except (Refused, KeyError, TypeError, ValueError) as error:
            import traceback

            traceback.print_exc()  # UID0 private fixture log, never an HTTP body
            self.close_connection = True
            refused = error if isinstance(error, Refused) else Refused("FORBIDDEN_ROLE")
            body = safe_error(refused)
            self.send(body["http_status"], body)
        except (psycopg.Error, ConnectionError, socket.timeout, OSError):
            self.close_connection = True
            body = safe_error(Refused("R0_STORAGE_UNAVAILABLE", 503, True))
            self.send(503, body)
        except Exception:
            import traceback

            traceback.print_exc()  # retained only in the private fixture log
            self.close_connection = True
            self.send(503, safe_error(Refused("R0_STORAGE_UNAVAILABLE", 503, True)))
        finally:
            self.app.slots.release()

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_DELETE(self):
        self.dispatch("DELETE")

    def do_PUT(self):
        self.dispatch("PUT")


class BoundedServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, tls):
        self.tls = tls
        self.connections = BoundedSemaphore(8)
        super().__init__(address, handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return self.tls.wrap_socket(
            connection, server_side=True, do_handshake_on_connect=False
        ), address

    def process_request(self, request, address):
        if not self.connections.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.connections.release()

    def handle_error(self, request, address):
        print('{"stage":"G1_REQUEST_ABORTED","details":"PRIVATE_ONLY"}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = json.loads(open(args.config, encoding="utf-8").read())
    app = Application(cfg)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(cfg["certificate"], cfg["certificate_key"])
    server = BoundedServer(("127.0.0.1", 8766), Handler, tls)
    server.app = app
    print('{"stage":"G1_REAL_LOOPBACK_TLS_READY","port":8766,"public":false}', flush=True)
    server.serve_forever(poll_interval=0.1)


if __name__ == "__main__":
    main()
