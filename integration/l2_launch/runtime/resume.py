"""CONTROLLED callable return-flow proposal; no HTTP service or permanent identity.

Invites and sessions only retain server-held routing. Every read still needs the
original current APP/PG authority; report release remains independently denied.
Restart clears the ephemeral map and ends all old return access.
"""

from dataclasses import dataclass
import hashlib
import math
import re
import secrets
import time

from integration.l2_launch.runtime.adapter import Denied, PrivateAdapter

HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
COOKIE = "__Host-vrae-return"


@dataclass(frozen=True)
class Held:
    tenant: str
    task: object
    expires: float
    deadline: float


class ResumeProposal:
    def __init__(self, adapter):
        if type(adapter) is not PrivateAdapter:
            raise Denied("RETURN_ACCESS_ENDED")
        self.adapter = adapter
        self.invites = {}
        self.sessions = {}

    @staticmethod
    def digest(value):
        if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]{32,128}", value) is None:
            raise Denied("RETURN_ACCESS_ENDED")
        return hashlib.sha256(value.encode()).hexdigest()

    def issue_controlled(self, tenant, task, *, ttl=120):
        # Trusted supervisor only, not a browser endpoint or customer authority.
        if type(ttl) not in (int, float) or not math.isfinite(ttl) or not 0 < ttl <= 120:
            raise Denied("RETURN_ACCESS_ENDED")
        self.adapter.status(tenant, task)
        invitation = secrets.token_urlsafe(32)
        self.invites[self.digest(invitation)] = Held(
            tenant, task, min(time.time() + 120, self.adapter.policy.expires)
        )
        return invitation

    def current(self, held, tenant):
        if (
            held is None
            or held.tenant != tenant
            or time.time() >= held.expires
            or time.monotonic() >= held.deadline
        ):
            raise Denied("RETURN_ACCESS_ENDED")
        try:
            return self.adapter.status(tenant, held.task)
        except ValueError:
            raise Denied("RETURN_ACCESS_ENDED") from None

    def exchange(self, tenant, invitation):
        key = self.digest(invitation)
        held = self.invites.pop(key, None)  # consume once, including failed attempts
        self.current(held, tenant)
        sid = secrets.token_urlsafe(32)
        self.sessions[self.digest(sid)] = held
        # Transport candidate only: no actual listener/browser cookie is created.
        return f"{COOKIE}={sid}; Path=/; HttpOnly; Secure; SameSite=Strict", dict(HEADERS)

    def status(self, tenant, cookie_header, *, query=""):
        if query or type(cookie_header) is not str or not cookie_header.startswith(COOKIE + "="):
            raise Denied("RETURN_ACCESS_ENDED")
        sid = cookie_header[len(COOKIE) + 1 :]
        if ";" in sid or "&" in sid or "=" in sid:
            raise Denied("RETURN_ACCESS_ENDED")
        held = self.sessions.get(self.digest(sid))
        return self.current(held, tenant), dict(HEADERS)

    def revoke_all(self):
        self.invites.clear()
        self.sessions.clear()
