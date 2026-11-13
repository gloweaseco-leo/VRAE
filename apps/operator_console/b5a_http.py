"""Disposable exact-loopback HTTP for signed TEST_ONLY Reviewer sessions.

This is not TLS or a production login. Issuer provisioning is out of band;
bearers are accepted only in the login Authorization header and never rendered.
"""

from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import parse_qsl, unquote, urlsplit

from . import views
from .b5a_console import SignedConsoleService
from .b5a_preview import SignedPreview
from .contracts import ConsoleError, refuse
from .interface import ConsoleInterface, Response
from .proposal_views import composer, hidden

PREFIX = "/b5a/"
BODY_LIMIT = 24_576
FORM = "application/x-www-form-urlencoded"
SECRET = re.compile(
    r"(?:Bearer\s|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|-----BEGIN .*PRIVATE KEY)"
)
AUTHORITY_FIELDS = {
    "role",
    "db_role",
    "dsn",
    "tenant",
    "tenant_id",
    "actor",
    "issuer",
    "sub",
    "privileges",
    "authority",
}


@dataclass(frozen=True)
class Reply:
    response: Response
    headers: tuple = field(default_factory=tuple)


def form(raw):
    if type(raw) is not bytes or len(raw) > BODY_LIMIT:
        refuse("INVALID_INPUT")
    try:
        text = raw.decode("utf-8", errors="strict")
        if re.search(r"%(?![0-9a-fA-F]{2})", text):
            refuse("INVALID_INPUT")
        pairs = parse_qsl(
            text,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
            max_num_fields=64,
        )
        if len(pairs) != len(dict(pairs)) or any(
            SECRET.search(k) or SECRET.search(v) for k, v in pairs
        ):
            refuse("INVALID_INPUT")
        value = dict(pairs)
        if value.keys() & AUTHORITY_FIELDS:
            refuse("INVALID_INPUT")
        return value
    except (ValueError, UnicodeError):
        refuse("INVALID_INPUT")


def cookie(name, value, age):
    return f"{name}={value}; Path={PREFIX}; Max-Age={age}; HttpOnly; SameSite=Strict"


