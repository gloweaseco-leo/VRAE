"""Commerce events are VEYFRONT facts, never inferred from audit status."""

from .errors import DomainError


def advance_handoff(handoff: dict, to_stage: str) -> dict:
    current = handoff["stage"]
    allowed = {
        "HANDOFF_REQUESTED": "VF_INQUIRY_RECORDED",
        "VF_INQUIRY_RECORDED": "QUALIFIED_BY_HUMAN",
    }
    if allowed.get(current) != to_stage:
        raise DomainError("INVALID_TRANSITION", "Cannot infer business progress")
    if to_stage == "VF_INQUIRY_RECORDED" and not handoff["vf_receipt_ref"]:
        raise DomainError("BUSINESS_EVIDENCE_REQUIRED", "No saved VF inquiry receipt")
    if to_stage == "QUALIFIED_BY_HUMAN" and not all((
        handoff["vf_receipt_ref"],
        handoff["inquiry_evidence_ref"],
        handoff["verified_by"],
    )):
        raise DomainError("BUSINESS_EVIDENCE_REQUIRED", "No verified human qualification")
    return {**handoff, "stage": to_stage}
