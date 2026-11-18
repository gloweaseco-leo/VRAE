"""R0 offline contract predicates. No HTTP, real identity, approval or VF adapter.

Signed fixture assertions demonstrate the proposed trust ports, not formal
human review. Live availability stays closed pending Owner G0 and R1 adapters.
"""

from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

from vrae.domain.contracts import load_schema, validate_contract
from vrae.domain.errors import DomainError
from vrae.domain.policy import authorize_source, parse_time
from vrae.domain.reviews import check_share
from vrae.collection.policy import canonical_url
from vrae.collection.errors import CollectionError

VERSION = "vf-vrae-r0.1"
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((Path(__file__).parent / "schema.json").read_text(encoding="utf-8"))
VFB_SCHEMA = json.loads((Path(__file__).parent / "vf-b.schema.json").read_text(encoding="utf-8"))
resources = [
    SCHEMA,
    VFB_SCHEMA,
    *(
        json.loads(p.read_text(encoding="utf-8"))
        for p in (ROOT / "contracts/v1").glob("*.schema.json")
    ),
]
REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in resources)


class Refused(ValueError):
    def __init__(self, code, status=403, retryable=False):
        self.code, self.status, self.retryable = code, status, retryable
        super().__init__(code)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate(name, value):
    schema = SCHEMA if name in SCHEMA["$defs"] else VFB_SCHEMA
    if name not in schema["$defs"]:
        raise Refused("R0_WRONG_CONTRACT", 400)
    try:
        canonical(value)
        Draft202012Validator(
            {"$ref": schema["$id"] + "#/$defs/" + name},
            registry=REGISTRY,
            format_checker=FormatChecker(),
        ).validate(value)
    except (ValidationError, ValueError, TypeError):
        raise Refused("R0_WRONG_CONTRACT", 400) from None


def domain_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except DomainError as error:
        conflict = error.code in {
            "REPORT_VERSION_STALE",
            "IDEMPOTENCY_CONFLICT",
            "INVALID_TRANSITION",
        }
        raise Refused(error.code, 409 if conflict else 403) from None


@dataclass(frozen=True)
class TrustedFixtureKey:
    """Test registry input, never a key/role accepted from a request body."""

    public_key: bytes
    tenant_id: str
    subject_ref: str
    role: str
    revoked: bool = False


class FixtureVerifier:
    """Real Ed25519 over synthetic assertions; not a real human-ID resolver."""

    ROLES = {
        "permission": {"PERMISSION_AUTHORITY"},
        "review": {"REVIEWER", "OWNER"},
        "share": {"OWNER"},
        "vf_storage": {"VF_STORAGE_SERVICE"},
        "vf_qualification": {"OWNER"},
    }

    def __init__(self, trusted_keys):
        self.keys = dict(trusted_keys)

    def verify(self, proof, purpose, document, tenant, now):
        validate("Attestation", proof)
        key = self.keys.get(proof["key_id"])
        claim = proof["claim"]
        if (
            key is None
            or key.revoked
            or key.role not in self.ROLES[purpose]
            or key.tenant_id != tenant
            or claim["tenant_id"] != tenant
            or claim["purpose"] != purpose
            or claim["subject_ref"] != key.subject_ref
            or claim["document_sha256"] != digest(document)
            or now.tzinfo is None
            or parse_time(claim["issued_at"]) > now
            or parse_time(claim["expires_at"]) <= now
        ):
            raise Refused("R0_ATTESTATION_DENIED")
        unsigned = {k: v for k, v in proof.items() if k != "signature"}
        try:
            Ed25519PublicKey.from_public_bytes(key.public_key).verify(
                bytes.fromhex(proof["signature"]), canonical(unsigned)
            )
        except Exception:
            raise Refused("R0_ATTESTATION_DENIED") from None
        return key


def availability():
    return {
        "contract_version": VERSION,
        "state": "NOT_AVAILABLE",
        "submit_enabled": False,
        "report_enabled": False,
        "reason": "G0_NOT_FROZEN_NO_LIVE_ADAPTER",
    }


