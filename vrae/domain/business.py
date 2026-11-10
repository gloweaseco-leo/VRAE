"""Commerce events are VEYFRONT facts, never inferred from audit status."""

from .access import require_access
from .errors import DomainError


def advance_handoff(
    handoff: dict, to_stage: str, actor: dict, *,
    receipt_verified: bool = False, qualification_confirmed: bool = False,
) -> dict:
    require_access(actor, handoff["tenant_id"], "handoff")
    current = handoff["stage"]
    allowed = {
        "HANDOFF_REQUESTED": "VF_INQUIRY_RECORDED",
        "VF_INQUIRY_RECORDED": "QUALIFIED_BY_HUMAN",
    }
    if allowed.get(current) != to_stage:
        raise DomainError("INVALID_TRANSITION", "Cannot infer business progress")
    if to_stage == "VF_INQUIRY_RECORDED" and (
        not handoff["vf_receipt_ref"] or not receipt_verified
    ):
        raise DomainError("BUSINESS_EVIDENCE_REQUIRED", "No saved VF inquiry receipt")
    if to_stage == "QUALIFIED_BY_HUMAN" and (
        actor["role"] != "OWNER" or not qualification_confirmed or not all((
        handoff["vf_receipt_ref"],
        handoff["inquiry_evidence_ref"],
        handoff["verified_by"],
    ))):
        raise DomainError("BUSINESS_EVIDENCE_REQUIRED", "No verified human qualification")
    return {**handoff, "stage": to_stage}
