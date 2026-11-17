"""Append-only internal brief bytes in a dedicated PG namespace.

Install with an admin connection in a controlled bootstrap. Runtime identity gets
SELECT/INSERT only; no old table, role, policy or report is changed. The ledger is
not an authorization port: BriefService rechecks the live upstream reader.
"""

from datetime import UTC, datetime

from vrae.reviewing.canonical import canonical, parse, sha

from .briefs import validate_document
from .sources import OperationsDenied, text

SCHEMA = "l2_ops_v1"


def install(admin, runtime_role):
    text(runtime_role, limit=63)
    if runtime_role != "l2_ops_runtime":
        raise OperationsDenied("L2_DEDICATED_RUNTIME_ROLE_REQUIRED")
    from psycopg import sql

    admin.execute("CREATE SCHEMA l2_ops_v1")
    admin.execute("REVOKE ALL ON SCHEMA l2_ops_v1 FROM PUBLIC")
    admin.execute("""CREATE TABLE l2_ops_v1.briefs (
        tenant_id text NOT NULL, brief_ref text NOT NULL,
        content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
        document bytea NOT NULL CHECK (octet_length(document) BETWEEN 1 AND 2000000),
        authorization_expires_at timestamptz NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY (tenant_id, brief_ref))""")
    admin.execute("""CREATE TABLE l2_ops_v1.brief_completions (
        tenant_id text NOT NULL, brief_ref text NOT NULL, content_sha256 text NOT NULL,
        completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(tenant_id,brief_ref,content_sha256),
        FOREIGN KEY(tenant_id,brief_ref) REFERENCES l2_ops_v1.briefs(tenant_id,brief_ref))""")
    admin.execute("""CREATE FUNCTION l2_ops_v1.check_commit_deadline() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF clock_timestamp() >= NEW.authorization_expires_at THEN
            RAISE EXCEPTION 'L2_AUTHORIZATION_EXPIRED' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$""")
    admin.execute("""CREATE CONSTRAINT TRIGGER l2_ops_commit_deadline AFTER INSERT ON l2_ops_v1.briefs
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION l2_ops_v1.check_commit_deadline()""")
    admin.execute("REVOKE ALL ON l2_ops_v1.briefs FROM PUBLIC")
    admin.execute(sql.SQL("GRANT USAGE ON SCHEMA l2_ops_v1 TO {}").format(sql.Identifier(runtime_role)))
    admin.execute(sql.SQL("GRANT SELECT, INSERT ON l2_ops_v1.briefs, l2_ops_v1.brief_completions TO {}").format(sql.Identifier(runtime_role)))


class BriefLedger:
    def __init__(self, connect):
        self.connect = connect

    def put(self, document, *, authority_expires_at):
        if (type(authority_expires_at) is not datetime or authority_expires_at.tzinfo is None or
                authority_expires_at.utcoffset() is None or datetime.now(UTC) >= authority_expires_at):
            raise OperationsDenied("L2_CURRENT_AUTHORITY_EXPIRED")
        validate_document(document)
        raw = canonical(document, limit=2_000_000)
        value = parse(raw, limit=2_000_000)
        claimed = value.pop("content_sha256", None)
        if sha(canonical(value, limit=2_000_000)) != claimed:
            raise OperationsDenied("L2_BRIEF_TAMPERED")
        if value.get("contract_version") != "internal-rebuild-brief-v1" or any(
            value.get(k) is not False for k in
            ("external_delivery_allowed", "customer_approval", "l2m_execution_allowed")
        ):
            raise OperationsDenied("L2_INTERNAL_ONLY_REQUIRED")
        tenant, ref = value["pins"]["tenant_id"], value["brief_ref"]
        text(tenant, limit=64)
        text(ref)
        with self.connect() as c:
            c.execute("""INSERT INTO l2_ops_v1.briefs (tenant_id, brief_ref, content_sha256, document, authorization_expires_at)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT (tenant_id, brief_ref) DO NOTHING""",
                      (tenant, ref, claimed, raw, authority_expires_at))
            row = c.execute("SELECT b.document,EXISTS(SELECT 1 FROM l2_ops_v1.brief_completions f WHERE "
                            "(f.tenant_id,f.brief_ref,f.content_sha256)=(b.tenant_id,b.brief_ref,b.content_sha256)) "
                            "FROM l2_ops_v1.briefs b WHERE b.tenant_id=%s AND b.brief_ref=%s", (tenant, ref)).fetchone()
            if row is None or bytes(row[0]) != raw:
                raise OperationsDenied("L2_IMMUTABLE_BRIEF_CONFLICT")
        return claimed

    def confirm(self, document):
        """Completion is a durable fence, NOT permission or distributed atomicity.

        Called only after both original authorization contexts exit AND a fresh
        post-commit current snapshot matches. Every read still reauthenticates.
        A failed/unknown commit stays pending and can be retried with same bytes.
        """
        validate_document(document)
        tenant, ref, digest = document["pins"]["tenant_id"], document["brief_ref"], document["content_sha256"]
        with self.connect() as c:
            row = c.execute("SELECT content_sha256 FROM l2_ops_v1.briefs WHERE tenant_id=%s AND brief_ref=%s", (tenant, ref)).fetchone()
            if row != (digest,):
                raise OperationsDenied("L2_BRIEF_COMPLETION_FENCE_MISMATCH")
            c.execute("INSERT INTO l2_ops_v1.brief_completions(tenant_id,brief_ref,content_sha256) VALUES(%s,%s,%s) "
                      "ON CONFLICT DO NOTHING", (tenant, ref, digest))

    def get(self, tenant, ref):
        text(tenant, limit=64)
        text(ref)
        with self.connect() as c:
            row = c.execute("SELECT b.document,EXISTS(SELECT 1 FROM l2_ops_v1.brief_completions f WHERE "
                            "(f.tenant_id,f.brief_ref,f.content_sha256)=(b.tenant_id,b.brief_ref,b.content_sha256)) "
                            "FROM l2_ops_v1.briefs b WHERE b.tenant_id=%s AND b.brief_ref=%s", (tenant, ref)).fetchone()
        if row is None:
            raise OperationsDenied("L2_BRIEF_NOT_FOUND")
        if row[1] is not True:
            raise OperationsDenied("L2_BRIEF_PENDING_REVALIDATION")
        return parse(bytes(row[0]), limit=2_000_000)