def permission_document(command, policy):
    ref = command["permission_reference"]
    return {
        "contract_version": VERSION,
        "request": command["request"],
        "scope_sha256": digest(
            {
                k: policy[k]
                for k in ("mode", "permitted_hosts", "scope_paths", "authorization_reference")
            }
        ),
        "reference": ref["reference"],
        "consent_version": ref["consent_version"],
        "consent_sha256": ref["consent_sha256"],
    }


def check_permission(command, policy, caller, verifier, now):
    validate("AuditCommand", command)
    req = command["request"]
    if caller.get("tenant_id") != req["tenant_id"]:
        raise Refused("FORBIDDEN_TENANT")
    if caller.get("role") not in {"OWNER", "SERVICE"}:
        raise Refused("FORBIDDEN_ROLE")
    if policy is None:
        raise Refused("POLICY_REQUIRED")
    validate_contract("SourcePolicy", policy)
    domain_call(authorize_source, req, policy, now)
    try:
        canonical_url(req["site_url"])  # syntax only, no DNS/HTTP/collector execution
    except CollectionError:
        raise Refused("SOURCE_NOT_ALLOWED") from None
    ref = command["permission_reference"]
    if policy["authorization_reference"] != ref["reference"]:
        raise Refused("POLICY_REQUIRED")
    verifier.verify(
        ref["proof"], "permission", permission_document(command, policy), req["tenant_id"], now
    )


STATE_MAP = {
    "CREATED": "PENDING",
    "POLICY_CHECK": "PENDING",
    "QUEUED": "PENDING",
    "FETCHING": "IN_PROGRESS",
    "EVIDENCE_READY": "IN_PROGRESS",
    "RULED": "IN_PROGRESS",
    "DRAFT_READY": "REVIEW_PENDING",
    "REVIEW_REQUIRED": "REVIEW_PENDING",
    "POLICY_BLOCKED": "BLOCKED",
    "ACCESS_BLOCKED": "BLOCKED",
    "INSUFFICIENT_EVIDENCE": "UNKNOWN",
    "MODEL_INVALID": "UNKNOWN",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
}


def status_view(run, withdrawn=False):
    validate_contract("AuditRun", run)
    result = {
        "contract_version": VERSION,
        "run": run,
        "access_state": "WITHDRAWN" if withdrawn else "ACTIVE",
        "presentation": {
            "state": "CANCELLED" if withdrawn else STATE_MAP[run["status"]],
            "progress_percent": None,
            "scope": "AUTHORIZED_PAGES_ONLY",
        },
    }
    validate("AuditStatus", result)
    return result


def validate_projection(view):
    validate("ReportView", view)
    if view["view_type"] == "ApprovedL2ReportView" and view["audit_mode"] != "L2":
        raise Refused("R0_VIEW_TIER_MISMATCH")
    if view["view_type"] == "PublicPreviewView" and view["audit_mode"] != "L1":
        raise Refused("R0_VIEW_TIER_MISMATCH")
    if view["coverage"]["observed_pages"] > view["coverage"]["authorized_pages"]:
        raise Refused("R0_COVERAGE_MISMATCH")
    seen = set()
    for citation in view["citations"]:
        parts = urlsplit(citation["source_url"])
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or citation["citation_id"] in seen
        ):
            raise Refused("R0_CITATION_DENIED")
        seen.add(citation["citation_id"])
    for summary in view["summary"].values():
        if not set(summary["citation_ids"]) <= seen:
            raise Refused("EVIDENCE_REFERENCE_INVALID")
        if summary["basis"] == "OBSERVATION" and (
            not summary["citation_ids"] or not view["coverage"]["observed_pages"]
        ):
            raise Refused("EVIDENCE_INSUFFICIENT")
    # A deny scan supplements explicit field allowlists and signed redaction;
    # it does not establish that arbitrary text is safe for public release.
    scan = canonical(view).decode()
    if re.search(
        r"-----BEGIN|\bBearer\s|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.|[\w.+-]+@[\w.-]+", scan
    ):
        raise Refused("R0_PUBLIC_PROJECTION_DENIED")


