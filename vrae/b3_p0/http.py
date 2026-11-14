"""Narrow loopback test transport. Server-provisioned opaque sessions, no login/IdP."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import secrets
import threading
import time

from .contracts import Command, Denied


class Sessions:
    def __init__(self):
        self._entries = {}
        self._lock = threading.Lock()

    def provision(self, witness, *, ttl=120):
        if not 0 < ttl <= 120:
            raise Denied("B3_SESSION_TTL")
        with self._lock:
            self._entries = {k: v for k, v in self._entries.items() if v[1] > time.monotonic()}
            if len(self._entries) >= 64:
                raise Denied("B3_SESSION_CAPACITY")
            key = secrets.token_urlsafe(32)
            self._entries[key] = (witness, time.monotonic() + ttl)
            return key

    def require(self, token):
        with self._lock:
            row = self._entries.get(token)
            if row is None or row[1] <= time.monotonic():
                raise Denied("B3_SESSION_DENIED")
            return row[0]


@contextmanager
def serve(factory, sessions):
    """factory(witness) context supplies only a configured low-privilege connection."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *args):
            pass

        def reply(self, status, raw):
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                # Durable history survives a caller that loses its response.
                pass

        def do_POST(self):
            from vrae.reviewing.canonical import canonical

            try:
                # Consume a valid bounded frame before returning any policy/auth
                # refusal. Closing with an unread body can reset TCP instead of
                # delivering the fixed JSON denial (Host/Origin as well as session).
                lengths = self.headers.get_all("Content-Length")
                if (
                    self.headers.get("Transfer-Encoding") is not None
                    or lengths is None
                    or len(lengths) != 1
                    or not re.fullmatch(r"[0-9]{1,6}", lengths[0])
                ):
                    raise Denied("B3_BODY_BOUND")
                size = int(lengths[0])
                if not 0 < size <= 131072:
                    raise Denied("B3_BODY_BOUND")
                self.connection.settimeout(3)
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise Denied("B3_BODY_BOUND")
                expected = "127.0.0.1:" + str(server.server_port)
                authorization = self.headers.get_all("Authorization") or []
                if (
                    self.headers.get_all("Host") != [expected]
                    or self.headers.get("Origin") is not None
                    or len(authorization) != 1
                    or self.headers.get("Content-Type") != "application/json"
                ):
                    raise Denied("B3_TRANSPORT_DENIED")
                token = self.headers["Authorization"]
                if not re.fullmatch(r"Bearer [A-Za-z0-9_-]{43}", token):
                    raise Denied("B3_SESSION_DENIED")
                witness = sessions.require(token[7:])
                from vrae.reviewing.canonical import parse

                with factory(witness) as service:
                    if self.path == "/test-only/intents":
                        receipt = service.submit(witness, Command(raw))
                    elif self.path == "/test-only/receipts":
                        d = parse(raw, limit=131072)
                        if set(d) != {"idempotency_key"}:
                            raise Denied("B3_CLOSED_RECEIPT_QUERY")
                        receipt = service.get_receipt(witness, d["idempotency_key"])
                    else:
                        raise Denied("B3_PORT_DENIED")
                self.reply(200, receipt.payload)
            except Denied as exc:
                status = (
                    409
                    if str(exc) in {"UNKNOWN_COMMIT", "B3_STALE_CAS", "B3_IDEMPOTENCY_CONFLICT"}
                    else 403
                )
                self.reply(status, canonical({"error": str(exc)}, limit=4096))
            except Exception:
                # No SQL, evidence, DSN or user-controlled exception text crosses HTTP.
                self.reply(403, b'{"error":"B3_REQUEST_DENIED"}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