class Application:
    def __init__(self, sessions, tasks):
        self.sessions, self.tasks = sessions, tasks
        self.service = SignedConsoleService(sessions, tasks)
        self.preview = SignedPreview(self.service)
        self.interface = ConsoleInterface(
            self.service, prefix=PREFIX, proposal_preview=self.preview
        )
        self.bootstrap_csrf = secrets.token_urlsafe(32)
        self.origin = None

    def _headers(self, method, headers):
        if self.origin is None or headers.get("Host") != self.origin.removeprefix("http://"):
            refuse("UNAUTHORIZED")
        if any(
            headers.get(k) is not None
            for k in ("X-Role", "X-Actor", "X-Tenant", "X-DB-Role", "X-DSN", "X-Issuer")
        ):
            refuse("UNAUTHORIZED")
        origin = headers.get("Origin")
        if (origin is not None and origin != self.origin) or headers.get("Sec-Fetch-Site") not in (
            None,
            "none",
            "same-origin",
        ):
            refuse("UNAUTHORIZED")
        if method == "POST" and origin != self.origin:
            refuse("UNAUTHORIZED")
        if headers.get("Transfer-Encoding") is not None or headers.get("Expect") is not None:
            refuse("INVALID_INPUT")

    def _cookies(self, headers):
        raw = headers.get("Cookie", "")
        if len(raw) > 512:
            refuse("UNAUTHORIZED")
        if not raw:
            return {}
        pieces = raw.split(";")
        keys = [p.strip().split("=", 1)[0] for p in pieces]
        if len(keys) != len(set(keys)) or set(keys) - {"b5a_session", "b5a_challenge"}:
            refuse("UNAUTHORIZED")
        c = SimpleCookie()
        try:
            c.load(raw)
        except Exception:
            refuse("UNAUTHORIZED")
        if set(c) != set(keys) or any(
            not re.fullmatch(r"[A-Za-z0-9_-]{43}", v.value) for v in c.values()
        ):
            refuse("UNAUTHORIZED")
        return {k: v.value for k, v in c.items()}

    def _path(self, target):
        if (
            type(target) is not str
            or len(target) > 2048
            or re.search(r"%(?![0-9a-fA-F]{2})", target)
            or any(ord(c) < 32 for c in target)
        ):
            refuse("INVALID_INPUT")
        u = urlsplit(target)
        if u.scheme or u.netloc or u.fragment or not u.path.startswith(PREFIX):
            refuse("INVALID_INPUT")
        path = unquote(u.path, errors="strict")
        if "\\" in path or ".." in path.split("/") or unquote(path) != path:
            refuse("INVALID_INPUT")
        return path, u.query

    def _preflight(self, sid, path, query):
        session = self.sessions.require(sid)
        relative = path[len(PREFIX) :]
        if relative == "":
            allowed = {"stage", "q"}
        else:
            parts = relative.split("/")
            if len(parts) < 2 or parts[0] != "tasks" or parts[1] != session.task_id:
                refuse("UNAUTHORIZED")
            if len(parts) == 2:
                allowed = set()
            elif len(parts) in (3, 4):
                allowed = {"version", "draft", "target"}
                if parts[2] not in ("review", "target", "proposal", "evidence", "proposal-preview"):
                    refuse("NOT_IMPLEMENTED")
            else:
                refuse("NOT_IMPLEMENTED")
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True, max_num_fields=4)
        q = dict(pairs)
        if len(q) != len(pairs) or q.keys() - allowed or any(SECRET.search(v) for v in q.values()):
            refuse("INVALID_INPUT")
        task = self.tasks[
            self.sessions.readers[session.binding.db_role].pins[session.binding.location].case
        ]
        if "version" in q and q["version"] != str(session.binding.location.version):
            refuse("STALE_VERSION")
        if "draft" in q and q["draft"] != task["report_pins"]["expected_draft_ref"]:
            refuse("STALE_VERSION")
        if "target" in q and q["target"] != session.binding.location.target_digest:
            refuse("STALE_VERSION")
        return session

    def _decorate(self, sid, response):
        if response.status != 200 or not response.content_type.startswith("text/html"):
            return response
        self.sessions.require(sid)
        body = response.body.decode("utf-8")
        logout_nonce = self.sessions.action_nonce(sid, PREFIX + "logout")
        banner = (
            '<section class="notice" data-key="b5a-session"><h2>TEST_ONLY 签名会话 · Reviewer 原文只读</h2>'
            "<p>本地测试签名已校验；当前 PostgreSQL Reviewer 授权逐请求复核。不是自然人登录，不是审批或分享权限。</p>"
            "<p>任务元数据仍为合成夹具；报告、来源、Guard 和 HTML 指纹来自实际数据库原始字节。</p>"
            f'<form method="post" action="{PREFIX}logout">'
            + hidden("_csrf", logout_nonce)
            + '<button id="b5a-logout" type="submit">退出该测试会话</button></form></section>'
        )
        body = body.replace(
            '<main id="main" tabindex="-1">', '<main id="main" tabindex="-1">' + banner, 1
        )
        if '<form id="proposal-form"' in body:
            nonce = self.sessions.action_nonce(
                sid, PREFIX + "tasks/" + self.sessions.require(sid).task_id + "/proposal-preview"
            )
            body = re.sub(
                r'(<form id="proposal-form"[^>]*>)',
                lambda m: m[1] + hidden("_csrf", nonce),
                body,
                count=1,
            )
        self.sessions.require(sid)
        return Response(response.status, body.encode("utf-8"), response.content_type)

    def _login_page(self):
        content = (
            '<h1>建立本地 TEST_ONLY 签名会话</h1><section class="notice">'
            "<p>本页不收集、显示或保存身份 Token。独立本地测试发证器通过 Authorization 请求头提交一次性签名凭据。</p>"
            "<p>签名通过后仍须当前 PG Reviewer 授权及原始字节校验；这不是自然人或生产 IdP 登录。</p>"
            "<p>仅 127.0.0.1 HTTP：HttpOnly / SameSite 不能提供生产 TLS 保密性。不得部署或对外开放。</p></section>"
            + hidden("_bootstrap_csrf", self.bootstrap_csrf)
        )
        return Response(
            200, views.frame(PREFIX, "TEST_ONLY 登录", content, "签名入口").encode("utf-8")
        )

    def handle(self, method, target, headers, raw=b""):
        try:
            self._headers(method, headers)
            path, query = self._path(target)
            cookies = self._cookies(headers)
            if method in ("GET", "HEAD") and path == PREFIX + "style.css" and not query:
                return Reply(
                    Response(
                        200,
                        Path(__file__).with_name("style.css").read_bytes(),
                        "text/css; charset=utf-8",
                    )
                )
            if method in ("GET", "HEAD") and path == PREFIX + "login" and not query:
                return Reply(self._login_page())
            if method == "POST" and path == PREFIX + "challenge" and not query:
                if headers.get("Content-Type") != FORM or headers.get("Authorization") is not None:
                    refuse("INVALID_INPUT")
                f = form(raw)
                if set(f) != {"task", "_csrf"} or not secrets.compare_digest(
                    f["_csrf"], self.bootstrap_csrf
                ):
                    refuse("UNAUTHORIZED")
                key, nonce, csrf = self.sessions.challenge(f["task"])
                return Reply(
                    Response(
                        200, json.dumps({"nonce": nonce, "csrf": csrf}).encode(), "application/json"
                    ),
                    (("Set-Cookie", cookie("b5a_challenge", key, 30)),),
                )
            if method == "POST" and path == PREFIX + "session" and not query:
                if raw != b"{}" or headers.get("Content-Type") != "application/json":
                    refuse("INVALID_INPUT")
                sid = self.sessions.login(
                    cookies.get("b5a_challenge", ""),
                    headers.get("Authorization", ""),
                    headers.get("X-B5A-CSRF", ""),
                )
                session = self.sessions.require(sid)
                age = max(0, int(session.expires - self.sessions.clock()))
                return Reply(
                    Response(303, b""),
                    (
                        ("Location", PREFIX),
                        ("Set-Cookie", cookie("b5a_session", sid, age)),
                        ("Set-Cookie", cookie("b5a_challenge", "", 0)),
                    ),
                )
            if headers.get("Authorization") is not None:
                refuse("UNAUTHORIZED")
            sid = cookies.get("b5a_session", "")
            if method == "POST" and path == PREFIX + "logout" and not query:
                if headers.get("Content-Type") != FORM:
                    refuse("INVALID_INPUT")
                f = form(raw)
                if set(f) != {"_csrf"}:
                    refuse("INVALID_INPUT")
                self.sessions.consume_action(sid, path, f["_csrf"])
                self.sessions.logout(sid)
                return Reply(
                    Response(303, b""),
                    (("Location", PREFIX + "login"), ("Set-Cookie", cookie("b5a_session", "", 0))),
                )
            if method == "POST" and path.endswith("/proposal-preview") and not query:
                if headers.get("Content-Type") != FORM:
                    refuse("INVALID_INPUT")
                self._preflight(sid, path, "")
                f = form(raw)
                csrf = f.pop("_csrf", None)
                self.sessions.consume_action(sid, path, csrf)
                session = self.sessions.require(sid)
                task = self.tasks[
                    self.sessions.readers[session.binding.db_role]
                    .pins[session.binding.location]
                    .case
                ]
                if (
                    f.get("version") != str(session.binding.location.version)
                    or f.get("draft") != task["report_pins"]["expected_draft_ref"]
                    or f.get("target") != session.binding.location.target_digest
                ):
                    refuse("STALE_VERSION")
                with self.service.request(sid):
                    values = self.preview.validate(sid, session.task_id, f)
                    response = Response(200, composer(PREFIX, *values).encode("utf-8"))
                return Reply(self._decorate(sid, response))
            if method not in ("GET", "HEAD"):
                refuse("NOT_IMPLEMENTED")
            self._preflight(sid, path, query)
            return Reply(self._decorate(sid, self.interface.dispatch(sid, method, target)))
        except ConsoleError as exc:
            code = str(exc)
            status = (
                503
                if code == "DB_UNAVAILABLE"
                else 409
                if code in ("SOURCE_INTEGRITY", "STALE_VERSION")
                else 501
                if code == "NOT_IMPLEMENTED"
                else 400
                if code == "INVALID_INPUT"
                else 403
            )
            return Reply(Response(status, views.error(PREFIX, code).encode("utf-8")))
        except Exception:
            return Reply(Response(403, views.error(PREFIX, "UNAUTHORIZED").encode("utf-8")))


