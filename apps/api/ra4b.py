"""Loopback-only, fixed synthetic principal HTTP adapter. No public launch mode."""

import argparse
import hmac
import json
import re
import socketserver
import threading
import time
import uuid

import h11
import psycopg

from vrae.application.ra4b import store

HOST = "127.0.0.1:8765"
ORIGIN = "http://127.0.0.1:8765"
ALLOWED = {"host", "origin", "authorization", "content-length", "content-type", "idempotency-key", "connection",
           "accept", "accept-encoding", "user-agent"}


def unique_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate key")
        result[k] = v
    return result


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, config):
        self.config = config
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(("127.0.0.1", 8765), Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def handle_error(self, request, address):
        # Bodies, SQL diagnostics and provisioning paths must never enter logs.
        print("RA4B_HTTP_REQUEST_CLOSED", flush=True)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        protocol = h11.Connection(h11.SERVER, max_incomplete_event_size=8192)
        try:
            code, body = self.read_dispatch(protocol)
        except (ValueError, UnicodeError, h11.ProtocolError, TimeoutError):
            code, body = 400, {"error": "REQUEST_DENIED"}
        except psycopg.errors.InvalidParameterValue:
            code, body = 409, {"error": "IDEMPOTENCY_CONFLICT"}
        except psycopg.errors.InsufficientPrivilege:
            code, body = 403, {"error": "CURRENT_AUTHORITY_DENIED"}
        except psycopg.Error:
            code, body = 503, {"error": "DURABLE_STORE_UNAVAILABLE"}
        raw = json.dumps(body, separators=(",", ":")).encode()
        # A fixed response serializer also works after a parser rejection.
        response = (f"HTTP/1.1 {code} Response\r\nContent-Type: application/json\r\n"
                    f"Content-Length: {len(raw)}\r\nConnection: close\r\n"
                    "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n").encode()
        try:
            self.request.sendall(response + raw)
        except OSError:
            pass

    def read_dispatch(self, protocol):
        deadline = time.monotonic() + 3
        raw_header = bytearray()
        body = bytearray()
        request = None
        headers = {}
        while True:
            event = protocol.next_event()
            if event is h11.NEED_DATA:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                self.request.settimeout(remaining)
                data = self.request.recv(2048)
                if request is None:
                    raw_header.extend(data)
                    prefix = bytes(raw_header).split(b"\r\n\r\n", 1)[0]
                    if len(prefix) > 8192:
                        return 431, {"error": "HEADERS_TOO_LARGE"}
                    if b"\r\n\r\n" in raw_header:
                        lines = prefix.split(b"\r\n")[1:]
                        names = [line.split(b":", 1)[0].lower() for line in lines]
                        if len(lines) > 16 or len(names) != len(set(names)) or any(line[:1] in (b" ", b"\t") for line in lines):
                            raise ValueError("ambiguous headers")
                if not data:
                    raise ValueError("incomplete request")
                protocol.receive_data(data)
            elif isinstance(event, h11.Request):
                request = event
                headers = {k.decode("ascii"): v.decode("ascii") for k, v in event.headers}
                if event.http_version != b"1.1" or set(headers) - ALLOWED:
                    return 400, {"error": "HEADERS_DENIED"}
                if headers.get("accept-encoding", "identity") != "identity" or headers.get("accept", "application/json") not in ("application/json", "*/*"):
                    return 400, {"error": "HEADERS_DENIED"}
                if headers.get("host") != HOST or headers.get("origin") != ORIGIN:
                    return 403, {"error": "ORIGIN_DENIED"}
                auth = headers.get("authorization", "")
                if not hmac.compare_digest(auth, "Bearer " + self.server.config["bearer"]):
                    return 401, {"error": "AUTH_REQUIRED"}
                if int(headers.get("content-length", "0")) > 1024:
                    return 413, {"error": "BODY_TOO_LARGE"}
            elif isinstance(event, h11.Data):
                body.extend(event.data)
                if len(body) > 1024:
                    return 413, {"error": "BODY_TOO_LARGE"}
            elif isinstance(event, h11.EndOfMessage):
                if protocol.trailing_data[0]:
                    raise ValueError("pipelining denied")
                break
            else:
                raise ValueError("request denied")
        method = request.method.decode("ascii")
        path = request.target.decode("ascii")
        cfg = self.server.config
        if method == "POST" and path == "/v1/audit-requests":
            if headers.get("content-type") != "application/json":
                return 415, {"error": "JSON_REQUIRED"}
            key = headers.get("idempotency-key", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", key):
                return 422, {"error": "IDEMPOTENCY_KEY_REQUIRED"}
            payload = json.loads(body, object_pairs_hook=unique_object)
            if (not isinstance(payload, dict) or set(payload) != {"source_ref"}
                    or not isinstance(payload["source_ref"], str) or payload["source_ref"] not in cfg["sources"]):
                return 422, {"error": "FIXED_SYNTHETIC_SOURCE_REQUIRED"}
            with store.connect(cfg) as c:
                result = store.admit(c, cfg, key, payload["source_ref"])
            return 202, result
        parts = path.split("/")
        if len(parts) in (4, 5) and parts[1:3] == ["v1", "audit-requests"]:
            if body:
                return 400, {"error": "BODY_DENIED"}
            try:
                identifier = str(uuid.UUID(parts[3]))
            except ValueError:
                return 404, {"error": "NOT_FOUND"}
            if method == "GET" and len(parts) == 4 or method == "POST" and parts[4:] == ["cancel"]:
                with store.connect(cfg) as c:
                    result = store.status(c, cfg, identifier)
                if result is None:
                    return 404, {"error": "NOT_FOUND"}
                if method == "POST":
                    return 501, {"error": "CANCEL_NOT_IMPLEMENTED", "authority": store.AUTHORITY}
                return 200, result
        return 404, {"error": "NOT_FOUND"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = store.load_config(args.config, "APP")
    if not isinstance(cfg.get("bearer"), str) or len(cfg["bearer"]) < 32:
        raise ValueError("RA4B_PRIVATE_BEARER_REQUIRED")
    with store.connect(cfg):
        pass
    with Server(cfg) as server:
        print("RA4B_LOOPBACK_TEST_ONLY_READY", flush=True)
        server.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
