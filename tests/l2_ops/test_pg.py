"""Real PG16 sidecar tests; synthetic upstream DTOs are explicitly not L2 E2E."""
import os
import secrets
from pathlib import Path

import pytest

from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.ledger import BriefLedger, install
from vrae.l2_ops.sources import OperationsDenied
from vrae.reviewing.canonical import canonical, sha


@pytest.fixture(scope="module")
def database():
    dsn = os.environ.get("L2OPS_TEST_DSN")
    if not dsn:
        pytest.skip("L2OPS_TEST_DSN: isolated PG16 required")
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    password = secrets.token_urlsafe(32)
    with psycopg.connect(dsn) as c:
        assert 160000 <= c.info.server_version < 170000
        c.execute(sql.SQL("CREATE ROLE l2_ops_runtime LOGIN PASSWORD {}").format(sql.Literal(password)))
        install(c, "l2_ops_runtime")
    runtime = make_conninfo(dsn, user="l2_ops_runtime", password=password)
    output = os.environ.get("L2OPS_RUNTIME_OUTPUT")
    if output:
        Path(output).write_text(runtime, encoding="utf-8")
    return lambda: psycopg.connect(runtime)


def test_pg_append_only_replay_conflict_and_current_lock(database, bundle, reader):
    service = BriefService(reader)
    ledger = BriefLedger(database)
    document = service.prepare(bundle, brief_ref="pg-brief")
    assert service.save_current(ledger, document) == document["content_sha256"]
    assert service.save_current(ledger, document) == document["content_sha256"]
    assert service.load_current(ledger, "pg-brief") == document
    altered = {**document, "consultation": {**document["consultation"], "reference": "another", "state": "UNVERIFIED_REFERENCE"}}
    altered["content_sha256"] = sha(canonical({k: v for k, v in altered.items() if k != "content_sha256"}, limit=2_000_000))
    with pytest.raises(OperationsDenied, match="IMMUTABLE_BRIEF_CONFLICT"):
        service.save_current(ledger, altered)
    assert ledger.get(bundle.tenant_id, "pg-brief") == document
    with pytest.raises(OperationsDenied, match="NOT_FOUND"):
        ledger.get("another-tenant", "pg-brief")

    class LockObservingLedger:
        def put(self, value):
            assert reader.locked
            return ledger.put(value)

    service.save_current(LockObservingLedger(), document)
    reader.allowed = False
    with pytest.raises(OperationsDenied, match="REVOKED"):
        service.load_current(ledger, "pg-brief")


def test_pg_runtime_cannot_update_delete_or_bootstrap(database):
    import psycopg
    for query in ("UPDATE l2_ops_v1.briefs SET brief_ref='changed'",
                  "DELETE FROM l2_ops_v1.briefs", "DROP TABLE l2_ops_v1.briefs",
                  "CREATE TABLE l2_ops_v1.unauthorized(x int)"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), database() as c:
            c.execute(query)


def test_pg_restart_marker(database, bundle, reader):
    service = BriefService(reader)
    ledger = BriefLedger(database)
    original = service.prepare(bundle, brief_ref="restart-readback")
    service.save_current(ledger, original)
    assert service.load_current(ledger, "restart-readback") == original


def test_pg_real_deferred_commit_failure_returns_no_receipt(database, bundle, reader):
    import psycopg
    with psycopg.connect(os.environ["L2OPS_TEST_DSN"]) as c:
        c.execute("""CREATE FUNCTION l2_ops_v1.test_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.brief_ref = 'commit-must-fail' THEN RAISE EXCEPTION 'test deferred failure' USING ERRCODE='23514'; END IF;
            RETURN NEW; END $$""")
        c.execute("""CREATE CONSTRAINT TRIGGER test_commit_failure AFTER INSERT ON l2_ops_v1.briefs
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION l2_ops_v1.test_commit_failure()""")
    service = BriefService(reader)
    ledger = BriefLedger(database)
    document = service.prepare(bundle, brief_ref="commit-must-fail")
    with pytest.raises(psycopg.errors.CheckViolation, match="test deferred failure"):
        service.save_current(ledger, document)
    with pytest.raises(OperationsDenied, match="NOT_FOUND"):
        ledger.get(bundle.tenant_id, "commit-must-fail")
