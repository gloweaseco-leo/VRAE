"""Executed only after an actual docker restart by integration/l2_ops/verify.py."""
import os

import pytest

from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.ledger import BriefLedger


def test_real_pg_restart_current_read_and_role_limits(bundle, reader):
    dsn = os.environ.get("L2OPS_RUNTIME_DSN")
    if not dsn:
        pytest.skip("requires explicit post-restart runtime connection")
    import psycopg
    def connect():
        return psycopg.connect(dsn)
    service = BriefService(reader)
    expected = service.prepare(bundle, brief_ref="restart-readback")
    assert service.load_current(BriefLedger(connect), "restart-readback") == expected
    with connect() as c:
        assert c.execute("SELECT current_user").fetchone()[0] == "l2_ops_runtime"
        assert c.execute("SELECT has_table_privilege(current_user,'l2_ops_v1.briefs','UPDATE')").fetchone()[0] is False
        assert c.execute("SELECT has_table_privilege(current_user,'l2_ops_v1.briefs','DELETE')").fetchone()[0] is False
