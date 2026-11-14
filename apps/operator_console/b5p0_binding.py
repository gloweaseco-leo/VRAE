"""Server-provisioned synthetic B2 -> B3 mapping; no browser authority inputs."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from uuid import UUID

from vrae.b3_p0.contracts import MODE, Denied, Witness
from vrae.persistence.private_bytes import Artifact, ByteGraph
from vrae.reviewing import SyntheticTrust
from vrae.reviewing.canonical import canonical, sha

from .b5a_reader import ReviewerSettings
from .contracts import refuse


def mapping_subject(issuer, subject, role, location):
    return "TEST_ONLY_" + sha(canonical([issuer, subject, role, asdict(location)]))


@dataclass(frozen=True)
class Binding:
    issuer: str
    subject: str = field(repr=False)
    role: str
    witness: Witness = field(repr=False)
    b3_subject: str

    def __post_init__(self):
        if (
            type(self.witness) is not Witness
            or type(self.witness.token) is not UUID
            or self.b3_subject
            != mapping_subject(self.issuer, self.subject, self.role, self.witness.location)
        ):
            raise ValueError("B5P0_TRUSTED_BINDING_REQUIRED")

    @property
    def scope(self):
        return sha(canonical([self.b3_subject, asdict(self.witness.location)]))


def original_graph(snapshot):
    """All artifact bytes are the actual B5A SQL snapshot, not fixture regeneration."""
    pin = snapshot["pin"]
    row = json.loads(
        Path(__file__).with_name("review-target-pins.json").read_text(encoding="utf-8")
    )
    held = row["cases"][pin.case]
    trust = SyntheticTrust(
        row["authority"], canonical(held["held"]), canonical(held["policy"]), held["artifact_ref"]
    )
    artifacts = tuple(Artifact(k, key, raw) for (k, key), raw in sorted(snapshot["raw"].items()))
    # B5A proved this exact canonical descriptor byte sequence equals actual SQL
    # manifest_raw. Reconstructing it does not supply new trust or replace bytes.
    manifest = canonical(list(pin.descriptors))
    if sha(manifest) != pin.manifest_sha256:
        refuse("SOURCE_INTEGRITY")
    return ByteGraph(
        pin.location.ref_id, snapshot["raw"][("TARGET", "target")], artifacts, manifest, trust
    )


@contextmanager
def intent_port(settings, graph, current, audit, binding):
    """A real psycopg Connection subclass, never SET ROLE/admin/fake SQL results."""
    import psycopg
    from vrae.b3_p0.service import IntentService

    if type(settings) is not ReviewerSettings:
        refuse("UNAUTHORIZED")
    states = []

    class Cursor(psycopg.Cursor):
        def execute(self, query, params=None, **kwargs):
            self.b3_result = isinstance(query, str) and query.startswith(
                ("SELECT b3_p0.submit_test(", "SELECT b3_p0.get_receipt(")
            )
            try:
                return super().execute(query, params, **kwargs)
            except psycopg.Error as exc:
                states.append(exc.sqlstate)
                if exc.sqlstate in ("42501", "P0002", "40001", "23505"):
                    audit("sql_state", sqlstate=exc.sqlstate)
                raise

        def fetchone(self):
            row = super().fetchone()
            if self.b3_result and row is not None:
                from vrae.b3_p0.contracts import Receipt

                d = Receipt(bytes(row[0])).document
                if (
                    d["subject"] != binding.b3_subject
                    or d["db_actor"] != binding.role
                    or d["target_digest"] != binding.witness.location.target_digest
                ):
                    raise Denied("B5P0_CANDIDATE_IDENTITY_MISMATCH")
                audit("b3_candidate_binding_verified", mapping=binding.scope)
            return row

    class Connection(psycopg.Connection):
        @contextmanager
        def transaction(self, *args, **kwargs):
            with super().transaction(*args, **kwargs) as tx:
                yield tx
                # Runs inside the actual transaction immediately before the
                # driver's COMMIT; failures cause actual rollback, not a claim.
                audit("commit_entry")
                current()

    current()
    with Connection.connect(
        host=settings.host,
        port=settings.port,
        dbname=settings.dbname,
        user=settings.user,
        password=settings.password,
        autocommit=True,
        connect_timeout=3,
        cursor_factory=Cursor,
        options="-c statement_timeout=15000 -c lock_timeout=1500",
    ) as c:
        service = IntentService(c, graph, mode=MODE)
        yield service, states
    current()


def probe(settings, graph, binding, current, audit, probe_key):
    """Only P0002 from the real authenticated B3 lookup proves a fresh witness.

    IntentService maps both disconnection and missing-row to UNKNOWN_COMMIT;
    observe the native SQLSTATE rather than treating that ambiguous code as auth.
    """
    with intent_port(settings, graph, current, audit, binding) as (port, states):
        try:
            port.get_receipt(binding.witness, probe_key)
        except Denied as exc:
            if str(exc) == "UNKNOWN_COMMIT" and states == ["P0002"]:
                current()
                return
            raise
        raise Denied("B5P0_PROBE_COLLISION")
