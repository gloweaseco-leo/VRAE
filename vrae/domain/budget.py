"""Fail-closed paid-call budget contract; no network requests or currency conversion."""

import re
from decimal import Decimal, InvalidOperation

from .errors import DomainError


_CURRENCY = re.compile(r"^[A-Z]{3}$")


def _amount(value: int | float | Decimal | None) -> Decimal:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise DomainError("MODEL_COST_UNKNOWN", "Missing or invalid amount")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainError("MODEL_COST_UNKNOWN", "Invalid amount") from exc
    if not number.is_finite() or number < 0:
        raise DomainError("MODEL_COST_UNKNOWN", "Uncertain/negative amount")
    return number


def authorize_charge(
    level: str,
    limit: int | float | Decimal | None,
    spent: int | float | Decimal | None,
    next_estimate: int | float | Decimal | None,
    cost_status: str,
    *,
    limit_currency: str | None,
    spent_currency: str | None,
    next_currency: str | None,
) -> None:
    """Refuse any paid execution without explicit same-currency known budget.

    This arithmetic guard is not an atomic reservation: RA-4 must transact
    shared, concurrent spending and idempotency before provider invocation.
    """
    if level == "L0":
        raise DomainError("SOURCE_NOT_ALLOWED", "L0 model calls prohibited")
    if level not in ("L1", "L2"):
        raise DomainError("SOURCE_NOT_ALLOWED", "Unknown audit tier")
    if cost_status not in ("ESTIMATED", "RECONCILED"):
        raise DomainError("MODEL_COST_UNKNOWN", "Uncertain provider cost status")
    currencies = (limit_currency, spent_currency, next_currency)
    if any(not isinstance(v, str) or not _CURRENCY.fullmatch(v) for v in currencies):
        raise DomainError("MODEL_COST_UNKNOWN", "Unknown/malformed currency")
    if len(set(currencies)) != 1:
        raise DomainError("MODEL_COST_UNKNOWN", "Currency mismatch; conversion prohibited")
    cap, paid, future = (_amount(v) for v in (limit, spent, next_estimate))
    if paid + future > cap:
        raise DomainError("LIMIT_EXCEEDED", "Paid call would exceed approved budget")
