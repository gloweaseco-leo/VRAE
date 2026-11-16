"""Actual measured duration and explicitly priced estimates; unknown is not zero."""

import re
import time
from dataclasses import dataclass
from decimal import ROUND_UP, Decimal

from .sources import OperationsDenied, text


@dataclass(frozen=True)
class Measurement:
    operation_ref: str
    kind: str
    wall_ns: int
    cpu_ns: int | None
    actor_kind: str
    attestation_ref: str | None = None

    def __post_init__(self):
        text(self.operation_ref)
        if self.kind not in {"DIAGNOSIS_RUNTIME", "REVIEW_ACTIVITY", "SALES_PREPARATION"}:
            raise OperationsDenied("L2_MEASUREMENT_KIND")
        if self.actor_kind not in {"SYSTEM", "AUTOMATED_DEMO", "HUMAN_ATTESTED"}:
            raise OperationsDenied("L2_ACTIVITY_ATTRIBUTION")
        if self.actor_kind == "HUMAN_ATTESTED":
            text(self.attestation_ref)
        elif self.attestation_ref is not None:
            raise OperationsDenied("L2_ATTESTATION_ATTRIBUTION")
        for value in (self.wall_ns, self.cpu_ns):
            if value is not None and (type(value) is not int or not 0 <= value <= 86_400_000_000_000):
                raise OperationsDenied("L2_MEASUREMENT_BOUND")
        if self.wall_ns is None:
            raise OperationsDenied("L2_MEASUREMENT_REQUIRED")

    def priced(self, *, rate_micros_per_hour=None, currency=None):
        if (rate_micros_per_hour is not None and
                (type(rate_micros_per_hour) is not int or not 0 <= rate_micros_per_hour <= 1_000_000_000_000)):
            raise OperationsDenied("L2_RATE_BOUND")
        if currency is not None and (type(currency) is not str or re.fullmatch(r"[A-Z]{3}", currency) is None):
            raise OperationsDenied("L2_CURRENCY")
        known = rate_micros_per_hour is not None and currency is not None
        amount = None
        if rate_micros_per_hour is not None and currency is not None:
            amount = int((Decimal(self.wall_ns) * Decimal(rate_micros_per_hour) / Decimal(3_600_000_000_000)).to_integral_value(rounding=ROUND_UP))
        return {"operation_ref": self.operation_ref, "kind": self.kind, "wall_ns": self.wall_ns,
                "cpu_ns": self.cpu_ns, "actor_kind": self.actor_kind,
                "human_labor_claim": self.actor_kind == "HUMAN_ATTESTED",
                "attestation_ref": self.attestation_ref,
                "rate_micros_per_hour": rate_micros_per_hour, "currency": currency,
                "amount_micros": amount, "cost_status": "ESTIMATED" if known else "UNKNOWN",
                "invoice_reconciled": False}


class ActivityTimer:
    def __init__(self, operation_ref, kind, actor_kind, *, attestation_ref=None, clock=time.monotonic_ns):
        self.operation_ref, self.kind, self.actor_kind = operation_ref, kind, actor_kind
        self.attestation_ref = attestation_ref
        self.clock = clock
        self.started = clock()
        self.finished = False

    def finish(self):
        if self.finished:
            raise OperationsDenied("L2_ACTIVITY_ALREADY_FINISHED")
        duration = self.clock() - self.started
        measurement = Measurement(self.operation_ref, self.kind, duration, None, self.actor_kind, self.attestation_ref)
        self.finished = True
        return measurement


def validated_cost(row):
    if type(row) is not dict:
        raise OperationsDenied("L2_COST_RECORD_REQUIRED")
    try:
        expected = Measurement(row["operation_ref"], row["kind"], row["wall_ns"],
                               row["cpu_ns"], row["actor_kind"], row["attestation_ref"]).priced(
            rate_micros_per_hour=row["rate_micros_per_hour"], currency=row["currency"])
    except KeyError:
        raise OperationsDenied("L2_COST_RECORD_REQUIRED") from None
    if row != expected:
        raise OperationsDenied("L2_COST_RECORD_CHANGED")
    return expected


def total_cost(rows):
    rows = tuple(validated_cost(row) for row in rows)
    currencies = {r["currency"] for r in rows if r["currency"] is not None}
    known = bool(rows) and len(currencies) == 1 and all(r["amount_micros"] is not None for r in rows)
    return {"currency": next(iter(currencies)) if len(currencies) == 1 else None,
            "amount_micros": sum(r["amount_micros"] for r in rows) if known else None,
            "cost_status": "ESTIMATED" if known else "UNKNOWN", "invoice_reconciled": False}