def server(app, host="127.0.0.1", port=0):
    if host != "127.0.0.1" or type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("B5A_EXACT_LOOPBACK_REQUIRED")

    class Handler(BaseHTTPRequestHandler):
        def send_error(self, code, message=None, explain=None):
            # BaseHTTPRequestHandler otherwise reflects a malformed request
            # line/method into HTML before our application boundary can run.
            self.close_connection = True
            body = b"B5A_REQUEST_DENIED"
            # Malformed version parsing can still have the stdlib HTTP/0.9
            # sentinel; emit a complete fixed HTTP/1.0 error with no-store.
            self.request_version = "HTTP/1.0"
            self.send_response_only(code if 400 <= code <= 599 else 400)
            for name, value in (
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                ("Referrer-Policy", "no-referrer"),
                ("X-Content-Type-Options", "nosniff"),
                ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
                ("Connection", "close"),
            ):
                self.send_header(name, value)
            self.end_headers()
            if getattr(self, "command", "") != "HEAD":
                try:
                    self.wfile.write(body)
                except OSError:
                    pass

        def respond(self):
            self.close_connection = True
            try:
                if any(
                    len(self.headers.get_all(k, [])) > 1
                    for k in [
                        "Host",
                        "Origin",
                        "Cookie",
                        "Authorization",
                        "Content-Length",
                        "Content-Type",
                        "X-B5A-CSRF",
                    ]
                ):
                    reply = Reply(Response(400, b"B5A_REQUEST_DENIED", "text/plain"))
                else:
                    lengths = self.headers.get_all("Content-Length", [])
                    size = (
                        int(lengths[0])
                        if lengths and re.fullmatch(r"[0-9]{1,6}", lengths[0])
                        else 0
                        if not lengths
                        else BODY_LIMIT + 1
                    )
                    self.connection.settimeout(5)
                    # Consume at most one byte beyond the application limit.
                    # Closing with the boundary-sized request still unread can
                    # reset Windows TCP before its fixed413 reaches the client.
                    # Oversize bytes are never passed to the application.
                    raw = self.rfile.read(min(size, BODY_LIMIT + 1)) if size else b""
                    if not 0 <= size <= BODY_LIMIT:
                        reply = Reply(Response(413, b"B5A_REQUEST_DENIED", "text/plain"))
                    else:
                        if len(raw) != size:
                            reply = Reply(Response(400, b"B5A_REQUEST_DENIED", "text/plain"))
                        else:
                            reply = app.handle(self.command, self.path, self.headers, raw)
            except Exception:
                reply = Reply(Response(403, b"B5A_REQUEST_DENIED", "text/plain"))
            response = reply.response
            self.send_response(response.status)
            for key, value in [
                ("Content-Type", response.content_type),
                ("Content-Length", str(len(response.body))),
                ("Cache-Control", "no-store"),
                ("Pragma", "no-cache"),
                (
                    "Referrer-Policy",
                    "same-origin"
                    if response.status == 200 and response.content_type.startswith("text/html")
                    else "no-referrer",
                ),
                ("X-Content-Type-Options", "nosniff"),
                ("Cross-Origin-Resource-Policy", "same-origin"),
                (
                    "Content-Security-Policy",
                    "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; connect-src 'none'",
                ),
                ("Connection", "close"),
                *reply.headers,
            ]:
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                try:
                    self.wfile.write(response.body)
                except OSError:
                    pass

        do_GET = respond
        do_HEAD = respond
        do_POST = respond
        do_PUT = respond
        do_DELETE = respond
        do_PATCH = respond
        do_OPTIONS = respond

        def log_message(self, fmt, *args):
            pass

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = False
        gate = threading.BoundedSemaphore(16)

        def process_request(self, request, client_address):
            if not self.gate.acquire(blocking=False):
                request.close()
                return
            try:
                super().process_request(request, client_address)
            except Exception:
                self.gate.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.gate.release()

        def handle_error(self, request, client_address):
            pass

    http = Server((host, port), Handler)
    app.origin = f"http://127.0.0.1:{http.server_port}"
    return http
