"""M2 short sessions established ONLY by the public SignedGeneratedReader.

No signing key, APP config, private authenticator, legacy Locator or report cache.
The original one-use token is discarded after login. Each subsequent operation
replays current M1 bytes under the original assignment locks in its transaction.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import math
import secrets
import threading

from vrae.application.ra4b_p2.m1.reader import SignedGeneratedReader, GeneratedReport, JobAssignment
from vrae.application.ra4b_p2.m1.consumer import TaskClient, TaskHandle
from vrae.application.ra4b_p2.m1.producer import Output, replay
from vrae.identity.boundary import document, decode, IdentityDenied
from .b5b_m2_report import ReportView


def denied():
    raise IdentityDenied('M2_SESSION_DENIED') from None


def digest(value):
    return hashlib.sha256(value.encode()).digest()


@dataclass(frozen=True)
class GeneratedSession:
    assignment: object = field(repr=False)
    expires: float
    generation: str


class GeneratedSessions:
    def __init__(self, reader):
        if type(reader) is not SignedGeneratedReader:
            raise ValueError('M2_ACCEPTED_READER_REQUIRED')
        self.reader = reader
        self.lock = threading.RLock()
        self.sessions, self.challenges, self.actions = {}, {}, {}
        self.boot = secrets.token_hex(32)
        self.last = 0
        self.refresh = lambda: None
        self.task_handles = {}

    def now(self):
        n = self.reader.clock()
        if type(n) not in (int, float) or not math.isfinite(n) or n <= 0 or n < self.last:
            denied()
        self.last = n
        self.sessions = {k: v for k, v in self.sessions.items() if v.expires > n}
        self.challenges = {k: v for k, v in self.challenges.items() if v[3] > n}
        self.actions = {k: v for k, v in self.actions.items() if v[2] > n}
        return n

    def generation(self):
        a = self.reader.anchor
        if not a.available or a.expires <= self.now():
            denied()
        return hashlib.sha256(json.dumps([
            self.boot, a.issuer, a.audience, a.expires, a.available,
            sorted(a.revoked), hashlib.sha256(a.jwks).hexdigest(),
        ], sort_keys=True).encode()).hexdigest()

    def bind_task(self, assignment, client, task):
        with self.lock:
            if (type(assignment) is not JobAssignment or type(client) is not TaskClient
                    or type(task) is not TaskHandle or assignment.tenant != task.tenant_id
                    or assignment.job_id != task.job_id or assignment.expires <= self.now()):
                denied()
            old = [a for a in self.reader.assignments if (a.tenant, a.job_id) == (assignment.tenant, assignment.job_id)]
            if old and old != [assignment]:
                denied()
            if not old:
                if len(self.reader.assignments) >= 40:
                    denied()
                self.reader.assignments = (*self.reader.assignments, assignment)
            self.task_handles[(assignment.tenant, assignment.job_id)] = (client, task)

    def challenge(self, tenant, job_id):
        with self.lock:
            now = self.now()
            matches = [a for a in self.reader.assignments
                       if a.tenant == tenant and a.job_id == job_id and a.active and a.expires > now]
            if len(matches) != 1 or len(self.challenges) >= 128:
                denied()
            challenge, nonce, csrf = (secrets.token_urlsafe(32) for _ in range(3))
            self.challenges[digest(challenge)] = (
                matches[0], nonce, digest(csrf), min(now + 30, matches[0].expires), self.generation())
            return challenge, nonce, csrf

    def login(self, challenge, bearer, csrf):
        with self.lock:
            now = self.now()
            value = self.challenges.pop(digest(challenge), None)
            if (value is None or value[2] != digest(csrf) or value[3] <= now
                    or value[4] != self.generation() or len(self.sessions) >= 64):
                denied()
            assignment, nonce = value[:2]
            # Public accepted crypto + actual PG16 role/scope + native replay.
            bound = self.task_handles.get((assignment.tenant, assignment.job_id))
            if bound is None:
                self.reader.read(bearer, assignment.tenant, assignment.job_id, nonce=nonce)
            else:
                client, task = bound
                client.read(task, self.reader, bearer, nonce=nonce)
            # Metadata from the EXACT already-verified token, never authority
            # from an unverified parse and never retained bearer bytes.
            claims = document(decode(bearer[7:].split('.')[1]))
            if claims['sub'] != assignment.subject:
                denied()
            expires = min(now + 120, claims['exp'], assignment.expires, self.reader.anchor.expires)
            if expires <= self.now() or value[4] != self.generation():
                denied()
            sid = secrets.token_urlsafe(32)
            self.sessions[digest(sid)] = GeneratedSession(assignment, expires, value[4])
            return sid

    def require(self, sid):
        self.refresh()
        now = self.now()
        if type(sid) is not str or not 32 <= len(sid) <= 128:
            denied()
        session = self.sessions.get(digest(sid))
        if session is None:
            denied()
        a = session.assignment
        matches = [v for v in self.reader.assignments
                   if (v.issuer, v.subject, v.tenant, v.job_id, v.db_role)
                   == (a.issuer, a.subject, a.tenant, a.job_id, a.db_role)]
        if (session.expires <= now or session.generation != self.generation()
                or matches != [a] or not a.active or a.expires <= now):
            denied()
        return session

    def action(self, sid, path):
        with self.lock:
            s = self.require(sid)
            if len(self.actions) >= 512:
                denied()
            raw = secrets.token_urlsafe(32)
            self.actions[digest(raw)] = (digest(sid), path, s.expires)
            return raw

    def consume(self, sid, path, raw):
        with self.lock:
            self.require(sid)
            if type(raw) is not str or not 32 <= len(raw) <= 128:
                denied()
            value = self.actions.pop(digest(raw), None)
            if value is None or value[:2] != (digest(sid), path):
                denied()

    @contextmanager
    def request(self, sid):
        with self.lock:
            session = self.require(sid)
            a = session.assignment
            with self.reader.connect(a.db_role) as c:
                if (not c.autocommit or c.info.host not in ('127.0.0.1', 'localhost')
                        or c.info.dbname != 'vrae_ra4a_p1'):
                    denied()
                row = c.execute("SELECT session_user,current_user,current_setting('server_version_num')::int,"
                    "rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,"
                    "pg_has_role(session_user,'p2b1_review','MEMBER') FROM pg_roles WHERE rolname=session_user").fetchone()
                if (not row or row[:2] != (a.db_role, a.db_role) or not 160000 <= row[2] < 170000
                        or any(row[3:7]) or row[7] is not True):
                    denied()
                with c.transaction():
                    raw = c.execute('SELECT * FROM ra4b_p2.m1_read_assigned(%s,%s)',
                                    (a.tenant, a.job_id)).fetchone()
                    if not raw:
                        denied()
                    loc = raw[0]
                    source, report, html = (bytes(v) for v in raw[1:])
                    view = ReportView(GeneratedReport(loc, source, report, html))
                    d = replay(Output(source, report, html, b''))
                    if (d['scope']['tenant_id'] != a.tenant or loc['job_id'] != a.job_id
                            or loc['tenant_id'] != a.tenant):
                        denied()
                    bound = self.task_handles.get((a.tenant, a.job_id))
                    if bound is not None and any(loc.get(k) != getattr(bound[1], k)
                            for k in ('tenant_id', 'request_id', 'run_id', 'job_id')):
                        denied()
                    yield c, view
                    # The caller submits only inside this scope; never return
                    # a durable receipt until this real outer COMMIT succeeds.
                    if self.require(sid) != session:
                        denied()
