"""Internal commercial preparation bound to current, authorized L2 output.

DTO validation is not authentication. Only the composition root supplies the
current-reader context, held throughout preparation/readback. No VF receipt is
verified here; external handoff remains unavailable.
"""

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from vrae.reviewing.canonical import canonical, parse, sha

from .accounting import total_cost
from .sources import OperationsDenied, SourceBundle, digest, text

PIN_FIELDS = ("tenant_id", "request_id", "run_id", "job_id", "event_id", "source_ref", "report_ref", "report_version", "native_pack_ref", "diagnosis_ref")
HASH_FIELDS = ("report_sha256", "source_bundle_sha256", "industry_pack_sha256", "payload_sha256")
CONFIRMATIONS = ("business_goals", "products_and_target_markets", "material_reuse_rights",
                 "included_and_excluded_scope", "legacy_urls_and_redirects", "acceptance_criteria",
                 "customer_approval", "veyfront_consultation_receipt")


def exact_shape(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise OperationsDenied("L2_EXACT_SHAPE_REQUIRED")


def pin(value):
    exact_shape(value, (*PIN_FIELDS, *HASH_FIELDS))
    for key in PIN_FIELDS:
        text(value[key])
    for key in HASH_FIELDS:
        digest(value[key])
    for key, prefix in (("native_pack_ref", "ep-"), ("diagnosis_ref", "l2-")):
        if not value[key].startswith(prefix):
            raise OperationsDenied("L2_NATIVE_RESULT_PIN_REQUIRED")
        digest(value[key][len(prefix):])
    return parse(canonical(value))


@dataclass(frozen=True)
class CurrentL2:
    """Normalized *trusted server adapter* result, never a browser input DTO."""

    pins: dict
    payload: dict
    review: dict
    blueprint: dict
    authority_expires_at: datetime = field(repr=False)

    def assert_live(self):
        deadline = self.authority_expires_at
        if type(deadline) is not datetime or deadline.tzinfo is None or deadline.utcoffset() is None:
            raise OperationsDenied("L2_CURRENT_AUTHORITY_DEADLINE_REQUIRED")
        if datetime.now(UTC) >= deadline:
            raise OperationsDenied("L2_CURRENT_AUTHORITY_EXPIRED")

    def snapshot(self):
        self.assert_live()
        p = pin(self.pins)
        payload = parse(canonical(self.payload, limit=1_000_000), limit=1_000_000)
        if sha(canonical(payload, limit=1_000_000)) != p["payload_sha256"]:
            raise OperationsDenied("L2_PAYLOAD_CHANGED")
        if payload.get("diagnostic_depth") != "L2":
            raise OperationsDenied("L2_DEEP_RESULT_REQUIRED")
        bindings = {"tenant_id": "tenant_id", "run_id": "run_id",
                    "expected_pack_ref": "native_pack_ref", "diagnosis_ref": "diagnosis_ref"}
        if any(payload.get(source) != p[target] for source, target in bindings.items()):
            raise OperationsDenied("L2_NATIVE_TASK_BINDING_MISMATCH")
        # The accepted upstream producer owns content semantics. This adapter
        # only checks correlation, not a second diagnostic or review engine.
        r = parse(canonical(self.review))
        exact_shape(r, ("receipt_ref", "receipt_sha256", "report_version", "report_sha256", "decision"))
        text(r["receipt_ref"])
        digest(r["receipt_sha256"])
        if r["decision"] not in {"APPROVE_INTERNAL", "REJECT_INTERNAL", "REVISE_INTERNAL"}:
            raise OperationsDenied("L2_REVIEW_DECISION")
        if (r["report_version"], r["report_sha256"]) != (p["report_version"], p["report_sha256"]):
            raise OperationsDenied("L2_REVIEW_VERSION_MISMATCH")
        b = parse(canonical(self.blueprint, limit=1_000_000), limit=1_000_000)
        if b.get("report_version") != p["report_version"] or b.get("report_sha256") != p["report_sha256"]:
            raise OperationsDenied("L2_BLUEPRINT_VERSION_MISMATCH")
        return p, payload, r, b


class CurrentReader(Protocol):
    def current(self) -> AbstractContextManager[CurrentL2]:
        """Original signature/tenant/revocation/current-version checks and lock."""
        ...


class BriefService:
    def __init__(self, reader: CurrentReader):
        self.reader = reader

    def prepare(self, bundle: SourceBundle, *, brief_ref, activities=(), consultation_ref=None):
        text(brief_ref)
        if consultation_ref is not None:
            text(consultation_ref)
        source = bundle.document()
        with self.reader.current() as current:
            p, payload, review, blueprint = current.snapshot()
            if p["tenant_id"] != bundle.tenant_id:
                raise OperationsDenied("L2_TENANT_MISMATCH")
            if p["source_bundle_sha256"] != source["content_sha256"]:
                raise OperationsDenied("L2_SOURCE_MISMATCH")
            rows = parse(canonical(list(activities)))
            costs = total_cost(rows)
            core = {
                "contract_version": "internal-rebuild-brief-v1", "brief_ref": brief_ref,
                "audience": "VEYFRONT_INTERNAL", "pins": p, "source": source,
                "review": review, "blueprint": blueprint,
                "diagnostic_payload_sha256": sha(canonical(payload, limit=1_000_000)),
                "preparation_status": {"APPROVE_INTERNAL": "INTERNAL_REVIEW_RECORDED",
                                       "REJECT_INTERNAL": "REJECTED",
                                       "REVISE_INTERNAL": "REVISION_REQUIRED"}[review["decision"]],
                "customer_confirmations": [{"key": k, "status": "PENDING", "evidence_ref": None}
                                           for k in CONFIRMATIONS],
                "consultation": {"reference": consultation_ref,
                                 "state": "UNVERIFIED_REFERENCE" if consultation_ref else "UNLINKED",
                                 "verified_receipt": None, "counts_as_e2": False, "counts_as_e3": False},
                "activities": rows, "cost_total": costs,
                "external_delivery_allowed": False, "customer_approval": False,
                "l2m_execution_allowed": False,
            }
            return {**core, "content_sha256": sha(canonical(core, limit=2_000_000))}

    def read_current(self, document):
        """A stored hash is insufficient: reauthenticate and replay current pins."""
        document = validate_document(parse(canonical(document, limit=2_000_000), limit=2_000_000))
        claimed = document.pop("content_sha256", None)
        if sha(canonical(document, limit=2_000_000)) != claimed:
            raise OperationsDenied("L2_BRIEF_TAMPERED")
        with self.reader.current() as current:
            p, _, review, blueprint = current.snapshot()
            if document["pins"] != p or document["review"] != review or document["blueprint"] != blueprint:
                raise OperationsDenied("L2_BRIEF_STALE_OR_CROSS_TASK")
            current.assert_live()
            return {**document, "content_sha256": claimed}

    def save_current(self, ledger, document):
        # Hold the same upstream authorization/current-version context through
        # the durable COMMIT. Revalidating a hash outside this lock is unsafe.
        validate_document(document)
        with self.reader.current() as current:
            p, _, review, blueprint = current.snapshot()
            if (document.get("pins"), document.get("review"), document.get("blueprint")) != (p, review, blueprint):
                raise OperationsDenied("L2_BRIEF_STALE_OR_CROSS_TASK")
            result = ledger.put(document, authority_expires_at=current.authority_expires_at)
            current.assert_live()
            return result

    def load_current(self, ledger, brief_ref):
        with self.reader.current() as current:
            p, _, review, blueprint = current.snapshot()
            document = validate_document(ledger.get(p["tenant_id"], brief_ref))
            core = {k: v for k, v in document.items() if k != "content_sha256"}
            if sha(canonical(core, limit=2_000_000)) != document.get("content_sha256"):
                raise OperationsDenied("L2_BRIEF_TAMPERED")
            if (document.get("pins"), document.get("review"), document.get("blueprint")) != (p, review, blueprint):
                raise OperationsDenied("L2_BRIEF_STALE_OR_CROSS_TASK")
            current.assert_live()
            return document


def validate_document(document):
    """Validate fixed internal-only claims, including a correctly rehashed edit."""
    keys = ("contract_version", "brief_ref", "audience", "pins", "source", "review", "blueprint",
            "diagnostic_payload_sha256", "preparation_status", "customer_confirmations", "consultation",
            "activities", "cost_total", "external_delivery_allowed", "customer_approval",
            "l2m_execution_allowed", "content_sha256")
    exact_shape(document, keys)
    core = {k: v for k, v in document.items() if k != "content_sha256"}
    if sha(canonical(core, limit=2_000_000)) != document["content_sha256"]:
        raise OperationsDenied("L2_BRIEF_TAMPERED")
    if document["contract_version"] != "internal-rebuild-brief-v1" or document["audience"] != "VEYFRONT_INTERNAL":
        raise OperationsDenied("L2_INTERNAL_ONLY_REQUIRED")
    if any(document[k] is not False for k in ("external_delivery_allowed", "customer_approval", "l2m_execution_allowed")):
        raise OperationsDenied("L2_INTERNAL_ONLY_REQUIRED")
    pin(document["pins"])
    text(document["brief_ref"])
    source = document["source"]
    source_core = {k: v for k, v in source.items() if k != "content_sha256"}
    if (sha(canonical(source_core, limit=131072)) != source.get("content_sha256") or
            source.get("content_sha256") != document["pins"]["source_bundle_sha256"] or
            source.get("tenant_id") != document["pins"]["tenant_id"] or
            source.get("external_delivery_allowed") is not False):
        raise OperationsDenied("L2_SOURCE_MISMATCH")
    if document["diagnostic_payload_sha256"] != document["pins"]["payload_sha256"]:
        raise OperationsDenied("L2_PAYLOAD_CHANGED")
    review = document["review"]
    exact_shape(review, ("receipt_ref", "receipt_sha256", "report_version", "report_sha256", "decision"))
    states = {"APPROVE_INTERNAL": "INTERNAL_REVIEW_RECORDED", "REJECT_INTERNAL": "REJECTED", "REVISE_INTERNAL": "REVISION_REQUIRED"}
    if review["decision"] not in states or document["preparation_status"] != states[review["decision"]]:
        raise OperationsDenied("L2_REVIEW_DECISION")
    if any(document[section].get(k) != document["pins"][k]
           for section in ("review", "blueprint") for k in ("report_version", "report_sha256")):
        raise OperationsDenied("L2_REVIEW_VERSION_MISMATCH")
    consultation = document["consultation"]
    exact_shape(consultation, ("reference", "state", "verified_receipt", "counts_as_e2", "counts_as_e3"))
    if consultation["reference"] is not None:
        text(consultation["reference"])
    expected = {"reference": consultation["reference"],
                "state": "UNVERIFIED_REFERENCE" if consultation["reference"] else "UNLINKED",
                "verified_receipt": None, "counts_as_e2": False, "counts_as_e3": False}
    if consultation != expected:
        raise OperationsDenied("L2_CONSULTATION_AUTHORITY_NOT_VERIFIED")
    pending = [{"key": k, "status": "PENDING", "evidence_ref": None} for k in CONFIRMATIONS]
    if document["customer_confirmations"] != pending:
        raise OperationsDenied("L2_CUSTOMER_CONFIRMATION_NOT_VERIFIED")
    if total_cost(document["activities"]) != document["cost_total"]:
        raise OperationsDenied("L2_COST_RECORD_CHANGED")
    return document
