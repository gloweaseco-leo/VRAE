"""Private disposable fixture provisioning, independent of all runtime authority."""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import uuid

from psycopg import sql

from vrae.b3_p0.contracts import Command, MODE, Witness
from vrae.b3_p0.service import IntentService, args
from vrae.persistence.private_bytes import locator
from integration.ra4a.p2b1_support import proposal

ROOT = Path(__file__).resolve().parents[2]
TABLES = (
    "authority",
    "witnesses",
    "states",
    "intents",
    "claims",
    "sections",
    "audit",
    "outbox",
    "bootstrap",
)
BUSINESS = ("states", "intents", "claims", "sections", "audit", "outbox")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def bootstrap(lab):
    raw = (ROOT / "db/b3_p0/testonly_schema.sql").read_bytes().replace(b"\r\n", b"\n")
    with lab.connect() as c, c.transaction():
        before = protected(c)
        c.execute(raw.decode("utf-8-sig"))
        c.execute("INSERT INTO b3_p0.bootstrap VALUES(%s)", (sha(raw),))
        c.execute(
            "INSERT INTO b3_p0.authority VALUES('tenant-test',1,true,clock_timestamp()+interval '1 day')"
        )
        assert protected(c) == before, "B3_CHANGED_ACCEPTED_SCHEMA_OR_BYTES"
        from .lab import wire

        with wire(lab.state_path) as (_, _, accepted):
            accepted.verify_migrations(c)


def protected(c):
    queries = [
        "SELECT version,sha256 FROM ra4a_private.migrations ORDER BY version",
        "SELECT n.nspname,p.proname,pg_get_functiondef(p.oid),p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname LIKE 'ra4a%' ORDER BY 1,2,3",
        "SELECT n.nspname,c.relname,c.relacl::text,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname LIKE 'ra4a%' AND c.relkind IN ('r','S') ORDER BY 1,2",
        "SELECT nspname,nspacl::text FROM pg_namespace WHERE nspname LIKE 'ra4a%' OR nspname='public' ORDER BY 1",
        "SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolinherit FROM pg_roles ORDER BY 1",
        "SELECT pg_get_userbyid(roleid),pg_get_userbyid(member),admin_option,inherit_option,set_option FROM pg_auth_members ORDER BY 1,2",
        "SELECT kind,object_key,content_sha256,octet_length(raw),encode(sha256(raw),'hex') FROM ra4a_bytes.objects ORDER BY kind,object_key",
    ]
    return sha(encode([c.execute(q).fetchall() for q in queries]))


def snapshot(c, *, schema=False, details=False):
    rows = {
        t: c.execute(
            sql.SQL(
                "SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]'::jsonb) FROM b3_p0.{} x"
            ).format(sql.Identifier(t))
        ).fetchone()[0]
        for t in TABLES
    }
    if schema:
        from integration.ra4e.security import table_acl_entries, independent_planes

        rows["functions"] = c.execute(
            "SELECT proname,pg_get_functiondef(oid),proacl::text FROM pg_proc WHERE pronamespace='b3_p0'::regnamespace ORDER BY 1"
        ).fetchall()
        rows["tables"] = [
            (name, owner, table_acl_entries(c, raw, owner), rls, force)
            for name, owner, raw, rls, force in c.execute(
                "SELECT relname,pg_get_userbyid(relowner),relacl::text,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace='b3_p0'::regnamespace AND relkind='r' ORDER BY 1"
            ).fetchall()
        ]
        rows["default_acls"] = independent_planes(c)["default_acls"]
        rows["schema_acl"] = c.execute(
            "SELECT nspname,pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace WHERE nspname='b3_p0'"
        ).fetchall()
        rows["column_acls"] = c.execute(
            "SELECT t.relname,a.attname,a.attacl::text FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid WHERE t.relnamespace='b3_p0'::regnamespace AND t.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,a.attnum"
        ).fetchall()
        rows["effective_table_privileges"] = c.execute(
            "SELECT r.rolname,t.relname,p,has_table_privilege(r.oid,t.oid,p) FROM pg_roles r CROSS JOIN pg_class t CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p WHERE t.relnamespace='b3_p0'::regnamespace AND t.relkind='r' AND (r.rolname LIKE 'ra4a_%' OR r.rolname LIKE 'p2%') ORDER BY 1,2,3"
        ).fetchall()
        rows["constraints"] = c.execute(
            "SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='b3_p0'::regnamespace ORDER BY 1,2"
        ).fetchall()
        rows["triggers"] = c.execute(
            "SELECT tgrelid::regclass::text,tgname,pg_get_triggerdef(oid) FROM pg_trigger WHERE tgrelid IN (SELECT oid FROM pg_class WHERE relnamespace='b3_p0'::regnamespace) AND NOT tgisinternal ORDER BY 1,2"
        ).fetchall()
        rows["policies"] = c.execute(
            "SELECT tablename,qual,with_check FROM pg_policies WHERE schemaname='b3_p0' ORDER BY 1"
        ).fetchall()
    return rows if details else sha(encode(rows))


def counts(c):
    return {
        t: c.execute(sql.SQL("SELECT count(*) FROM b3_p0.{}").format(sql.Identifier(t))).fetchone()[
            0
        ]
        for t in BUSINESS
    }


class Case:
    def __init__(self, lab, dbname, admin):
        self.lab, self.dbname, self.admin = lab, dbname, admin
        self.graphs = lab.graphs

    def connect(self, role="p2b1_test_a_reviewer"):
        return self.lab.connect(role, self.dbname)

    def witness(
        self,
        case="404",
        *,
        role="p2b1_test_a_reviewer",
        subject="TEST_ONLY_reviewer",
        ttl=120,
        epoch=1,
        graph=None,
    ):
        loc = locator(graph or self.graphs[case])
        token = uuid.uuid4()
        self.admin.execute(
            "INSERT INTO b3_p0.witnesses VALUES(%s,%s,%s,%s,%s,clock_timestamp()+(%s*interval '1 second'),%s,%s,%s,%s,%s)",
            (
                loc.tenant,
                token,
                role,
                subject,
                epoch,
                ttl,
                loc.ref_id,
                loc.source_run,
                loc.report,
                loc.version,
                loc.target_digest,
            ),
        )
        return Witness(token, loc)

    @contextmanager
    def service(self, witness, *, role="p2b1_test_a_reviewer", graph=None):
        g = graph or next(g for g in self.graphs.values() if locator(g) == witness.location)
        with self.connect(role) as c:
            yield IntentService(c, g, mode=MODE)

    def submit(self, witness=None, command=None, *, role="p2b1_test_a_reviewer", graph=None):
        w = witness or self.witness()
        g = graph or next(g for g in self.graphs.values() if locator(g) == w.location)
        cmd = command or Command(proposal(g).payload)
        with self.service(w, role=role, graph=g) as api:
            return api.submit(w, cmd)

    def raw(self, c, w, cmd=None):
        g = next((g for g in self.graphs.values() if locator(g) == w.location), self.graphs["404"])
        return bytes(
            c.execute(
                "SELECT b3_p0.submit_test(%s,%s,%s,%s,%s,%s,%s,%s)",
                (w.token, *args(w.location), (cmd or Command(proposal(g).payload)).payload),
            ).fetchone()[0]
        )
