"""Finite ephemeral sessions from accepted single-use B2 identity observations.

All binding/issuer/role/locator inputs are server provisioning, never HTTP fields.
Only opaque random identifiers leave this store. Raw bearer tokens are not kept.
"""

from dataclasses import dataclass, field
import hashlib
import json
import math
import secrets
import threading
import time

from vrae.identity.boundary import IdentityBoundary, TrustAnchor, Assignment, decode, document

from .contracts import refuse


def digest(value):
    return hashlib.sha256(value.encode()).digest()


@dataclass(frozen=True)
class Session:
    binding: Assignment
    task_id: str
    subject: str = field(repr=False)
    generation: str
    expires: float
    kid: str


@dataclass(frozen=True)
class Challenge:
    binding: Assignment
    task_id: str
    generation: str
    nonce: str = field(repr=False)
    csrf_digest: bytes = field(repr=False)
    expires: float


class SessionStore:
    def __init__(
        self,
        *,
        anchor,
        bindings,
        readers,
        clock=time.time,
        session_capacity=64,
        challenge_capacity=128,
        action_capacity=512,
        session_ttl=120,
    ):
        for value in (session_capacity, challenge_capacity, action_capacity):
            if type(value) is not int or not 1 <= value <= 1024:
                raise ValueError("B5A_FINITE_CAP_REQUIRED")
        if type(session_ttl) is not int or not 1 <= session_ttl <= 120:
            raise ValueError("B5A_SHORT_SESSION_REQUIRED")
        self.bindings, self.readers = dict(bindings), dict(readers)
        if any(
            type(b) is not Assignment or b.db_role not in readers for b in self.bindings.values()
        ):
            raise ValueError("B5A_TRUSTED_BINDINGS_REQUIRED")
        self.clock, self.ttl = clock, session_ttl
        self.session_capacity, self.challenge_capacity, self.action_capacity = (
            session_capacity,
            challenge_capacity,
            action_capacity,
        )
        self.sessions, self.challenges, self.actions = {}, {}, {}
        self.boot = secrets.token_hex(32)
        self.last_time = 0
        self.lock = threading.RLock()
        self.boundary = IdentityBoundary(
            anchor=anchor,
            assignments=list(self.bindings.values()),
            connect=self._connect,
            clock=clock,
            skew=0,
            replay_capacity=4096,
        )

    def _connect(self, role):
        if role not in self.readers or self.readers[role].settings.user != role:
            refuse("UNAUTHORIZED")
        return self.readers[role].connect()

    def _now(self):
        now = self.clock()
        if (
            type(now) not in (int, float)
            or not math.isfinite(now)
            or now <= 0
            or now < self.last_time
        ):
            refuse("UNAUTHORIZED")
        self.last_time = now
        self.sessions = {k: v for k, v in self.sessions.items() if v.expires > now}
        self.challenges = {k: v for k, v in self.challenges.items() if v.expires > now}
        self.actions = {k: v for k, v in self.actions.items() if v[2] > now}
        return now

    def _generation(self, now):
        a = self.boundary.anchor
        if (
            type(a) is not TrustAnchor
            or a.available is not True
            or type(a.expires) is not int
            or a.expires <= now
            or type(a.jwks) is not bytes
        ):
            refuse("UNAUTHORIZED")
        raw = json.dumps(
            [
                self.boot,
                a.issuer,
                a.audience,
                a.expires,
                a.available,
                sorted(a.revoked),
                hashlib.sha256(a.jwks).hexdigest(),
            ],
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(raw).hexdigest()

    def _binding(self, binding, now):
        matches = [
            b
            for b in self.boundary.assignments
            if type(b) is Assignment
            and b.issuer == binding.issuer
            and b.subject == binding.subject
            and b.location == binding.location
            and b.active is True
            and b.expires > now
        ]
        if len(matches) != 1 or matches[0] != binding:
            refuse("UNAUTHORIZED")

    def challenge(self, task_id):
        with self.lock:
            now = self._now()
            if task_id not in self.bindings or len(self.challenges) >= self.challenge_capacity:
                refuse("UNAUTHORIZED")
            b = self.bindings[task_id]
            self._binding(b, now)
            generation = self._generation(now)
            key, nonce, csrf = (secrets.token_urlsafe(32) for _ in range(3))
            self.challenges[digest(key)] = Challenge(
                b,
                task_id,
                generation,
                nonce,
                digest(csrf),
                min(now + 30, b.expires, self.boundary.anchor.expires),
            )
            return key, nonce, csrf

    def login(self, challenge_id, bearer, csrf):
        with self.lock:
            now = self._now()
            if not all(
                type(v) is str and 1 <= len(v) <= 8192 for v in (challenge_id, bearer, csrf)
            ):
                refuse("UNAUTHORIZED")
            challenge = self.challenges.pop(digest(challenge_id), None)
            if (
                challenge is None
                or challenge.expires <= now
                or digest(csrf) != challenge.csrf_digest
                or challenge.generation != self._generation(now)
                or len(self.sessions) >= self.session_capacity
            ):
                refuse("UNAUTHORIZED")
            self._binding(challenge.binding, now)
            try:
                if not bearer.startswith("Bearer "):
                    refuse("UNAUTHORIZED")
                h, p, _ = bearer[7:].split(".")
                header, claims = document(decode(h)), document(decode(p))
                # Reject privilege-shaped browser extras before any SQL; these
                # unverified fields are never used to choose identity or scope.
                if set(claims) != {"iss", "aud", "sub", "exp", "nbf", "iat", "jti", "nonce"}:
                    refuse("UNAUTHORIZED")
                observation = self.boundary.check(
                    bearer, challenge.binding.location, nonce=challenge.nonce
                )
                # Only use metadata from this same already signature-verified
                # token; it is discarded immediately, never retained as session.
                expires = min(
                    now + self.ttl,
                    claims["exp"],
                    self.boundary.anchor.expires,
                    challenge.binding.expires,
                )
                if observation.subject != challenge.binding.subject or expires <= now:
                    refuse("UNAUTHORIZED")
                with self.readers[challenge.binding.db_role].request(challenge.binding):
                    pass
                # The session starts only after immutable original validation,
                # not merely a nonempty SQL result or valid signature.
                now = self._now()
                self._binding(challenge.binding, now)
                if challenge.generation != self._generation(now) or expires <= now:
                    refuse("UNAUTHORIZED")
                sid = secrets.token_urlsafe(32)
                self.sessions[digest(sid)] = Session(
                    challenge.binding,
                    challenge.task_id,
                    observation.subject,
                    challenge.generation,
                    expires,
                    header["kid"],
                )
                return sid
            except Exception:
                refuse("UNAUTHORIZED")

    def require(self, sid):
        with self.lock:
            now = self._now()
            if type(sid) is not str or not 32 <= len(sid) <= 128:
                refuse("UNAUTHORIZED")
            session = self.sessions.get(digest(sid))
            if (
                session is None
                or session.generation != self._generation(now)
                or session.kid in self.boundary.anchor.revoked
            ):
                refuse("UNAUTHORIZED")
            self._binding(session.binding, now)
            return session

    def action_nonce(self, sid, path):
        with self.lock:
            session = self.require(sid)
            if len(self.actions) >= self.action_capacity:
                refuse("UNAUTHORIZED")
            raw = secrets.token_urlsafe(32)
            self.actions[digest(raw)] = (digest(sid), path, session.expires)
            return raw

    def consume_action(self, sid, path, raw):
        with self.lock:
            self.require(sid)
            if type(raw) is not str or not 32 <= len(raw) <= 128:
                refuse("UNAUTHORIZED")
            nonce = self.actions.pop(digest(raw), None)
            if nonce is None or nonce[:2] != (digest(sid), path):
                refuse("UNAUTHORIZED")

    def logout(self, sid):
        with self.lock:
            self.require(sid)
            key = digest(sid)
            self.sessions.pop(key, None)
            self.actions = {k: v for k, v in self.actions.items() if v[0] != key}

    def rotate(self, anchor, assignments):
        """Only local provisioning calls this; there is no HTTP mutation port."""
        with self.lock:
            self.boundary.anchor = anchor
            self.boundary.assignments = tuple(assignments)
            self.sessions.clear()
            self.challenges.clear()
            self.actions.clear()
            self.boot = secrets.token_hex(32)