def simulate_report_read(bundle, principal, bearer, verifier, now, *, current_grant):
    """Pure fixture consumer; production must keep availability NOT_AVAILABLE.

    Review/Owner fixtures are not formal human review or actual ShareGrants.
    A future authenticated adapter must establish those independently.
    """
    if now.tzinfo is None:
        raise Refused("R0_AWARE_CLOCK_REQUIRED")
    report, decision, grant, view = (bundle[k] for k in ("report", "decision", "grant", "view"))
    check_permission(
        bundle["source_command"], bundle["source_policy"], bundle["source_caller"], verifier, now
    )
    run = bundle["run"]
    validate_contract("AuditRun", run)
    req = bundle["source_command"]["request"]
    if (
        run["status"] != "REVIEW_REQUIRED"
        or req["audit_mode"] != report["audit_mode"]
        or any(run[k] != req[k] for k in ("tenant_id", "audit_id", "request_id"))
        or run["run_id"] != report["run_id"]
        or view["audit_id"] != run["audit_id"]
        or run["tenant_id"] != report["tenant_id"]
        or run["input_hash"] != digest(req)
    ):
        raise Refused("REPORT_NOT_APPROVED")
    for name, value in [
        ("ReportVersion", report),
        ("ReviewDecision", decision),
        ("ShareGrant", grant),
    ]:
        validate_contract(name, value)
    validate_projection(view)
    for citation in view["citations"]:
        try:
            canonical_url(citation["source_url"])
        except CollectionError:
            raise Refused("R0_CITATION_DENIED") from None
        domain_call(
            authorize_source,
            {**req, "site_url": citation["source_url"]},
            bundle["source_policy"],
            now,
        )
        if (
            not parse_time(bundle["source_policy"]["created_at"])
            <= parse_time(citation["captured_at"])
            <= now
        ):
            raise Refused("R0_CITATION_DENIED")
    tenant = report["tenant_id"]
    if current_grant != {"grant": grant, "view_sha256": digest(view)}:
        raise Refused("SHARE_EXPIRED")
    if principal.get("tenant_id") != tenant:
        raise Refused("FORBIDDEN_TENANT")
    if (
        principal.get("audience") != "vrae-report"
        or principal.get("token_revoked") is not False
        or not principal.get("expires_at")
        or parse_time(principal["expires_at"]) <= now
        or principal.get("subject_ref") != grant["subject_ref"]
        or not bearer
        or not hmac.compare_digest(hashlib.sha256(bearer.encode()).hexdigest(), grant["token_hash"])
    ):
        raise Refused("FORBIDDEN_ROLE")
    reviewer = verifier.verify(bundle["review_proof"], "review", decision, tenant, now)
    owner = verifier.verify(
        bundle["share_proof"], "share", {"grant": grant, "view_sha256": digest(view)}, tenant, now
    )
    if reviewer.subject_ref != decision["reviewer_id"]:
        raise Refused("FORBIDDEN_ROLE")
    domain_call(
        check_share,
        report,
        decision,
        grant,
        {"role": owner.role, "actor_id": owner.subject_ref, "tenant_id": tenant},
        bundle["latest_version"],
        now,
        report["audit_mode"],
        findings=bundle["findings"],
    )
    if any(
        view[k] != report[k]
        for k in (
            "tenant_id",
            "run_id",
            "report_id",
            "report_version_id",
            "version",
            "content_hash",
            "audit_mode",
        )
    ):
        raise Refused("REPORT_VERSION_STALE", 409)
    return {"scope": "SYNTHETIC_CONTRACT_FIXTURE_NOT_A_RELEASE", "view": view}


def error_reply(error, request_id):
    legacy = None
    if error.code in load_schema("ErrorCode")["properties"]["code"]["enum"]:
        legacy = {
            "schema_version": "1.0",
            "code": error.code,
            "safe_message": "Request refused.",
            "request_id": request_id,
            "retryable": error.retryable,
        }
    body = {
        "contract_version": VERSION,
        "http_status": error.status,
        "request_id": request_id,
        "code": error.code,
        "retryable": error.retryable,
        "retry_after_seconds": 60 if error.status == 429 else None,
        "v1_error": legacy,
    }
    validate("Error", body)
    return body
