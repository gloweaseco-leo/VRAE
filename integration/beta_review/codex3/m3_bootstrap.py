"""Install only Owner-accepted M1 SQL and authorized recorded synthetic inputs."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from tests.collection.test_security import fixture
from tests.reviewing.synthetic import inputs


def install(lab):
    sql = Path(__file__).resolve().parents[3] / "db/ra4b_p2/m1/001_runtime.sql"
    with lab.connect(dbname="vrae_ra4a_p1") as c:
        assert c.execute("SELECT to_regnamespace('ra4b_p2')").fetchone() == (None,)
        c.execute(sql.read_text(encoding="utf-8"))
        for case in ("404", "200"):
            raw = inputs(case).source
            ref = c.execute(
                "SELECT tenant_id,policy_id,policy_version,ref_sha256,metadata FROM ra4a.references WHERE ref_id=%s",
                ("accepted-" + case,),
            ).fetchone()
            assert hashlib.sha256(raw).hexdigest() == ref[4]["source_record_sha256"]
            audit, policy = fixture("AuditRequest"), fixture("SourcePolicy")
            audit.update(tenant_id=ref[0], source_policy_ref=ref[1], source_policy_version=ref[2])
            expiry = c.execute(
                "SELECT expires_at FROM ra4a.policies WHERE(tenant_id,policy_id,version)=(%s,%s,%s)",
                ref[:3],
            ).fetchone()[0]
            policy.update(
                tenant_id=ref[0],
                policy_id=ref[1],
                policy_version=ref[2],
                permitted_hosts=["example.org"],
                scope_paths=["/"],
                expires_at=expiry.isoformat(),
                revoked_at=None,
            )
            c.execute(
                "INSERT INTO ra4b_p2.m1_inputs(tenant_id,source_ref,reference_sha256,source_record,policy_document,audit_document,reviewer_role) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    ref[0],
                    "accepted-" + case,
                    ref[3],
                    raw,
                    Jsonb(policy),
                    Jsonb(audit),
                    "p2b1_test_a_reviewer",
                ),
            )
        assert c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (0,)
    return {
        "sql_sha256": hashlib.sha256(sql.read_bytes()).hexdigest(),
        "sources": ["accepted-404", "accepted-200"],
        "seeded_results": 0,
        "legacy_migrations_changed": False,
    }
