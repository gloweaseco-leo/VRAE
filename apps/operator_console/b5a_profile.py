"""Strict out-of-band TEST_ONLY provisioning; never an HTTP profile/DSN port."""

from dataclasses import fields
import json
from pathlib import Path
import threading

from vrae.identity.boundary import Assignment, TrustAnchor
from vrae.persistence.private_bytes import Locator

from .b5a_http import Application
from .b5a_reader import ReviewerSettings, OriginalPins, ReviewerReader
from .b5a_sessions import SessionStore
from .contracts import TaskRecord


def load_profile(path, audit=None):
    raw = Path(path).read_bytes()
    if not 1 <= len(raw) <= 131072:
        raise ValueError("B5A_PROFILE_BOUND")

    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError("B5A_PROFILE_DUPLICATE")
            result[k] = v
        return result

    p = json.loads(raw, object_pairs_hook=pairs)
    if (
        set(p) != {"version", "settings", "schema_pin", "pins", "tasks", "anchor", "bindings"}
        or p["version"] != "B5A_TEST_ONLY_PROFILE_1"
        or set(p["settings"]) != {f.name for f in fields(ReviewerSettings)}
    ):
        raise ValueError("B5A_PROFILE_SHAPE")
    settings = ReviewerSettings(**p["settings"])
    tasks = {k: TaskRecord.parse(v).document for k, v in p["tasks"].items()}
    if set(tasks) != {"404", "200"}:
        raise ValueError("B5A_PROFILE_TASKS")
    pins = {}
    for value in p["pins"]:
        loc = Locator(**value["location"])
        pin = OriginalPins(
            value["case"],
            loc,
            value["target_sha256"],
            value["manifest_sha256"],
            tuple(value["descriptors"]),
        )
        if loc in pins or pin.case not in tasks:
            raise ValueError("B5A_PROFILE_PINS")
        pins[loc] = pin
    reader = ReviewerReader(settings, pins, tasks, p["schema_pin"], audit=audit)
    a = dict(p["anchor"])
    a["jwks"] = json.dumps(a["jwks"], separators=(",", ":")).encode()
    a["revoked"] = frozenset(a["revoked"])
    anchor = TrustAnchor(**a)
    bindings = {}
    for key, value in p["bindings"].items():
        v = dict(value)
        v["location"] = Locator(**v["location"])
        b = Assignment(**v)
        if (
            b.db_role != settings.user
            or b.location not in pins
            or key != "task-" + pins[b.location].case
        ):
            raise ValueError("B5A_PROFILE_BINDING")
        bindings[key] = b
    sessions = SessionStore(anchor=anchor, bindings=bindings, readers={settings.user: reader})
    return Application(sessions, tasks), raw


class ProvisionedApplication:
    """A changed/unavailable local profile invalidates all prior in-memory state.

    There is no HTTP refresh, administration or token minting endpoint. A bad
    profile cannot leave a previously trusted session usable as fallback.
    """

    def __init__(self, path, *, audit=None):
        self.path, self.audit = Path(path), audit
        self.lock = threading.RLock()
        self.app, self.raw = load_profile(path, audit)

    @property
    def origin(self):
        return self.app.origin

    @origin.setter
    def origin(self, value):
        self.app.origin = value

    def handle(self, *args, **kwargs):
        with self.lock:
            return self._handle(*args, **kwargs)

    def _handle(self, *args, **kwargs):
        try:
            raw = self.path.read_bytes()
            if raw != self.raw:
                old_origin = self.app.origin
                # Invalidation precedes parsing a replacement profile.
                self.app.sessions.sessions.clear()
                self.app.sessions.challenges.clear()
                self.app.sessions.actions.clear()
                fresh, fresh_raw = load_profile(self.path, self.audit)
                fresh.origin = old_origin
                self.app, self.raw = fresh, fresh_raw
            return self.app.handle(*args, **kwargs)
        except Exception:
            from .b5a_http import Reply
            from .interface import Response

            self.app.sessions.sessions.clear()
            self.app.sessions.challenges.clear()
            self.app.sessions.actions.clear()
            return Reply(Response(403, b"B5A_PROVISIONING_UNAVAILABLE", "text/plain"))
