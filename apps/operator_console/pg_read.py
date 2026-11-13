"""Explicit TEST_ONLY PG16 read-side. No writer/admin credential or fallback.

The approved read API verifies all bytes. A second native read holds its existing
tenant/version/assignment locks through rendering, then checks the same snapshot
again before any response is returned. Only SELECT/BEGIN/ROLLBACK are issued.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys

from vrae.persistence import PersistenceError
from vrae.persistence.private_bytes import Artifact, ByteGraph, assemble, locator, verify
from vrae.persistence.private_postgres import TestOnlyPrivateBytes
from vrae.reviewing.canonical import canonical, sha, SOURCE_LIMIT

from .contracts import ConsoleError, TEST_ONLY, refuse

MODE = "TEST_ONLY_PRIVATE_BYTES_PG16"
READ_SQL = "SELECT * FROM ra4a_bytes.read_graph(%s,%s,%s,%s,%s,%s)"
READ_ROLES = ("ra4a_test_a_app", "ra4a_test_b_app", "ra4a_test_unassigned")


def _schema_identity(connection):
    """Same catalog fingerprint as accepted P2A, compared to outside-held pin."""
    root=Path(__file__).resolve().parents[2]
    sql=(root/'db/migrations/0001_ra4a_test_only.sql').read_text(encoding='utf-8')
    expected={(a,b):body for a,b,body in re.findall(
        r'CREATE FUNCTION (ra4a|ra4a_private)\.(\w+)\(.*?AS \$\$(.*?)\$\$;',sql,re.S)}
    actual={(schema,name):body for schema,name,body,owner in connection.execute(
        "SELECT n.nspname,p.proname,p.prosrc,pg_get_userbyid(p.proowner) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('ra4a','ra4a_private')").fetchall()
        if owner=='ra4a_owner'}
    if not expected or any(actual.get(k)!=v for k,v in expected.items()):
        raise PersistenceError('P2A_SCHEMA_INTEGRITY')
    queries = (
        "SELECT proname,pg_get_functiondef(oid),proacl::text FROM pg_proc WHERE pronamespace='ra4a_bytes'::regnamespace ORDER BY proname",
        "SELECT relname,relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) FROM pg_class WHERE relnamespace='ra4a_bytes'::regnamespace AND relkind='r' ORDER BY relname",
        "SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace='ra4a_bytes'::regnamespace ORDER BY conname",
        "SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN (SELECT oid FROM pg_class WHERE relnamespace='ra4a_bytes'::regnamespace) ORDER BY tgrelid::regclass::text,tgname",
        "SELECT tablename,qual,with_check FROM pg_policies WHERE schemaname='ra4a_bytes' ORDER BY tablename",
        "SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee)::text END,c.relname::text,a.privilege_type FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a WHERE n.nspname='ra4a_bytes' AND c.relkind='r' ORDER BY 1,2,3",
        "SELECT c.relname,a.attname,pg_get_expr(d.adbin,d.adrelid) FROM pg_attrdef d JOIN pg_attribute a ON a.attrelid=d.adrelid AND a.attnum=d.adnum JOIN pg_class c ON c.oid=d.adrelid WHERE c.relnamespace='ra4a_bytes'::regnamespace ORDER BY c.relname,a.attname",
    )
    snapshot = [connection.execute(q).fetchall() for q in queries]
    return sha(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode())


def _deny(exc):
    if isinstance(exc, ConsoleError):
        raise exc
    if isinstance(exc, PersistenceError):
        if any(v in str(exc) for v in ("INTEGRITY", "BINDING", "PROVENANCE", "SCHEMA")):
            refuse("SOURCE_INTEGRITY")
        refuse("UNAUTHORIZED")
    if getattr(exc, "sqlstate", None) == "42501":
        refuse("UNAUTHORIZED")
    refuse("DB_UNAVAILABLE")


@dataclass(frozen=True)
class PgReadSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str = field(repr=False)

    def __post_init__(self):
        if (
            self.host != "127.0.0.1"
            or type(self.port) is not int
            or not 1 <= self.port <= 65535
            or not re.fullmatch(r"vrae_p2a_[0-9a-f]{12}", self.dbname)
            or self.user not in READ_ROLES
            or type(self.password) is not str
            or not 12 <= len(self.password) <= 256
            or any(ord(c) < 32 for c in self.password)
        ):
            raise ValueError("PG_LOCAL_RESTRICTED_PROFILE_REQUIRED")

    @classmethod
    def load(cls, path):
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            type(value) is not dict
            or set(value) != {"mode", "host", "port", "dbname", "user", "password"}
            or value["mode"] != MODE
        ):
            raise ValueError("PG_LOCAL_RESTRICTED_PROFILE_REQUIRED")
        return cls(**{k: v for k, v in value.items() if k != "mode"})

    def connect(self):
        # Optional locked driver is never imported or contacted in default mode.
        import psycopg

        return psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            autocommit=True,
            connect_timeout=3,
            options="-c statement_timeout=15000 -c lock_timeout=1500 -c idle_in_transaction_session_timeout=30000",
        )


class _Request:
    def __init__(self, repository, scope):
        self.repository, self.scope = repository, scope
        self.connection = None
        self.snapshots = {}

    def _rows(self, provenance):
        point = locator(provenance)
        return self.connection.execute(
            READ_SQL,
            (
                point.tenant,
                point.ref_id,
                point.source_run,
                point.report,
                point.version,
                point.target_digest,
            ),
        ).fetchall()

    def _snapshot(self, rows, provenance):
        if not rows:
            raise PersistenceError("P2A_PRIVATE_BYTES_ABSENT")
        target, manifest = bytes(rows[0][0]), bytes(rows[0][1])
        artifacts = []
        for t, m, kind, key, raw, digest, length in rows:
            raw = bytes(raw)
            if (
                bytes(t) != target
                or bytes(m) != manifest
                or sha(raw) != digest
                or len(raw) != length
            ):
                raise PersistenceError("P2A_SERVER_BYTES_INTEGRITY")
            artifacts.append(Artifact(kind, key, raw))
        # Keep the actual row bytes for presentation after original verification.
        candidate = ByteGraph(
            provenance.ref_id, target, tuple(artifacts), manifest, provenance.trust
        )
        verify(candidate, provenance=provenance)
        return candidate

    def load(self, case):
        if case in self.snapshots:
            return self.snapshots[case]
        provenance = self.repository._provenance[case]
        if self.connection is None:
            self.connection = self.repository.settings.connect()
            api = TestOnlyPrivateBytes(self.connection, mode=MODE)
            row = self.connection.execute(
                "SELECT session_user,current_user,pg_has_role(session_user,'p2a_fixture_writer','MEMBER'),rolcanlogin FROM pg_roles WHERE rolname=session_user"
            ).fetchone()
            if row is None or row[0] != self.repository.settings.user or row[1] != row[0] or row[2] or not row[3]:
                raise PersistenceError("P2A_RUNTIME_ROLE_DENIED")
            if _schema_identity(self.connection) != self.repository._schema_pin:
                raise PersistenceError("P2A_SCHEMA_INTEGRITY")
            # Real approved API call, with independent accepted-main provenance.
            api.read(locator(provenance), provenance=provenance)
            self.repository._event("approved_read", case=case)
            # read_graph's original locks serialize revocation/publication. The
            # first API owns its transaction, so reacquire and compare before use.
            self.connection.execute("BEGIN")
        candidate = self._snapshot(self._rows(provenance), provenance)
        self.repository._event(
            "snapshot",
            case=case,
            objects=len(candidate.artifacts),
            target_digest=locator(candidate).target_digest,
            manifest_sha256=sha(candidate.manifest),
        )
        self.snapshots[case] = candidate
        return candidate

    def finish(self):
        if self.connection is not None:
            # Policy expiration uses clock_timestamp, not an old tx timestamp.
            # Verify fresh rows at the response boundary under the existing locks.
            for case, snapshot in self.snapshots.items():
                current = self._snapshot(
                    self._rows(self.repository._provenance[case]), self.repository._provenance[case]
                )
                if current != snapshot:
                    raise PersistenceError("P2A_PRIVATE_BYTES_INTEGRITY")
                self.repository._event(
                    "response_current", case=case, objects=len(current.artifacts)
                )
            if _schema_identity(self.connection) != self.repository._schema_pin:
                raise PersistenceError("P2A_SCHEMA_INTEGRITY")

    def close(self):
        if self.connection is not None:
            try:
                self.connection.rollback()
            finally:
                self.connection.close()


class PgReadRepository:
    """Synthetic task metadata, but never in-memory report/source data on reads."""

    def __init__(
        self,
        metadata,
        settings,
        provenance,
        *,
        test_only=False,
        synthetic_fixtures=False,
        audit_sink=None,
    ):
        from .fixtures import FixtureRepository

        if (
            test_only is not True
            or synthetic_fixtures is not True
            or type(metadata) is not FixtureRepository
            or type(settings) is not PgReadSettings
            or set(provenance) != {"404", "200"}
        ):
            raise ValueError("PG_TEST_ONLY_WIRING_REQUIRED")
        self.metadata, self.settings = metadata, settings
        self._provenance = dict(provenance)
        for g in self._provenance.values():
            verify(g, provenance=g)
        self._request = ContextVar("ra4c3_request", default=None)
        self._audit_sink = audit_sink
        # Owner-accepted main's independent catalog identity, not a DB/profile row.
        root = Path(__file__).resolve().parents[2]
        scope = json.loads(
            (root / "docs/03-engineering/ra4a-p2a/SOURCE_SCOPE.json").read_text(encoding="utf-8")
        )
        self._schema_pin = scope["actual_dual_results"][0]["schema_sha256"]

    def _event(self, event, **values):
        if self._audit_sink is not None:
            # No SQL parameters, credentials, raw HTML, quotes or reasons in logs.
            self._audit_sink({"event": event, **values})

    @contextmanager
    def request(self, scope):
        if scope.source_kind != TEST_ONLY or self._request.get() is not None:
            refuse("UNAUTHORIZED")
        state = _Request(self, scope)
        token = self._request.set(state)
        try:
            yield
            state.finish()
        except ConsoleError:
            raise
        except Exception as exc:
            # Driver/DB exceptions can contain connection parameters. Never echo.
            _deny(exc)
        finally:
            pending = sys.exc_info()[0]
            try:
                state.close()
            except Exception:
                if pending is None:
                    refuse("DB_UNAVAILABLE")
            finally:
                self._request.reset(token)

    def assigned(self, scope):
        return self.metadata.assigned(scope)

    def task(self, task_id):
        return self.metadata.task(task_id)

    def report_source(self, case):
        refuse("NOT_IMPLEMENTED")  # A DB failure must never reach fixture fallback.

    def _state(self, scope, task):
        state = self._request.get()
        if (
            state is None
            or state.scope != scope
            or task["task_id"] not in scope.assigned_ids
            or task["audit_run"]["tenant_id"] != scope.tenant_id
            or task["owner_scope"] != scope.owner_scope
        ):
            refuse("UNAUTHORIZED")
        return state

    def probe(self, scope, task):
        # Called only after ConsoleService._task authorizes the exact task.
        state = self._state(scope, task)
        case = task["report_case"]
        if case is None:
            return  # No private graph belongs to a neutral/no-report task.
        try:
            state.load(case)
        except Exception as exc:
            _deny(exc)

    def dossier(self, scope, task, native):
        state = self._state(scope, task)
        case = task["report_case"]
        try:
            graph = state.load(case)
        except Exception as exc:
            _deny(exc)
        raw = {(a.kind, a.key): a.raw for a in graph.artifacts}
        dossier = native.load_original(case, raw)
        dossier["origin"] = {
            "mode": "PG16_TEST_ONLY_READ",
            "manifest_sha256": sha(graph.manifest),
            "objects": len(graph.artifacts),
            "source_sha256": sha(raw[("SOURCE", "source")]),
        }
        source = json.loads(raw[("SOURCE", "source")])
        return dossier, source


def make_pg_fixture(profile, *, test_only=False, synthetic_fixtures=False, audit_sink=None):
    if test_only is not True or synthetic_fixtures is not True:
        raise ValueError("PG_TEST_ONLY_WIRING_REQUIRED")
    from .fixtures import make_fixture

    service, context = make_fixture()
    provenance = {}
    # Independent main fixtures are held before opening any DB connection. They
    # provide verification pins only; actual page data must come from row reads.
    for case in ("404", "200"):
        source = service.repository.report_source(case)
        d = service.native.prepare(case, source)
        a = d["_artifacts"]
        provenance[case] = assemble(
            "accepted-" + case,
            a["document"],
            a["html"],
            canonical(source, limit=SOURCE_LIMIT),
            trust=service.targets._trust(case),
        )
    service.repository = PgReadRepository(
        service.repository,
        PgReadSettings.load(profile),
        provenance,
        test_only=True,
        synthetic_fixtures=True,
        audit_sink=audit_sink,
    )
    return service, context
