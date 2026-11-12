"""Pure proposed dispositions. Never a native/durable ReviewDecision."""

from dataclasses import dataclass
import re

from .canonical import COMMAND_LIMIT, canonical, digest, parse, refuse, shape, text
from .target import ReviewTarget

BASE_KEYS = (
    "contract_version",
    "kind",
    "tenant_id",
    "report_id",
    "report_version",
    "target_digest",
    "expected_review_seq",
    "idempotency_key",
    "dispositions",
    "sections",
    "reason",
)


@dataclass(frozen=True, slots=True)
class ReviewCommandProposal:
    """Untrusted immutable proposed command; validate against a replayed target."""

    payload: bytes

    @property
    def document(self):
        return parse(self.payload, limit=COMMAND_LIMIT)


@dataclass(frozen=True, slots=True)
class CoverageAcknowledgementProposal:
    """Separate kind: cannot request approval or contain a native decision."""

    payload: bytes

    @property
    def document(self):
        return parse(self.payload, limit=COMMAND_LIMIT)


def _validate_proposal(proposal, target: ReviewTarget):
    if type(proposal) not in (ReviewCommandProposal, CoverageAcknowledgementProposal):
        refuse("D_COMMAND_TYPE")
    c, t = proposal.document, target.document
    is_review = type(proposal) is ReviewCommandProposal
    shape(c, BASE_KEYS + (("action",) if is_review else ("checked_scope", "remaining_unknowns")))
    if c["contract_version"] != "ra3d-review-proposal-offline-v1" or c["kind"] != (
        "REVIEW_COMMAND_PROPOSAL" if is_review else "COVERAGE_ACK_PROPOSAL"
    ):
        refuse("D_COMMAND_VERSION")
    if c["tenant_id"] != t["tenant_id"] or c["report_id"] != t["report_id"]:
        refuse("D_TENANT_SCOPE")
    if (
        type(c["report_version"]) is not int
        or c["report_version"] != t["report_version"]
        or c["target_digest"] != target.target_digest
    ):
        refuse("D_TARGET_STALE")
    if type(c["expected_review_seq"]) is not int or not 0 <= c["expected_review_seq"] <= 9999:
        refuse("D_REVIEW_CONFLICT")
    if type(c["idempotency_key"]) is not str or not re.fullmatch(
        r"[A-Za-z0-9_.-]{8,128}", c["idempotency_key"]
    ):
        refuse("D_IDEMPOTENCY_KEY")
    if is_review:
        if t["kind"] != "L1_NATIVE":
            refuse("D_COVERAGE_NOT_REPORT")
        if c["action"] not in ("APPROVE_CANDIDATE", "REQUEST_CHANGES", "REJECT"):
            refuse("D_ACTION")
    elif t["kind"] != "COVERAGE_ONLY":
        refuse("D_COVERAGE_NOT_REPORT")
    if c["reason"] is not None:
        text(c["reason"])
    if is_review and c["action"] in ("REQUEST_CHANGES", "REJECT") and c["reason"] is None:
        refuse("D_REASON_REQUIRED")
    claims = {(x["guard_ref"], x["binding_ref"], x["pointer"]): x for x in t["claims"]}
    if type(c["dispositions"]) is not list or len(c["dispositions"]) != len(claims):
        refuse("D_CLAIM_INCOMPLETE")
    seen, changes = set(), []
    for d in c["dispositions"]:
        shape(d, ("guard_ref", "binding_ref", "pointer", "disposition"))
        key = (d["guard_ref"], d["binding_ref"], d["pointer"])
        if any(type(v) is not str for v in key):
            refuse("D_CLAIM_INCOMPLETE")
        if key not in claims or key in seen:
            refuse("D_CLAIM_INCOMPLETE")
        seen.add(key)
        if d["disposition"] in ("CHANGE_REQUESTED", "REJECTED"):
            changes.append(d["disposition"])
        elif d["disposition"] != claims[key]["allowed_acceptance"]:
            refuse("D_CLAIM_CEILING")
    if is_review:
        if c["action"] == "APPROVE_CANDIDATE" and changes:
            refuse("D_CLAIM_CEILING")
        if c["action"] == "REQUEST_CHANGES" and "CHANGE_REQUESTED" not in changes:
            refuse("D_REASON_LOCATION")
        if c["action"] == "REJECT" and "REJECTED" not in changes:
            refuse("D_REASON_LOCATION")
    elif changes:
        refuse("D_CLAIM_CEILING")
    if type(c["sections"]) is not list or len(c["sections"]) != len(t["required_sections"]):
        refuse("D_SECTION_INCOMPLETE")
    seen_sections = set()
    for section in c["sections"]:
        shape(section, ("section_id", "target_digest", "acknowledged"))
        name = section["section_id"]
        if (
            type(name) is not str
            or name in seen_sections
            or name not in t["required_sections"]
            or section["target_digest"] != target.target_digest
            or section["acknowledged"] is not True
        ):
            refuse("D_SECTION_INCOMPLETE")
        seen_sections.add(name)
    if not is_review:
        if (
            c["checked_scope"] != t["scope_digest"]
            or c["remaining_unknowns"] != t["limitations_digest"]
        ):
            refuse("D_COVERAGE_SCOPE")
    return digest("command", c, limit=COMMAND_LIMIT)


def proposal_bytes(value):
    """Encoding helper only; never fills acknowledgements or invents authority."""
    return canonical(value, limit=COMMAND_LIMIT)


def validate_proposal(proposal, target: ReviewTarget):
    from .canonical import ReviewError

    try:
        return _validate_proposal(proposal, target)
    except ReviewError:
        raise
    except (TypeError, ValueError, KeyError, IndexError, AttributeError):
        refuse("D_COMMAND_SHAPE")
