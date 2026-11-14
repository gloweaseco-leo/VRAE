"""Closed command, server-held witness and non-authoritative receipt contracts."""

from dataclasses import dataclass
from uuid import UUID

from vrae.persistence.private_bytes import Locator
from vrae.reviewing import CoverageAcknowledgementProposal, ReviewCommandProposal
from vrae.reviewing.canonical import COMMAND_LIMIT, canonical, parse

MODE = "B3_P0_TEST_ONLY"
AUTHORITY = "TEST_ONLY_REVIEW_INTENT"


class Denied(RuntimeError):
    """A bounded code, never database exceptions, evidence or credentials."""


def production_review_port(*args, **kwargs):
    raise Denied("B3_NATIVE_REVIEW_DENIED")


def production_share_port(*args, **kwargs):
    raise Denied("B3_SHARE_DENIED")


@dataclass(frozen=True)
class Witness:
    """Provisioned out of band by the disposable server fixture, never a person."""

    token: UUID
    location: Locator


@dataclass(frozen=True)
class Command:
    payload: bytes

    def proposal(self):
        d = parse(self.payload, limit=COMMAND_LIMIT)
        if canonical(d, limit=COMMAND_LIMIT) != self.payload:
            raise Denied("B3_CANONICAL_COMMAND_REQUIRED")
        cls = {
            "REVIEW_COMMAND_PROPOSAL": ReviewCommandProposal,
            "COVERAGE_ACK_PROPOSAL": CoverageAcknowledgementProposal,
        }.get(d.get("kind"))
        if cls is None:
            raise Denied("B3_COMMAND_KIND")
        return cls(self.payload)


@dataclass(frozen=True)
class Receipt:
    payload: bytes

    @property
    def document(self):
        d = parse(self.payload, limit=262144)
        required = {
            "contract_version",
            "authority",
            "intent_id",
            "event_id",
            "tenant_id",
            "report_id",
            "report_version",
            "ref_id",
            "source_run_id",
            "target_digest",
            "source_sha256",
            "html_sha256",
            "manifest_sha256",
            "db_actor",
            "subject",
            "command_digest",
            "idempotency_key",
            "status",
            "review_seq",
            "durable",
            "effective_approval",
            "external_visibility",
            "native_decision",
            "person_id",
            "share_grant",
        }
        if (
            set(d) != required
            or d["contract_version"] != "b3-p0-v1"
            or d["authority"] != AUTHORITY
            or d["status"] not in {"REVIEW_INTENT_TEST_ONLY", "COVERAGE_ACK_TEST_ONLY"}
            or d["effective_approval"] is not False
            or d["external_visibility"] is not False
            or any(d[k] is not None for k in ("native_decision", "person_id", "share_grant"))
            or d["durable"] is not True
            or type(d["review_seq"]) is not int
            or d["review_seq"] != 1
        ):
            raise Denied("B3_RECEIPT_CONTRACT")
        return d
