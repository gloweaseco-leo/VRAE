"""Nondurable sequential first-writer-wins reference; NOT production concurrency.

No database, transaction, signing, native approval, grant, share, or recovery.
Synthetic receipts are inert, immutable and incapable of authorizing anything.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from .canonical import canonical, digest, parse, refuse, text
from .proposals import CoverageAcknowledgementProposal, ReviewCommandProposal, validate_proposal
from .target import SyntheticTrust, ReviewTarget, build_target, validate_target

TEST_ONLY = "TEST_ONLY_ACTOR"


def prepare_production_review(*args, **kwargs):
    """Future verified human/session/auth/persistence port: unimplemented, deny ALL."""
    refuse("D_AUTHENTICATED_PRODUCTION_REVIEW_NOT_IMPLEMENTED")


@dataclass(frozen=True, slots=True)
class TestOnlyActor:
    """Deliberately labelled synthetic fixture. Never a verified natural person."""

    label: str
    tenant_id: str
    actor_id: str
    role: str
    assigned_reports: tuple[str, ...]
    synthetic_verified: bool
    actor_kind: str = "SYNTHETIC_HUMAN"


@dataclass(frozen=True, slots=True)
class SimulationReceipt:
    payload: bytes

    @property
    def document(self):
        return parse(self.payload)


@dataclass(frozen=True, slots=True)
class SimulationOutcome:
    receipt: SimulationReceipt
    effective_current: bool


@dataclass(frozen=True, slots=True)
class _Snapshot:
    target: ReviewTarget
    document: bytes
    html: bytes
    source: bytes
    trust: SyntheticTrust


class InMemoryReviewSimulation:
    """No thread-safety/persistence; callers serialize this reference model.

    Competing commands are explicitly interleaved in tests. This is not a
    transaction/CAS service. A new instance has no recovery state.
    """

    def __init__(self, *, simulation_label):
        if simulation_label != "OFFLINE_TEST_ONLY_NON_DURABLE":
            refuse("D_SIMULATION_ONLY")
        self._latest: dict[tuple, _Snapshot] = {}
        self._receipts: dict[tuple, SimulationReceipt] = {}
        self._idempotency: dict[tuple, tuple[str, SimulationReceipt]] = {}
        self._clock_high_water: datetime | None = None

    @staticmethod
    def _actor(actor, tenant_id, report_id):
        if type(actor) is not TestOnlyActor or actor.label != TEST_ONLY:
            refuse("D_HUMAN_REQUIRED")
        if actor.tenant_id != tenant_id:
            refuse("D_TENANT_SCOPE")
        if (
            actor.synthetic_verified is not True
            or actor.actor_kind != "SYNTHETIC_HUMAN"
            or actor.role not in ("OWNER", "REVIEWER")
        ):
            refuse("D_HUMAN_REQUIRED")
        if type(actor.assigned_reports) is not tuple or report_id not in actor.assigned_reports:
            refuse("D_ASSIGNMENT_REQUIRED")
        text(actor.actor_id, 128)

    def _clock(self, now):
        if (
            type(now) is not datetime
            or now.tzinfo is None
            or now.utcoffset() != timedelta(0)
            or (self._clock_high_water is not None and now < self._clock_high_water)
        ):
            refuse("D_CLOCK_UNTRUSTED")
        # Synthetic observation only; this mark is lost on restart.
        self._clock_high_water = now
        return now

    def publish(self, document, html, source, *, trust):
        target = build_target(document, html, source, trust=trust)
        t = target.document
        key = (t["tenant_id"], t["report_id"])
        old = self._latest.get(key)
        if old is not None:
            o = old.target.document
            if t["report_version"] <= o["report_version"]:
                if target.payload == old.target.payload:
                    return old.target
                refuse("D_VERSION_ROLLBACK")
        self._latest[key] = _Snapshot(target, document, html, source, trust)
        return target

    def submit(self, tenant_id, report_id, actor, proposal, *, synthetic_now=None):
        self._actor(actor, tenant_id, report_id)
        now = self._clock(synthetic_now)
        snapshot = self._latest.get((tenant_id, report_id))
        if snapshot is None:
            refuse("D_TARGET_REQUIRED")
        target = snapshot.target
        t = target.document
        if type(proposal) not in (ReviewCommandProposal, CoverageAcknowledgementProposal):
            refuse("D_COMMAND_TYPE")
        c = proposal.document
        if type(c) is not dict or type(c.get("idempotency_key")) is not str:
            refuse("D_COMMAND_SHAPE")
        validate_target(
            target, snapshot.document, snapshot.html, snapshot.source, trust=snapshot.trust
        )
        idem = (tenant_id, actor.actor_id, report_id, c.get("idempotency_key"))
        old = self._idempotency.get(idem)
        if old is not None:
            command_hash, receipt = old
            if digest("command", c, limit=131_072) != command_hash:
                refuse("D_COMMAND_CONFLICT")
            return SimulationOutcome(receipt, self._effective(receipt))
        command_hash = validate_proposal(proposal, target)
        round_key = (tenant_id, report_id, t["report_version"], target.target_digest)
        if round_key in self._receipts:
            refuse("D_REVIEW_CLOSED")
        if c["expected_review_seq"] != 0:
            refuse("D_REVIEW_CONFLICT")
        statuses = {
            "APPROVE_CANDIDATE": "SIMULATED_APPROVE_CANDIDATE",
            "REQUEST_CHANGES": "SIMULATED_CHANGES_REQUESTED",
            "REJECT": "SIMULATED_REJECTED",
        }
        status = (
            statuses[c["action"]] if t["kind"] == "L1_NATIVE" else "SIMULATED_INTERNAL_SCOPE_ACK"
        )
        payload = {
            "contract_version": "ra3d-simulation-receipt-offline-v1",
            "authority": "TEST_ONLY_ACTOR_NON_DURABLE_NO_REAL_DECISION",
            "tenant_id": tenant_id,
            "report_id": report_id,
            "report_version": t["report_version"],
            "target_digest": target.target_digest,
            "review_seq": 1,
            "status": status,
            "synthetic_actor_id": actor.actor_id,
            "synthetic_time": now.isoformat(),
            "command_digest": command_hash,
            "command": c,
            "native_decision": None,
            "native_approval": None,
            "share_grant": None,
            "external_visibility": False,
            "durable": False,
        }
        payload["receipt_digest"] = digest("simulation-receipt", payload)
        receipt = SimulationReceipt(canonical(payload))
        self._receipts[round_key] = receipt
        self._idempotency[idem] = (command_hash, receipt)
        self._clock_high_water = now
        return SimulationOutcome(receipt, True)

    def _effective(self, receipt):
        r = receipt.document
        latest = self._latest.get((r["tenant_id"], r["report_id"]))
        return (
            latest is not None
            and latest.target.target_digest == r["target_digest"]
            and self._receipts.get(
                (r["tenant_id"], r["report_id"], r["report_version"], r["target_digest"])
            )
            is receipt
        )

    def current_effect(self, tenant_id, report_id, actor, receipt, *, synthetic_now=None):
        self._actor(actor, tenant_id, report_id)
        self._clock(synthetic_now)
        if (
            type(receipt) is not SimulationReceipt
            or receipt.document["tenant_id"] != tenant_id
            or receipt.document["report_id"] != report_id
        ):
            refuse("D_DECISION_UNTRUSTED")
        return self._effective(receipt)

    @property
    def simulation_count(self):
        return len(self._receipts)
