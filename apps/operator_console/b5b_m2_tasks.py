"""Durable routing for the accepted TaskClient; no report/assignment authority."""

from dataclasses import asdict
from contextlib import contextmanager
import json
from pathlib import Path
import secrets
import re
import sqlite3

from vrae.application.ra4b_p2.m1.consumer import TaskClient, TaskHandle
from vrae.application.ra4b_p2.m1.reader import JobAssignment
from .b5b_m2_sessions import denied

SOURCES = {'404': 'accepted-404', '200': 'accepted-200'}


class TaskWorkflow:
    def __init__(self, client, journal, *, sources=None):
        if type(client) is not TaskClient or not set(SOURCES.values()) <= client.endpoint.source_refs:
            raise ValueError('M2_ACCEPTED_TASK_CLIENT_REQUIRED')
        self.client = client
        defaults = {
            '404': {'source_ref': SOURCES['404'], 'label': '制造业 · 联系路径404', 'depth': 'L1'},
            '200': {'source_ref': SOURCES['200'], 'label': '制造业 · 静态路径200／证据不足', 'depth': 'L1'},
        }
        choices = defaults if sources is None else sources
        if type(choices) is not dict or not 1 <= len(choices) <= 8:
            raise ValueError('M2_PRIVATE_SOURCE_CATALOG_REQUIRED')
        self.source_refs, self.source_labels, self.source_depths, self.source_enabled = {}, {}, {}, {}
        for case, spec in choices.items():
            if (type(case) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,32}', case)
                    or type(spec) is not dict or set(spec) not in ({'source_ref', 'label', 'depth'}, {'source_ref', 'label', 'depth', 'enabled'})
                    or type(spec['source_ref']) is not str or spec['source_ref'] not in client.endpoint.source_refs
                    or type(spec['label']) is not str or not 1 <= len(spec['label']) <= 160
                    or any(ord(c) < 32 for c in spec['label']) or spec['depth'] not in ('L1', 'L2')
                    or type(spec.get('enabled', True)) is not bool
                    or (case in SOURCES and {k: v for k, v in spec.items() if k != 'enabled'} != defaults[case])):
                raise ValueError('M2_PRIVATE_SOURCE_CATALOG_REQUIRED')
            self.source_refs[case] = spec['source_ref']
            self.source_labels[case] = spec['label']
            self.source_depths[case] = spec['depth']
            self.source_enabled[case] = spec.get('enabled', True)
        if len(set(self.source_refs.values())) != len(self.source_refs):
            raise ValueError('M2_PRIVATE_SOURCE_CATALOG_REQUIRED')
        self.path = Path(journal)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError('M2_PRIVATE_TASK_JOURNAL_REQUIRED')
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS tasks(ticket TEXT PRIMARY KEY, owner TEXT NOT NULL, '
                      'source_case TEXT NOT NULL, idem TEXT UNIQUE NOT NULL, handle TEXT)')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=2)
        try:
            with c:
                yield c
        finally:
            c.close()

    @staticmethod
    def owner(session):
        a = session.assignment
        return json.dumps([a.issuer, a.subject, a.db_role, a.tenant], separators=(',', ':'))

    def row(self, ticket, session):
        with self.connect() as c:
            row = c.execute('SELECT owner,source_case,idem,handle FROM tasks WHERE ticket=?', (ticket,)).fetchone()
        if row is None or row[0] != self.owner(session) or session.assignment.tenant != self.client.endpoint.tenant_id:
            denied()
        return row

    def list(self, session):
        if session.assignment.tenant != self.client.endpoint.tenant_id:
            denied()
        with self.connect() as c:
            return c.execute('SELECT ticket,source_case,handle IS NOT NULL FROM tasks WHERE owner=? ORDER BY rowid DESC LIMIT 40',
                             (self.owner(session),)).fetchall()

    def create(self, sessions, sid, case, *, ticket=None):
        with sessions.lock:
            session = sessions.require(sid)
            # Fresh actual parent-task authorization, released before APP HTTP
            # admission (which independently takes its original tenant locks).
            with sessions.request(sid):
                pass
            if session.assignment.tenant != self.client.endpoint.tenant_id or case not in self.source_refs or not self.source_enabled[case]:
                denied()
            if ticket is None:
                ticket, key = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                with self.connect() as c:
                    if c.execute('SELECT count(*) FROM tasks').fetchone()[0] >= 40:
                        denied()
                    c.execute('INSERT INTO tasks VALUES(?,?,?,?,NULL)', (ticket, self.owner(session), case, key))
            owner, held_case, key, raw = self.row(ticket, session)
            if case != held_case:
                denied()
            if raw is None:
                task = self.client.create(self.source_refs[case], idempotency_key=key)
                # A lost/expired response is recovered with the SAME persisted
                # key. No guessed handle or new key can stand in for APP202.
                sessions.require(sid)
                with sessions.request(sid):
                    pass
                with self.connect() as c:
                    c.execute('UPDATE tasks SET handle=? WHERE ticket=? AND owner=?',
                              (json.dumps(asdict(task), sort_keys=True), ticket, owner))
            return ticket

    def task(self, ticket, session):
        row = self.row(ticket, session)
        if row[3] is None:
            return None
        task = TaskHandle(**json.loads(row[3]))
        if task.tenant_id != session.assignment.tenant or task.source_ref != self.source_refs.get(row[1]):
            denied()
        return task

    def status(self, ticket, sessions, sid):
        with sessions.lock:
            session = sessions.require(sid)
            with sessions.request(sid):
                pass
            task = self.task(ticket, session)
            if task is None:
                return None, None
            state = self.client.status(task)
            sessions.require(sid)
            # Status HTTP uses the separate APP service identity. Fence its
            # return with a NEW native Reviewer read as well, so a DB revoke
            # during that HTTP call cannot escape as a successful status view.
            with sessions.request(sid):
                pass
            return task, state

    def challenge(self, ticket, sessions, sid):
        with sessions.lock:
            task, state = self.status(ticket, sessions, sid)
            if task is None or state.get('job_state') != 'TEST_ONLY_DONE':
                denied()
            a = sessions.require(sid).assignment
            assignment = JobAssignment(a.issuer, a.subject, a.db_role, task.tenant_id, task.job_id, a.expires)
            # This is a server routing binding, NEVER an INSERT/UPDATE of the
            # DB assignment. Worker COMMIT remains its sole accepted creator.
            sessions.bind_task(assignment, self.client, task)
            return sessions.challenge(task.tenant_id, task.job_id)
