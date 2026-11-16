"""Replay a bounded native capture archive through the accepted EvidencePack.

This checks consistency, not signed provenance or current access authority. It
never rewrites capture scope, timestamps, response status or snapshot identities.
The accepted Worker is responsible for any later actual task-scope collection.
"""
import base64
import json
import re
from dataclasses import dataclass

from vrae.evidence import EvidenceError, EvidencePack

from .sources import OperationsDenied, SourceBundle, digest, text


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OperationsDenied("L2_NATIVE_DUPLICATE_KEY")
        result[key] = value
    return result


def _nonfinite(_value):
    raise OperationsDenied("L2_NATIVE_NONFINITE_JSON")


@dataclass(frozen=True)
class NativeInput:
    pack: EvidencePack
    source_bundle_sha256: str
    consumed_reference: str
    pending_references: tuple[str, ...]

    def __post_init__(self):
        if type(self.pack) is not EvidencePack:
            raise OperationsDenied("L2_NATIVE_EVIDENCE_INTEGRITY")
        self.pack.verify()
        digest(self.source_bundle_sha256)
        text(self.consumed_reference)

    def metadata(self):
        doc = self.pack.document
        return {"state": "NATIVE_SOURCE_VERIFIED_NOT_DIAGNOSED",
                "native_pack_ref": self.pack.ref, "tenant_id": doc["tenant_id"],
                "original_capture_run_id": doc["run_id"],
                "source_bundle_sha256": self.source_bundle_sha256,
                "consumed_input_refs": [self.consumed_reference],
                "inputs_not_in_native_pack": list(self.pending_references),
                "snapshot_count": len(doc["snapshots"]), "evidence_count": len(doc["evidence"]),
                "network_requests": 0, "worker_task_created": False,
                "task_handle": None, "report_version": None,
                "authority": "CONSISTENCY_NOT_SIGNED_PROVENANCE_OR_ACCESS_GRANT"}


def load_native(bundle: SourceBundle, reference, *, expected_pack_ref, expected_capture_run_id):
    """Pins come from trusted server provisioning, not a browser authorization claim."""
    text(reference)
    text(expected_capture_run_id)
    if type(expected_pack_ref) is not str or not re.fullmatch(r"ep-[a-f0-9]{64}", expected_pack_ref):
        raise OperationsDenied("L2_NATIVE_EXPECTED_PIN_REQUIRED")
    selected = next((item for item in bundle.inputs if item.reference == reference), None)
    if selected is None or selected.media_type != "application/json":
        raise OperationsDenied("L2_NATIVE_CAPTURE_ARCHIVE_REQUIRED")
    try:
        archive = json.loads(selected.raw.decode("utf-8"), object_pairs_hook=_pairs,
                             parse_constant=_nonfinite)
        if type(archive) is not dict or set(archive) != {"pack", "objects_base64"}:
            raise OperationsDenied("L2_NATIVE_ARCHIVE_SHAPE")
        encoded = archive["objects_base64"]
        if type(encoded) is not dict or len(encoded) > 512:
            raise OperationsDenied("L2_NATIVE_OBJECT_BOUND")
        objects = {}
        for key, value in encoded.items():
            digest(key)
            if type(value) is not str:
                raise OperationsDenied("L2_NATIVE_OBJECT_ENCODING")
            objects[key] = base64.b64decode(value, validate=True)
        pack = EvidencePack.load(archive["pack"], objects, expected_ref=expected_pack_ref)
        doc = pack.document
        if doc["tenant_id"] != bundle.tenant_id or doc["run_id"] != expected_capture_run_id:
            raise OperationsDenied("L2_NATIVE_SOURCE_SCOPE_MISMATCH")
        # Existing M1 recorded input accepts a single CaptureManifest. Do not
        # silently broaden it to screenshots, redirects or arbitrary documents.
        if len(doc["sources"]) != 1 or doc["sources"][0]["kind"] != "CaptureManifest":
            raise OperationsDenied("L2_NATIVE_ACCEPTED_CAPTURE_REQUIRED")
        return NativeInput(pack, bundle.document()["content_sha256"], reference,
                           tuple(i.reference for i in bundle.inputs if i.reference != reference))
    except OperationsDenied:
        raise
    except (EvidenceError, ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        raise OperationsDenied("L2_NATIVE_EVIDENCE_INTEGRITY") from None
