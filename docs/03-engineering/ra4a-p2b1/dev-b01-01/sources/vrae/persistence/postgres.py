"""Optional real PG adapter. Synthetic local sessions only; no default DSN."""

from .contracts import PersistenceError, admission_payload


class TestOnlyPostgres:
    def __init__(self, connection, *, mode):
        if mode != "TEST_ONLY_PG16" or not connection.autocommit:
            raise PersistenceError("RA4A_TEST_ONLY_AUTOCOMMIT_REQUIRED")
        if (
            connection.info.host not in ("127.0.0.1", "localhost")
            or connection.info.dbname != "vrae_ra4a_p1"
        ):
            raise PersistenceError("RA4A_LOCAL_DATABASE_REQUIRED")
        row = connection.execute(
            "SELECT session_user,current_database(),current_setting('server_version_num')::int, "
            "rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_catalog.pg_roles WHERE rolname=session_user"
        ).fetchone()
        if (
            row is None
            or not row[0].startswith("ra4a_test_")
            or not 160000 <= row[2] < 170000
            or any(row[3:])
        ):
            raise PersistenceError("RA4A_RUNTIME_ROLE_DENIED")
        self.connection = connection

    def admit(
        self,
        tenant,
        key,
        *,
        policy_id="pol-001",
        policy_version=1,
        source_ref=None,
        expected_ref_sha256=None,
    ):
        if type(policy_version) is not int or policy_version < 1:
            raise PersistenceError("RA4A_POLICY_VERSION_INVALID")
        raw, digest = admission_payload(source_ref, expected_ref_sha256)
        with self.connection.transaction():
            row = self.connection.execute(
                "SELECT * FROM ra4a.admit(%s,%s,%s,%s,%s,%s)",
                (tenant, policy_id, policy_version, key, digest, raw),
            ).fetchone()
        # Returned only after PG commit; not HTTP 202 or a production authority.
        return row

    def claim(self, tenant, *, seconds=5):
        if type(seconds) is not int:
            raise PersistenceError("RA4A_LEASE_BOUNDS")
        with self.connection.transaction():
            return self.connection.execute(
                "SELECT * FROM ra4a.claim(%s,%s)", (tenant, seconds)
            ).fetchone()

    def finish(self, tenant, job_id, token, seq):
        with self.connection.transaction():
            return self.connection.execute(
                "SELECT ra4a.finish(%s,%s,%s,%s)", (tenant, job_id, token, seq)
            ).fetchone()[0]
