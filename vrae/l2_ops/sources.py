"""Versioned evidence custody. Access mode never determines diagnostic depth."""

import hashlib
import re
from dataclasses import dataclass, field

from vrae.reviewing.canonical import canonical, sha

VERSION = "l2-source-bundle-v1"
MODES = frozenset({"OFFLINE_SYNTHETIC", "PUBLIC_READONLY_CAPTURE", "CLIENT_PROVIDED"})
MEDIA = frozenset({"text/plain", "text/html", "text/csv", "application/json"})


class OperationsDenied(ValueError):
    def __init__(self, code="L2_OPERATIONS_DENIED"):
        super().__init__(code)
        self.code = code


def text(value, *, limit=256):
    if type(value) is not str or not 1 <= len(value) <= limit or not value.strip() or any(ord(c) < 32 or 0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069 for c in value):
        raise OperationsDenied("L2_BOUNDED_TEXT_REQUIRED")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise OperationsDenied("L2_UTF8_TEXT_REQUIRED") from None
    return value


def digest(value):
    if type(value) is not str or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise OperationsDenied("L2_SHA256_REQUIRED")
    return value


@dataclass(frozen=True)
class EvidenceInput:
    reference: str
    media_type: str
    raw: bytes = field(repr=False)
    origin_reference: str
    analysis_basis_reference: str
    synthetic: bool
    reuse_permission_reference: str | None = None

    def __post_init__(self):
        for value in (self.reference, self.origin_reference, self.analysis_basis_reference):
            text(value)
        if self.media_type not in MEDIA or type(self.raw) is not bytes or not 1 <= len(self.raw) <= 2_000_000:
            raise OperationsDenied("L2_BOUNDED_EVIDENCE_REQUIRED")
        try:
            self.raw.decode("utf-8", errors="strict")
        except UnicodeError:
            raise OperationsDenied("L2_UTF8_EVIDENCE_REQUIRED") from None
        if type(self.synthetic) is not bool:
            raise OperationsDenied()
        if self.reuse_permission_reference is not None:
            text(self.reuse_permission_reference)

    def descriptor(self):
        return {"reference": self.reference, "media_type": self.media_type,
                "sha256": hashlib.sha256(self.raw).hexdigest(), "bytes": len(self.raw),
                "origin_reference": self.origin_reference, "analysis_basis_reference": self.analysis_basis_reference,
                "synthetic": self.synthetic, "reuse_permission_reference": self.reuse_permission_reference,
                "rebuild_asset_use": "PENDING_CONFIRMATION" if self.reuse_permission_reference is None else "REFERENCE_REQUIRES_CURRENT_VERIFICATION"}


@dataclass(frozen=True)
class SourceBundle:
    tenant_id: str
    bundle_id: str
    access_mode: str
    inputs: tuple[EvidenceInput, ...]
    external_run_permission_reference: str | None = None

    def __post_init__(self):
        text(self.tenant_id, limit=64)
        text(self.bundle_id, limit=128)
        if self.access_mode not in MODES or type(self.inputs) is not tuple or not 1 <= len(self.inputs) <= 16:
            raise OperationsDenied("L2_SOURCE_MODE_OR_BOUND")
        if any(type(i) is not EvidenceInput for i in self.inputs):
            raise OperationsDenied()
        if len({i.reference for i in self.inputs}) != len(self.inputs):
            raise OperationsDenied("L2_DUPLICATE_EVIDENCE_REF")
        if self.access_mode == "OFFLINE_SYNTHETIC" and any(not i.synthetic for i in self.inputs):
            raise OperationsDenied("L2_SYNTHETIC_LABEL_MISMATCH")
        if self.external_run_permission_reference is not None:
            text(self.external_run_permission_reference)

    def document(self):
        core = {"contract_version": VERSION, "diagnostic_level": "L2", "tenant_id": self.tenant_id,
                "bundle_id": self.bundle_id, "access_mode": self.access_mode,
                "execution": "OFFLINE_CAPTURE_ONLY", "network_requests": 0,
                "inputs": [i.descriptor() for i in self.inputs],
                "external_run_permission_reference": self.external_run_permission_reference,
                "external_delivery_allowed": False}
        return {**core, "content_sha256": sha(canonical(core, limit=131072))}

    def require_external_access(self):
        # Receipt-shaped strings do not enable an unimplemented live transport.
        raise OperationsDenied("L2_EXTERNAL_EXECUTION_NOT_ENABLED_THIS_RUN")
