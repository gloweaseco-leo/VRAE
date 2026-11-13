"""Narrow local TEST_ONLY private byte graph read/write adapter, no public endpoint."""

import re

from .contracts import PersistenceError
from .private_bytes import Artifact, ByteGraph, Locator, locator, verify
from vrae.reviewing.canonical import sha


class TestOnlyPrivateBytes:
    def __init__(self, connection, *, mode):
        if (
            mode != "TEST_ONLY_PRIVATE_BYTES_PG16"
            or not connection.autocommit
            or connection.info.host not in ("127.0.0.1", "localhost")
            or not re.fullmatch(r"vrae_p2a_[0-9a-f]{12}", connection.info.dbname)
        ):
            raise PersistenceError("P2A_LOCAL_TEST_SESSION_REQUIRED")
        row = connection.execute(
            "SELECT session_user,current_setting('server_version_num')::int,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb "
            "FROM pg_roles WHERE rolname=session_user"
        ).fetchone()
        if row is None or not 160000 <= row[1] < 170000 or any(row[2:]):
            raise PersistenceError("P2A_RUNTIME_ROLE_DENIED")
        self.connection = connection

    def _idle(self):
        if self.connection.info.transaction_status != 0:
            raise PersistenceError("P2A_COMMIT_BOUNDARY_REQUIRED")

    def register(self, candidate, *, provenance):
        self._idle()
        graph = verify(candidate, provenance=provenance)
        scope = locator(graph)
        with self.connection.transaction():
            result = self.connection.execute(
                "SELECT ra4a_bytes.register(%s,%s,%s,%s,%s,%s,%s)",
                (
                    scope.tenant,
                    graph.ref_id,
                    graph.target,
                    graph.manifest,
                    [a.kind for a in graph.artifacts],
                    [a.key for a in graph.artifacts],
                    [a.raw for a in graph.artifacts],
                ),
            ).fetchone()[0]
        if result != scope.target_digest:
            raise PersistenceError("P2A_TARGET_BINDING")
        return scope

    def read(self, location, *, provenance):
        self._idle()
        if type(location) is not Locator or location != locator(provenance):
            raise PersistenceError("P2A_EXACT_LOCATOR_REQUIRED")
        with self.connection.transaction():
            rows = self.connection.execute(
                "SELECT * FROM ra4a_bytes.read_graph(%s,%s,%s,%s,%s,%s)",
                (
                    location.tenant,
                    location.ref_id,
                    location.source_run,
                    location.report,
                    location.version,
                    location.target_digest,
                ),
            ).fetchall()
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
            candidate = ByteGraph(
                location.ref_id, target, tuple(artifacts), manifest, provenance.trust
            )
            # Validation and policy/assignment/version locks share the read tx.
            result = verify(candidate, provenance=provenance)
        return result
