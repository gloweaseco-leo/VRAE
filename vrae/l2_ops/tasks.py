"""Compose the accepted APP202 and signed M1 reader; never confer review authority.

A fresh Worker pack is a prerequisite for native L2 analysis. It is deliberately
not an L2 result or a reusable signed authorization context.
"""
import base64
from dataclasses import asdict, dataclass, field

from vrae.application.ra4b_p2.m1.consumer import TaskClient, TaskHandle
from vrae.application.ra4b_p2.m1.reader import SignedGeneratedReader
from vrae.evidence import EvidencePack
from vrae.reviewing.canonical import SOURCE_LIMIT, parse

from .native_input import NativeInput
from .sources import OperationsDenied, text


def capture_identity(pack):
    """Compare retained evidence, excluding fresh run IDs and capture timestamps."""
    pack.verify()
    sources = pack.document["sources"]
    if len(sources) != 1 or sources[0]["kind"] != "CaptureManifest":
        raise OperationsDenied("L2_TASK_SINGLE_CAPTURE_REQUIRED")
    capture = sources[0]["document"]
    pages = tuple(sorted((p["snapshot"]["url"], p["snapshot"]["final_url"],
                          p["http_status"], p["snapshot"]["sha256"])
                         for p in capture["pages"]))
    if not pages or len({p[0] for p in pages}) != len(pages):
        raise OperationsDenied("L2_TASK_CAPTURE_PAGE_IDENTITY")
    robots = capture["robots"]
    return pages, (robots["url"], robots["status"], robots["sha256"])


@dataclass(frozen=True)
class RegisteredSource:
    """Provisioned by the trusted server; a browser cannot supply this object."""
    source_ref: str
    native: NativeInput = field(repr=False)

    def __post_init__(self):
        text(self.source_ref)
        if type(self.native) is not NativeInput:
            raise OperationsDenied("L2_TASK_REGISTERED_SOURCE_REQUIRED")
        capture_identity(self.native.pack)


@dataclass(frozen=True)
class WorkerEvidence:
    task: TaskHandle
    pack: EvidencePack = field(repr=False)
    source_bundle_sha256: str
    original_pack_ref: str
    signed_locator: dict = field(repr=False)

    def metadata(self):
        return {"state": "WORKER_EVIDENCE_VERIFIED_DEEP_ANALYSIS_PENDING",
                "task": asdict(self.task), "source_bundle_sha256": self.source_bundle_sha256,
                "original_pack_ref": self.original_pack_ref, "worker_pack_ref": self.pack.ref,
                "snapshot_count": len(self.pack.document["snapshots"]),
                "l2_complete": False, "review_authority": False,
                "authority": "SIGNED_M1_READ_SNAPSHOT_NOT_CURRENT_L2_REVIEW_AUTHORITY"}


class L2Tasks:
    def __init__(self, client, sources):
        if type(client) is not TaskClient:
            raise OperationsDenied("L2_TASK_CANONICAL_CLIENT_REQUIRED")
        rows = tuple(sources)
        if not rows or any(type(row) is not RegisteredSource for row in rows):
            raise OperationsDenied("L2_TASK_REGISTERED_SOURCE_REQUIRED")
        self.sources = {row.source_ref: row for row in rows}
        if len(rows) != len(self.sources) or any(
            row.source_ref not in client.endpoint.source_refs
            or row.native.pack.document["tenant_id"] != client.endpoint.tenant_id for row in rows
        ):
            raise OperationsDenied("L2_TASK_SOURCE_SCOPE")
        self.client = client

    def _source(self, task):
        if type(task) is not TaskHandle or task.tenant_id != self.client.endpoint.tenant_id:
            raise OperationsDenied("L2_TASK_SOURCE_SCOPE")
        try:
            return self.sources[task.source_ref]
        except KeyError:
            raise OperationsDenied("L2_TASK_UNREGISTERED_SOURCE") from None

    def create(self, source_ref, *, idempotency_key):
        if source_ref not in self.sources:
            raise OperationsDenied("L2_TASK_UNREGISTERED_SOURCE")
        return self.client.create(source_ref, idempotency_key=idempotency_key)

    def status(self, task):
        self._source(task)
        return self.client.status(task)

    def read_worker(self, task, reader, bearer, *, nonce):
        source = self._source(task)
        if type(reader) is not SignedGeneratedReader:
            raise OperationsDenied("L2_TASK_SIGNED_READER_REQUIRED")
        # This checks real status, original JWT/nonce/assignment/low-role read and
        # actual locator correlation. No DONE-only or caller-provided DTO shortcut.
        result = self.client.read(task, reader, bearer, nonce=nonce)
        try:
            data = parse(result.source, limit=SOURCE_LIMIT)
            report = parse(result.report, limit=SOURCE_LIMIT)
            pin = report["pins"]["expected_pack_ref"]
            pack = EvidencePack.load(data["pack"],
                {k: base64.b64decode(v, validate=True) for k, v in data["objects_base64"].items()},
                expected_ref=pin)
            if (pack.document["tenant_id"], pack.document["run_id"]) != (task.tenant_id, task.run_id):
                raise OperationsDenied("L2_TASK_WORKER_SCOPE_MISMATCH")
            if capture_identity(pack) != capture_identity(source.native.pack):
                raise OperationsDenied("L2_TASK_WORKER_SOURCE_MISMATCH")
            return WorkerEvidence(task, pack, source.native.source_bundle_sha256,
                                  source.native.pack.ref, dict(result.locator))
        except OperationsDenied:
            raise
        except Exception:
            raise OperationsDenied("L2_TASK_WORKER_EVIDENCE_DENIED") from None
