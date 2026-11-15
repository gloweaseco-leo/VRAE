"""Actual signed subject and low-privilege PG originals, no API or mocked SQL."""

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import time
import uuid

from psycopg import sql
from apps.operator_console.b5a_sessions import SessionStore
from integration.ra4c_b5a.probe import provision
from tests.identity.issuer import Issuer, ISSUER, AUDIENCE
from vrae.identity.boundary import Assignment, TrustAnchor
from vrae.persistence.private_bytes import locator
from vrae.b6_p0.reader import PrivateHandoffReader, RecipientPolicyDescriptor

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def fingerprint(c):
    tables = c.execute("SELECT n.nspname,t.relname FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE t.relkind='r' AND n.nspname NOT IN ('information_schema','pg_catalog') AND n.nspname NOT LIKE 'pg_toast%' ORDER BY 1,2").fetchall()
    contents = []
    for schema, table in tables:
        contents.append([schema, table, c.execute(sql.SQL("SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]'::jsonb) FROM {}.{} x").format(sql.Identifier(schema), sql.Identifier(table))).fetchone()[0]])
    catalog = c.execute("SELECT n.nspname,p.proname,pg_get_functiondef(p.oid),p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname LIKE 'ra4a%' OR n.nspname LIKE 'b3%' ORDER BY 1,2,3").fetchall()
    policies = c.execute("SELECT * FROM pg_policies WHERE schemaname LIKE 'ra4a%' OR schemaname LIKE 'b3%' ORDER BY schemaname,tablename,policyname").fetchall()
    relations = c.execute("SELECT n.nspname,t.relname,pg_get_userbyid(t.relowner),t.relacl::text,t.relrowsecurity,t.relforcerowsecurity FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname LIKE 'ra4a%' OR n.nspname LIKE 'b3%' ORDER BY 1,2").fetchall()
    constraints = c.execute("SELECT n.nspname,t.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class t ON t.oid=k.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname LIKE 'ra4a%' OR n.nspname LIKE 'b3%' ORDER BY 1,2,3").fetchall()
    triggers = c.execute("SELECT n.nspname,t.relname,g.tgname,pg_get_triggerdef(g.oid) FROM pg_trigger g JOIN pg_class t ON t.oid=g.tgrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE NOT g.tgisinternal AND (n.nspname LIKE 'ra4a%' OR n.nspname LIKE 'b3%') ORDER BY 1,2,3").fetchall()
    schemas = c.execute("SELECT nspname,pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace WHERE nspname LIKE 'ra4a%' OR nspname LIKE 'b3%' OR nspname='public' ORDER BY 1").fetchall()
    defaults = c.execute("SELECT pg_get_userbyid(d.defaclrole),n.nspname,d.defaclobjtype,d.defaclacl::text FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace ORDER BY 1,2,3").fetchall()
    roles = c.execute("SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolinherit FROM pg_roles ORDER BY 1").fetchall()
    memberships = c.execute("SELECT pg_get_userbyid(roleid),pg_get_userbyid(member),admin_option,inherit_option,set_option FROM pg_auth_members ORDER BY 1,2").fetchall()
    return {"business_sha256": digest(contents), "catalog_sha256": digest([catalog,policies,relations,constraints,triggers,schemas,defaults]),
            "roles_sha256": digest([roles,memberships]), "tables": [s+"."+t for s,t in tables]}


class Runtime:
    def __init__(self, owner, case_id):
        self.owner, self.case_id = owner, case_id
        self.dbname = "vrae_p2b1_" + uuid.uuid4().hex[:12]
        self.private = owner.private / ("case-" + uuid.uuid4().hex[:10])
        self.private.mkdir()
        self.events, self.secrets = [], []
        self.graphs = owner.graphs
        self.state_path = owner.state_path
        self.state = owner.state

    def start(self):
        with self.owner.connect(dbname="postgres") as c:
            c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(self.dbname),sql.Identifier(self.owner.dbname)))
        self.reader, self.tasks = provision(self, self.events.append)
        now = int(time.time())
        self.issuer = Issuer()
        self.bindings = {"task-"+case: Assignment(ISSUER,"synthetic-reviewer-1",self.reader.settings.user,locator(g),now+3600) for case,g in self.graphs.items()}
        self.store = SessionStore(anchor=TrustAnchor(ISSUER,AUDIENCE,self.issuer.jwks(),now+3600),bindings=self.bindings,readers={self.reader.settings.user:self.reader})
        self.policies = {task:RecipientPolicyDescriptor(b.issuer,b.subject,b.db_role,b.location,"pol-001",1,now+3600) for task,b in self.bindings.items()}
        self.service = PrivateHandoffReader(self.store,self.policies)
        self.before = self.fingerprint()
        return self

    def settings(self, role="p2b1_test_a_reviewer"):
        return replace(self.owner.settings(role),dbname=self.dbname)

    def connect(self, role="postgres"):
        return self.owner.connect(role,dbname=self.dbname)

    def fingerprint(self):
        with self.connect() as c:
            return fingerprint(c)

    def login(self, case="404", *, changes=None):
        key, nonce, csrf = self.store.challenge("task-"+case)
        now = int(time.time())
        fields={"iat":now,"nbf":now,"exp":now+90,"nonce":nonce,**(changes or {})}
        token=self.issuer.token(fields)
        self.secrets.append(token)
        sid = self.store.login(key,token,csrf)
        self.secrets.append(sid)
        self.last_login=(key,token,csrf)
        return sid

    def stop(self):
        if hasattr(self,"before"):
            after=self.fingerprint()
            summary={"case_id":self.case_id,"before":self.before,"after":after,
                     "sqlstates":[e for e in self.events if e.get("sqlstate")],
                     "events":{name:sum(e["event"]==name for e in self.events) for name in sorted({e["event"] for e in self.events})},
                     "observation":getattr(self,"observation",{})}
            (self.private / "observations.json").write_text(json.dumps(summary,sort_keys=True),encoding="utf-8")
        (self.private / "scan-secrets.json").write_text(json.dumps([self.state["admin_password"],*self.state["runtime_passwords"].values(),*self.secrets]),encoding="utf-8")
        with self.owner.connect(dbname="postgres") as c:
            c.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(self.dbname)))
            assert not c.execute("SELECT 1 FROM pg_database WHERE datname=%s",(self.dbname,)).fetchone()
        (self.private / "cleanup.json").write_text(json.dumps({"database_dropped":True}),encoding="utf-8")


@contextmanager
def no_egress():
    """Observe and reject Python network attempts, without replacing real SQL."""
    import contextvars
    import sys
    active=contextvars.ContextVar("b6_no_egress",default=None)
    attempts=[]

    def audit(event,args):
        if active.get() is not None and event in {"socket.connect","socket.getaddrinfo","socket.sendto"}:
            # Product has no Python network client at all; libpq is separately
            # restricted by accepted ReviewerSettings to exact loopback PG16.
            attempts.append(event)
            raise RuntimeError("B6_EXTERNAL_NETWORK_DENIED")

    sys.addaudithook(audit)
    token=active.set(True)
    try:
        yield attempts
    finally:
        active.reset(token)
