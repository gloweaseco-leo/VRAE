"""Audit execution state machine distinct from report approval and sharing."""

from .errors import DomainError

_TRANSITIONS = {
    "CREATED": {"POLICY_CHECK", "CANCELLED"},
    "POLICY_CHECK": {"QUEUED", "POLICY_BLOCKED", "CANCELLED"},
    "QUEUED": {"FETCHING", "CANCELLED", "FAILED"},
    "FETCHING": {"EVIDENCE_READY", "ACCESS_BLOCKED", "FAILED", "CANCELLED"},
    "EVIDENCE_READY": {"RULED", "INSUFFICIENT_EVIDENCE", "FAILED", "CANCELLED"},
    "RULED": {"DRAFT_READY", "INSUFFICIENT_EVIDENCE", "MODEL_INVALID", "FAILED"},
    "DRAFT_READY": {"REVIEW_REQUIRED", "FAILED"},
    "REVIEW_REQUIRED": set(),
}
_TERMINAL = {
    "POLICY_BLOCKED", "ACCESS_BLOCKED", "INSUFFICIENT_EVIDENCE",
    "MODEL_INVALID", "FAILED", "CANCELLED",
}
_ALL = set(_TRANSITIONS) | _TERMINAL


def advance_run(current: str, target: str) -> str:
    if current not in _ALL or target not in _ALL:
        raise DomainError("INVALID_TRANSITION", "Unknown state, fail closed")
    if target not in _TRANSITIONS.get(current, set()):
        raise DomainError("INVALID_TRANSITION", "Illegal audit transition")
    return target


def run_completed(status: str) -> bool:
    """Completion is only the review-ready execution state, never approval."""
    if status not in _ALL:
        raise DomainError("INVALID_TRANSITION", "Unknown run status")
    return status == "REVIEW_REQUIRED"
