"""No speculative model charges; cost unknown is a hard stop."""

import math

from .errors import DomainError


def authorize_charge(
    level: str, limit: float | None, spent: float | None,
    next_estimate: float | None, cost_status: str,
) -> None:
    if level == "L0":
        raise DomainError("SOURCE_NOT_ALLOWED", "L0 model calls are prohibited")
    if level not in ("L1", "L2"):
        raise DomainError("SOURCE_NOT_ALLOWED", "Unknown audit tier")
    if cost_status not in ("ESTIMATED", "RECONCILED"):
        raise DomainError("MODEL_COST_UNKNOWN", "Usage status is unknown")
    if any(x is None for x in (limit, spent, next_estimate)):
        raise DomainError("MODEL_COST_UNKNOWN", "Unknown costs cannot be zero")
    assert limit is not None and spent is not None and next_estimate is not None
    if any(x < 0 or not math.isfinite(x) for x in (limit, spent, next_estimate)):
        raise DomainError("MODEL_COST_UNKNOWN", "Invalid/uncertain amount")
    if spent + next_estimate > limit:
        raise DomainError("LIMIT_EXCEEDED", "Run would exceed approved budget")
