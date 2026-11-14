"""Composition around the SAME accepted B5A SSR server and /b5a namespace."""

import hashlib
import hmac
import secrets

from vrae.b3_p0.contracts import Command, Denied
from vrae.reviewing.canonical import canonical, sha

from .b5a_http import PREFIX, FORM, Reply, form
from .contracts import ConsoleError, refuse
from .interface import Response
from .views import link
from .b5p0_binding import Binding, intent_port, original_graph, probe
from . import b5p0_views as views


class RehearsalApplication:
    def __init__(self, base, bindings, journal, *, key_secret, audit=None, refresh=lambda: None):
        if (
            not isinstance(key_secret, bytes)
            or len(key_secret) < 32
            or any(type(v) is not Binding for v in bindings.values())
        ):
            raise ValueError("B5P0_TRUSTED_PROVISIONING_REQUIRED")
        self.base, self.sessions, self.tasks = base, base.sessions, base.tasks
        self.bindings, self.journal = dict(bindings), journal
        self.key_secret, self.sink, self.refresh = key_secret, audit, refresh
        self.tickets = {}
        self.probe_key = "b5p0-probe-" + secrets.token_hex(24)

    @property
    def origin(self):
        return self.base.origin

    @origin.setter
    def origin(self, value):
        self.base.origin = value

    def audit(self, event, **facts):
        if self.sink:
            self.sink({"event": event, **facts})

    def current(self, sid, expected=None):
        self.refresh()
        session = self.sessions.require(sid)
        if expected is not None and session is not expected:
            refuse("UNAUTHORIZED")
        binding = self.bindings.get(session.task_id)
        if (
            binding is None
            or binding.issuer != session.binding.issuer
            or binding.issuer != self.sessions.boundary.anchor.issuer
            or binding.subject != session.subject
            or binding.subject != session.binding.subject
            or binding.role != session.binding.db_role
            or binding.witness.location != session.binding.location
        ):
            refuse("UNAUTHORIZED")
        return session, binding

    def capture(self, sid, fields=None):
        session, binding = self.current(sid)
        with self.base.service.request(sid):
            snapshot = self.base.service.current.get()[2]
            graph = original_graph(snapshot)
            command = None
            if fields is not None:
                _, _, command, outcome = self.base.preview.validate(sid, session.task_id, fields)
                if outcome != "CONTRACT_VALID_ONLY":
                    refuse("INVALID_INPUT")
            task = self.tasks[snapshot["pin"].case]
            dossier = snapshot["dossier"]

        # The accepted B5A reader's tenant lock is now released. B3 performs its
        # own fresh native byte replay under its real transaction/authority locks.
        def check():
            return self.current(sid, session)

        settings = self.sessions.readers[binding.role].settings
        probe(settings, graph, binding, check, self.audit, self.probe_key)
        check()
        return session, binding, graph, task, dossier, command

    def read_receipt(self, sid, session, binding, graph, task):
        entry = self.journal.read(binding.scope)
        if entry is None:
            refuse("B5P0_UNKNOWN_COMMIT")

        def check():
            return self.current(sid, session)

        settings = self.sessions.readers[binding.role].settings
        try:
            with intent_port(settings, graph, check, self.audit, binding) as (port, _):
                receipt = port.get_receipt(binding.witness, self.journal.key(entry))
        except Denied as exc:
            if str(exc) == "UNKNOWN_COMMIT":
                refuse("B5P0_UNKNOWN_COMMIT")
            raise
        self.verify_receipt(receipt, binding, graph, entry)
        check()
        self.journal.confirmed(binding.scope, sha(receipt.payload))
        self.audit("receipt_verified", mapping=binding.scope, receipt_sha256=sha(receipt.payload))
        return Reply(
            Response(
                200,
                views.receipt(
                    PREFIX, session.task_id, receipt.document, sha(receipt.payload), binding.scope
                ).encode(),
            )
        )

    def verify_receipt(self, receipt, binding, graph, entry):
        d = receipt.document
        command = Command(entry["command"]).proposal()
        from vrae.reviewing import ReviewTarget, validate_proposal

        if (
            d["subject"] != binding.b3_subject
            or d["db_actor"] != binding.role
            or d["target_digest"] != binding.witness.location.target_digest
            or d["source_sha256"] != sha(next(a.raw for a in graph.artifacts if a.kind == "SOURCE"))
            or d["html_sha256"] != sha(next(a.raw for a in graph.artifacts if a.kind == "HTML"))
            or d["manifest_sha256"] != sha(graph.manifest)
            or d["command_digest"] != validate_proposal(command, ReviewTarget(graph.target))
            or d["idempotency_key"] != self.journal.key(entry)
            or entry["receipt_sha"] not in (None, sha(receipt.payload))
        ):
            refuse("SOURCE_INTEGRITY")

    def handle(self, method, target, headers, raw=b""):
        # Same lock used by accepted signed login/logout/rotate. All requests in
        # this process acquire it before any PG reader/transaction locks.
        with self.sessions.lock:
            try:
                self.refresh()
                self.base._headers(method, headers)
                path, query = self.base._path(target)
                cookies = self.base._cookies(headers)
                sid = cookies.get("b5a_session", "")
                parts = path.removeprefix(PREFIX).split("/")
                own = len(parts) in (3, 4) and parts[0] == "tasks" and parts[2] == "rehearsal"
                if own:
                    if query or headers.get("Authorization") is not None:
                        refuse("INVALID_INPUT")
                    session, binding = self.current(sid)
                    if parts[1] != session.task_id:
                        refuse("UNAUTHORIZED")
                    if len(parts) == 4:
                        if parts[3] != "receipt" or method not in ("GET", "HEAD"):
                            refuse("NOT_IMPLEMENTED")
                        session, binding, graph, task, _, _ = self.capture(sid)
                        return self.read_receipt(sid, session, binding, graph, task)
                    if method in ("GET", "HEAD"):
                        session, binding, graph, task, dossier, _ = self.capture(sid)
                        self.tickets = {
                            k: v
                            for k, v in self.tickets.items()
                            if v["expires"] > self.sessions.clock()
                        }
                        if len(self.tickets) >= 128:
                            refuse("UNAUTHORIZED")
                        ticket = secrets.token_urlsafe(32)
                        csrf = self.sessions.action_nonce(sid, path)
                        self.tickets[ticket] = {
                            "sid": sha(sid.encode()),
                            "generation": session.generation,
                            "scope": binding.scope,
                            "csrf": sha(csrf.encode()),
                            "body": None,
                            "expires": session.expires,
                        }
                        html = views.page(PREFIX, task, dossier, path, ticket, csrf)
                        self.current(sid, session)
                        return Reply(Response(200, html.encode()))
                    if method != "POST" or headers.get("Content-Type") != FORM:
                        refuse("NOT_IMPLEMENTED")
                    f = form(raw)
                    ticket = f.pop("_ticket", None)
                    csrf = f.pop("_csrf", None)
                    row = self.tickets.get(ticket)
                    if (
                        row is None
                        or not isinstance(csrf, str)
                        or row["sid"] != sha(sid.encode())
                        or row["generation"] != session.generation
                        or row["scope"] != binding.scope
                        or not secrets.compare_digest(row["csrf"], sha(csrf.encode()))
                    ):
                        refuse("UNAUTHORIZED")
                    body_hash = sha(raw)
                    if row["body"] is not None and row["body"] != body_hash:
                        refuse("B5P0_CONFLICT")
                    if row["body"] is None:
                        self.sessions.consume_action(sid, path, csrf)
                    session, binding, graph, task, dossier, command = self.capture(sid, f)
                    semantic = sha(canonical(command))
                    entry = self.journal.read(binding.scope)
                    if entry is not None:
                        if entry["semantic"] != semantic:
                            refuse("B5P0_CONFLICT")
                        row["body"] = body_hash
                        # Existing attempts are resolved only by fresh authorized
                        # key lookup. Never send again or replace the original key.
                        return self.read_receipt(sid, session, binding, graph, task)
                    key = (
                        "b5p0-"
                        + hmac.new(
                            self.key_secret,
                            canonical([binding.scope, session.generation, ticket, semantic]),
                            hashlib.sha256,
                        ).hexdigest()
                    )
                    command["idempotency_key"] = key
                    payload = canonical(command)
                    entry = self.journal.attempted(
                        binding.scope, semantic, payload, session.generation
                    )
                    row["body"] = body_hash
                    settings = self.sessions.readers[binding.role].settings

                    def check():
                        return self.current(sid, session)

                    self.audit("intent_attempt", mapping=binding.scope, command_sha256=sha(payload))
                    with intent_port(settings, graph, check, self.audit, binding) as (port, _):
                        receipt = port.submit(binding.witness, Command(payload))
                    self.verify_receipt(receipt, binding, graph, entry)
                    self.journal.confirmed(binding.scope, sha(receipt.payload))
                    return self.read_receipt(sid, session, binding, graph, task)
                public = path in (
                    PREFIX + "login",
                    PREFIX + "style.css",
                    PREFIX + "challenge",
                    PREFIX + "session",
                )
                if not public:
                    session, binding, graph, task, _, _ = self.capture(sid)
                result = self.base.handle(method, target, headers, raw)
                if (
                    not public
                    and result.response.status == 200
                    and result.response.content_type.startswith("text/html")
                ):
                    self.current(sid, session)
                    body = result.response.body.decode("utf-8")
                    block = views.NOTICE + link(
                        PREFIX + "tasks/" + session.task_id + "/rehearsal",
                        "进入内部演练（非审批）",
                        key="b5p0-entry",
                    )
                    body = body.replace(
                        '<main id="main" tabindex="-1">',
                        '<main id="main" tabindex="-1">' + block,
                        1,
                    )
                    body = views.internal_footer(body)
                    result = Reply(
                        Response(200, body.encode(), result.response.content_type), result.headers
                    )
                return result
            except (ConsoleError, Denied) as exc:
                code = str(exc)
                if code == "UNKNOWN_COMMIT":
                    code = "B5P0_UNKNOWN_COMMIT"
                if code not in {
                    "B5P0_UNKNOWN_COMMIT",
                    "B5P0_CONFLICT",
                    "INVALID_INPUT",
                    "SOURCE_INTEGRITY",
                    "STALE_VERSION",
                }:
                    code = "UNAUTHORIZED"
                return Reply(
                    Response(
                        409
                        if code
                        in {
                            "B5P0_UNKNOWN_COMMIT",
                            "B5P0_CONFLICT",
                            "SOURCE_INTEGRITY",
                            "STALE_VERSION",
                        }
                        else 403,
                        views.error(PREFIX, code).encode(),
                    )
                )
            except Exception:
                return Reply(Response(403, views.error(PREFIX, "UNAUTHORIZED").encode()))
