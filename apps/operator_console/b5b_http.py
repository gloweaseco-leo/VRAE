"""Additive consumer of accepted B5/B6 ports on the SAME signed SSR server."""

from vrae.b6_p0.reader import PrivateHandoffReader
from vrae.b6_p0.delivery import DeliveryAuthorizationGate
from vrae.b6_p0.contracts import B6Denied
from .b5a_http import PREFIX, FORM, Reply, form
from .b5p0_http import RehearsalApplication
from .contracts import ConsoleError, refuse
from .interface import Response
from . import b5b_views as views


class Application:
    def __init__(self, rehearsal, handoff, *, refresh=lambda: None):
        if (
            type(rehearsal) is not RehearsalApplication
            or type(handoff) is not PrivateHandoffReader
            or handoff.sessions is not rehearsal.sessions
        ):
            raise ValueError("B5B_ACCEPTED_SHARED_SESSION_PORTS_REQUIRED")
        self.rehearsal, self.handoff, self.refresh = rehearsal, handoff, refresh
        self.delivery = DeliveryAuthorizationGate()

    @property
    def origin(self):
        return self.rehearsal.origin

    @origin.setter
    def origin(self, value):
        self.rehearsal.origin = value

    def _reply(self, status, html):
        return Reply(Response(status, html.encode("utf-8")))

    def handle(self, method, target, headers, raw=b""):
        app = self.rehearsal
        with app.sessions.lock:
            try:
                app.base._headers(method, headers)
                path, query = app.base._path(target)
                parts = path.removeprefix(PREFIX).split("/")
                own = len(parts) >= 3 and parts[0] == "tasks" and parts[2] == "b5b"
                if own:
                    if len(parts) != 4 or headers.get("Authorization") is not None or query:
                        refuse("INVALID_INPUT")
                    sid = app.base._cookies(headers).get("b5a_session", "")
                    self.refresh()
                    session, _ = app.current(sid)
                    if parts[1] != session.task_id:
                        refuse("UNAUTHORIZED")
                    # Accepted B3 witness/epoch and original-byte probe, without
                    # changing the original read, save or receipt implementation.
                    app.capture(sid)
                    action = parts[3]
                    if action == "worker-result" and method in ("GET", "HEAD"):
                        return self._reply(409, views.blocked())
                    if action in ("private-preview", "private-document") and method in (
                        "GET",
                        "HEAD",
                    ):
                        package = self.handoff.prepare(sid)
                        if action == "private-document":
                            app.current(sid, session)
                            return Reply(Response(200, package.private_html))
                        csrf = app.sessions.action_nonce(
                            sid, PREFIX + "tasks/" + session.task_id + "/b5b/delivery"
                        )
                        html = views.preview(package, session.task_id, csrf)
                        app.current(sid, session)
                        return self._reply(200, html)
                    if action == "delivery" and method == "POST":
                        if headers.get("Content-Type") != FORM:
                            refuse("INVALID_INPUT")
                        fields = form(raw)
                        if set(fields) != {"_csrf", "operation"}:
                            refuse("INVALID_INPUT")
                        app.sessions.consume_action(sid, path, fields["_csrf"])
                        # No submitted candidate/recipient/claim can become
                        # authority. Even a valid operation uses the old DENY gate.
                        import json

                        receipt = json.loads(self.delivery.attempt(fields["operation"]))
                        app.current(sid, session)
                        return self._reply(403, views.denial(receipt))
                    refuse("NOT_IMPLEMENTED")
                reply = app.handle(method, target, headers, raw)
                # Keep all original mutations and receipt bytes untouched. Add
                # navigation only to an already-authorized signed home/task page.
                decorate = method in ("GET", "HEAD") and (
                    path == PREFIX or len(parts) == 2 and parts[0] == "tasks"
                )
                response = reply.response
                if (
                    decorate
                    and response.status == 200
                    and response.content_type.startswith("text/html")
                ):
                    sid = app.base._cookies(headers).get("b5a_session", "")
                    session, _ = app.current(sid)
                    html = response.body.decode("utf-8")
                    marker = '<main id="main" tabindex="-1">'
                    if html.count(marker) != 1:
                        refuse("SOURCE_INTEGRITY")
                    html = html.replace(marker, marker + views.navigation(session.task_id), 1)
                    return Reply(
                        Response(200, html.encode("utf-8"), response.content_type), reply.headers
                    )
                return reply
            except (ConsoleError, B6Denied) as exc:
                code = str(exc)
                status = 409 if code in {"STALE_VERSION", "SOURCE_INTEGRITY"} else 403
                from .b5p0_views import error

                return self._reply(
                    status, error(PREFIX, code if isinstance(exc, ConsoleError) else "UNAUTHORIZED")
                )
            except Exception:
                from .b5p0_views import error

                return self._reply(403, error(PREFIX, "UNAUTHORIZED"))
