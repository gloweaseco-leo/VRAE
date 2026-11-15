"""Closed bounded canonical DTOs. Valid bytes are NOT proof of current authority."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from vrae.reviewing.canonical import canonical as _canonical, parse as _parse, sha

LIMIT = 131072
ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = "TEST_ONLY_PRIVATE_PREVIEW"
WARNINGS = ["SYNTHETIC_ONLY", "NOT_APPROVED", "COVERAGE_LIMITED", "UNCHECKED_SCOPE_UNKNOWN",
            "NO_REAL_RECIPIENT", "NO_DELIVERY_PERMISSION"]
CLASSIFICATIONS = {"pins": "REVIEWER_ONLY", "findings": "INTERNAL_PREVIEW_ONLY",
                   "coverage": "INTERNAL_PREVIEW_ONLY", "recipient_policy": "REVIEWER_ONLY",
                   "private_html_sha256": "REVIEWER_ONLY",
                   "prospective_owner_fields": ["finding_count", "scope_warning_codes"],
                   "owner_visible_now": []}


class B6Denied(ValueError):
    """Only fixed non-reflective codes may cross this private boundary."""


def deny(code="B6_INPUT_DENIED"):
    raise B6Denied(code) from None


def canonical(value):
    try:
        return _canonical(value, limit=LIMIT)
    except Exception:
        deny()


def parse(raw):
    try:
        value = _parse(raw, limit=LIMIT)
        if canonical(value) != raw:
            deny()
        return value
    except Exception:
        deny()


@lru_cache(maxsize=3)
def validator(name):
    # All references are local #/$defs; no URL resolution or remote schema IO.
    names = {"B6PrivateHandoffCandidate", "B6VFIntendedEnvelope", "B6PrivateDenialReceipt"}
    if name not in names:
        deny()
    schema = _parse((ROOT / "contracts/b6_p0" / (name + ".schema.json")).read_bytes(),
                    limit=262144)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate(name, value):
    try:
        if not validator(name).is_valid(value):
            deny()
    except B6Denied:
        raise
    except Exception:
        deny()


@dataclass(frozen=True)
class Candidate:
    """Shape/content binding only; revalidate through PrivateHandoffReader.verify."""

    payload: bytes

    def __post_init__(self):
        self.document

    @property
    def document(self):
        d = parse(self.payload)
        validate("B6PrivateHandoffCandidate", d)
        core = {k: v for k, v in d.items() if k != "content_digest"}
        if sha(canonical(core)) != d["content_digest"]:
            deny("B6_SOURCE_BINDING_DENIED")
        if d["recipient_policy"]["tenant_id"] != d["pins"]["tenant_id"]:
            deny("B6_SOURCE_BINDING_DENIED")
        refs = []
        for cite in [r["citation"] for r in d["findings"]] + d["coverage"]["claims"]:
            if cite["byte_end"] <= cite["byte_start"] or cite["guard_ref"] not in d["pins"]["guard_refs"]:
                deny("B6_SOURCE_BINDING_DENIED")
            refs.append(cite["claim_pointer"])
        if len(refs) != len(set(refs)):
            deny("B6_SOURCE_BINDING_DENIED")
        return d


@dataclass(frozen=True)
class IntendedEnvelope:
    payload: bytes

    def __post_init__(self):
        self.document

    @property
    def document(self):
        d = parse(self.payload)
        validate("B6VFIntendedEnvelope", d)
        basis = [d["tenant_id"], d["report_id"], d["report_version"], d["candidate_digest"]]
        correlation = "b6cor-" + sha(canonical(basis))
        if (d["correlation_id"] != correlation
                or d["consumer_idempotency_key"] != "b6p0-" + sha(canonical([correlation, d["candidate_digest"]]))):
            deny("B6_SOURCE_BINDING_DENIED")
        return d
