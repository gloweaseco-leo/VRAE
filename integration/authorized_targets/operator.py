"""Offline trusted-admin target activation/revocation; no browser admin API."""

from psycopg.types.json import Jsonb
from integration.authorized_targets.source_authority import authorization, AuthorityDenied


def activate(connection, envelope):
    if connection.execute("SELECT session_user").fetchone() != ("postgres",):
        raise AuthorityDenied()
    d = envelope["document"]
    t, target = d["tenant_id"], d["target_id"]
    with connection.transaction():
        row = connection.execute(
            "SELECT document,encode(sha256(convert_to(document::text,'UTF8')),'hex') FROM target_v1.plans WHERE tenant_id=%s AND target_id=%s AND NOT revoked FOR SHARE",
            (t, target),
        ).fetchone()
        if row is None:
            raise AuthorityDenied()
        authorization(envelope, row[0], plan_sha256=row[1])
        connection.execute(
            "INSERT INTO target_v1.authorizations VALUES(%s,%s,%s,%s,%s,%s,%s,%s,false)",
            (
                t,
                target,
                d["reference"],
                row[1],
                Jsonb(envelope),
                d["not_before"],
                d["expires_at"],
                d["retention_until"],
            ),
        )


def revoke(connection, tenant, target):
    if connection.execute("SELECT session_user").fetchone() != ("postgres",):
        raise AuthorityDenied()
    with connection.transaction():
        connection.execute(
            "UPDATE target_v1.authorizations SET revoked=true WHERE tenant_id=%s AND target_id=%s",
            (tenant, target),
        )
        connection.execute(
            "INSERT INTO target_v1.capture_audit(tenant_id,job_id,phase,safe_code,authorization_ref,retention_until) SELECT b.tenant_id,j.job_id,'AUTHORIZATION_REVOKED','SOURCE_AUTHORITY_DENIED',a.reference,a.retention_until FROM target_v1.bindings b JOIN ra4a.runs r USING(tenant_id,request_id) JOIN ra4a.jobs j USING(tenant_id,run_id) JOIN target_v1.authorizations a USING(tenant_id,target_id) WHERE b.tenant_id=%s AND b.target_id=%s",
            (tenant, target),
        )
