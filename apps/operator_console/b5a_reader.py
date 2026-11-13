"""Actual P2B1 Reviewer read -> accepted immutable NativePreparation.

No APP credential, raw table read, SET ROLE, draft regeneration or fixture fallback.
Provisioning supplies descriptor pins separately; every displayed byte is returned
by the accepted load_target function under an authenticated Reviewer connection.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import re

from vrae.persistence.private_bytes import Locator
from vrae.reviewing.canonical import canonical, sha

from .contracts import ConsoleError, refuse
from .native import NativeVerifier
from .targets import ReviewTargetBridge

READ_SQL = "SELECT * FROM ra4a_review_test.load_target(%s,%s,%s,%s,%s,%s)"
REVIEWERS = ("p2b1_test_a_reviewer", "p2b1_test_a_peer", "p2b1_test_b_reviewer")


@dataclass(frozen=True)
class ReviewerSettings:
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
            or self.user not in REVIEWERS
            or not re.fullmatch(r"vrae_p2b1_[0-9a-f]{12}", self.dbname)
            or type(self.password) is not str
            or not 12 <= len(self.password) <= 256
        ):
            raise ValueError("B5A_REVIEWER_PROFILE_REQUIRED")

    def connect(self, audit=None):
        import psycopg

        class ObservedCursor(psycopg.Cursor):
            def execute(self, query, params=None, **kwargs):
                self.is_target = query == READ_SQL
                try:
                    return super().execute(query, params, **kwargs)
                except psycopg.Error as exc:
                    if audit and exc.sqlstate == "42501":
                        audit("actual_sql_denial", sqlstate="42501")
                    raise

            def fetchall(self):
                rows = super().fetchall()
                if self.is_target and rows and audit:
                    audit("actual_load_target_returned", objects=len(rows))
                return rows

        return psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            autocommit=True,
            connect_timeout=3,
            cursor_factory=ObservedCursor,
            options="-c statement_timeout=15000 -c lock_timeout=1500 -c idle_in_transaction_session_timeout=30000",
        )


@dataclass(frozen=True)
class OriginalPins:
    case: str
    location: Locator
    target_sha256: str
    manifest_sha256: str
    descriptors: tuple


def catalog_digest(c):
    """Read-only catalog fingerprint, generated out of band using the same role."""
    queries = (
        "SELECT n.nspname,p.proname,pg_get_functiondef(p.oid),pg_get_userbyid(p.proowner),p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test') ORDER BY 1,2,3",
        "SELECT n.nspname,t.relname,t.relrowsecurity,t.relforcerowsecurity,pg_get_userbyid(t.relowner),t.relacl::text FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test') AND t.relkind='r' ORDER BY 1,2",
        "SELECT schemaname,tablename,policyname,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test') ORDER BY 1,2,3",
        "SELECT r.rolname,m.rolname,a.admin_option,a.inherit_option,a.set_option FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.roleid JOIN pg_roles m ON m.oid=a.member WHERE r.rolname LIKE 'ra4a_%' OR r.rolname LIKE 'p2a_%' OR r.rolname LIKE 'p2b1_%' ORDER BY 1,2",
    )
    return sha(
        json.dumps(
            [c.execute(q).fetchall() for q in queries],
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    )


def current_reviewer(c, role):
    row = c.execute(
        "SELECT session_user,current_user,current_setting('server_version_num')::int,"
        "rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,"
        "pg_has_role(session_user,'p2b1_review','MEMBER') FROM pg_roles WHERE rolname=session_user"
    ).fetchone()
    if (
        not row
        or row[:2] != (role, role)
        or not 160000 <= row[2] < 170000
        or not row[3]
        or any(row[4:8])
        or not row[8]
    ):
        refuse("UNAUTHORIZED")
    return row


class ReviewerReader:
    def __init__(self, settings, pins, tasks, schema_pin, *, audit=None):
        if type(settings) is not ReviewerSettings or not re.fullmatch(r"[0-9a-f]{64}", schema_pin):
            raise ValueError("B5A_TRUSTED_PROVISIONING_REQUIRED")
        self.settings, self.pins, self.tasks = settings, dict(pins), dict(tasks)
        self.schema_pin, self.audit = schema_pin, audit
        self.native, self.targets = NativeVerifier(), ReviewTargetBridge()

    def event(self, name, **safe):
        if self.audit:
            self.audit({"event": name, **safe})

    def connect(self):
        return self.settings.connect(audit=self.event)

    def _load(self, c, pin):
        p = pin.location
        self.event("reviewer_load_attempt")
        rows = c.execute(
            READ_SQL, (p.tenant, p.ref_id, p.source_run, p.report, p.version, p.target_digest)
        ).fetchall()
        if not rows or len(rows) > 137:
            refuse("SOURCE_INTEGRITY")
        self.event("reviewer_original_rows_returned", objects=len(rows))
        target, manifest = bytes(rows[0][0]), bytes(rows[0][1])
        if sha(target) != pin.target_sha256 or sha(manifest) != pin.manifest_sha256:
            refuse("SOURCE_INTEGRITY")
        raw, descriptors = {}, []
        total = 0
        for t, m, kind, key, body, digest, length in rows:
            value = bytes(body)
            total += len(value)
            if (
                bytes(t) != target
                or bytes(m) != manifest
                or sha(value) != digest
                or len(value) != length
                or (kind, key) in raw
                or total > 64_000_000
            ):
                refuse("SOURCE_INTEGRITY")
            raw[(kind, key)] = value
            descriptors.append({"key": key, "kind": kind, "length": length, "sha256": digest})
        descriptors.sort(key=lambda d: (d["kind"], d["key"]))
        if (
            canonical(descriptors) != manifest
            or canonical(descriptors) != canonical(list(pin.descriptors))
            or raw.get(("TARGET", "target")) != target
        ):
            refuse("SOURCE_INTEGRITY")
        # This public accepted API loads the DB-original DRAFT/HTML/SOURCE. It
        # never calls NativeVerifier.prepare/build_draft for presentation.
        dossier = self.native.load_original(pin.case, raw)
        source = json.loads(raw[("SOURCE", "source")])
        task = self.tasks[pin.case]
        projection = self.targets.prepare(
            task, raw[("DRAFT", "draft")], raw[("HTML", "html")], raw[("SOURCE", "source")]
        ).document
        if (
            projection["target_digest"] != p.target_digest
            or canonical(projection["target"]) != target
        ):
            refuse("SOURCE_INTEGRITY")
        dossier["review_target"] = projection
        dossier["origin"] = {
            "mode": "PG16_TEST_ONLY_REVIEWER_READ",
            "manifest_sha256": sha(manifest),
            "source_sha256": sha(raw[("SOURCE", "source")]),
            "objects": len(raw),
        }
        self.event(
            "native_original_verified",
            case=pin.case,
            objects=len(raw),
            source_sha256=sha(raw[("SOURCE", "source")]),
            target_digest=p.target_digest,
        )
        return {
            "pin": pin,
            "dossier": dossier,
            "source": source,
            "fingerprint": sha(target + manifest),
            "raw": raw,
        }

    @contextmanager
    def request(self, binding, *, recheck=lambda: None):
        if binding.db_role != self.settings.user or binding.location not in self.pins:
            refuse("UNAUTHORIZED")
        c = None
        try:
            recheck()
            c = self.connect()
            role = current_reviewer(c, binding.db_role)
            if catalog_digest(c) != self.schema_pin:
                refuse("SOURCE_INTEGRITY")
            self.event(
                "actual_reviewer_identity",
                role=role[0],
                server_version=role[2],
                superuser=False,
                bypassrls=False,
            )
            with c.transaction():
                original = self._load(c, self.pins[binding.location])
                yield original
                recheck()
                current_reviewer(c, binding.db_role)
                current = self._load(c, self.pins[binding.location])
                if (
                    current["raw"] != original["raw"]
                    or current["fingerprint"] != original["fingerprint"]
                ):
                    refuse("SOURCE_INTEGRITY")
                if catalog_digest(c) != self.schema_pin:
                    refuse("SOURCE_INTEGRITY")
                self.event("response_current")
        except ConsoleError:
            raise
        except Exception as exc:
            code = getattr(exc, "sqlstate", None)
            self.event("read_denied", sqlstate=code if code in ("42501", "55000") else None)
            refuse("UNAUTHORIZED" if code == "42501" else "DB_UNAVAILABLE")
        finally:
            if c is not None:
                c.close()
