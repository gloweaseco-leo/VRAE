"""Immutable report approval and revocable sharing contract."""

from datetime import datetime
import hashlib
import json
import re

from .access import require_access
from .errors import DomainError
from .policy import parse_time


def report_content_hash(report: dict, findings: list[dict]) -> str:
    """Hash the RA-0 report manifest and exact finding contents, not rendered text.

    Inputs must come from trusted repositories after graph validation. This is
    content binding, not identity authentication or natural-language validation.
    RA-3 must additionally bind all rendered content and model/rule provenance.
    """
    if not isinstance(findings, list) or not all(isinstance(f, dict) for f in findings):
        raise DomainError("EVIDENCE_INSUFFICIENT", "Scoped finding records required")
    by_id = {}
    for finding in findings:
        if finding["tenant_id"] != report["tenant_id"]:
            raise DomainError("FORBIDDEN_TENANT", "Cross-tenant report finding")
        if finding["run_id"] != report["run_id"]:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Cross-run report finding")
        if finding["finding_id"] in by_id:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Ambiguous finding ID")
        by_id[finding["finding_id"]] = finding
    if not report["finding_ids"] or not set(report["finding_ids"]) <= by_id.keys():
        raise DomainError("EVIDENCE_INSUFFICIENT", "No resolved findings for approval")
    manifest = {k: v for k, v in report.items()
                if k not in {"content_hash", "status", "approved_by", "approved_at"}}
    payload = {"report": manifest, "findings": [by_id[k] for k in report["finding_ids"]]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def approve_version(
    report: dict, decision: dict, actor: dict, current_version: int,
    verified_findings: list[dict],
) -> dict:
    require_access(actor, report["tenant_id"], "review")
    digest = report_content_hash(report, verified_findings)
    if report["content_hash"] != digest:
        raise DomainError("REPORT_VERSION_STALE", "Report content has changed")
    if decision["tenant_id"] != report["tenant_id"]:
        raise DomainError("FORBIDDEN_TENANT", "Decision tenant mismatch")
    if (report["status"] not in {"DRAFT", "REVIEW_REQUIRED"}
            or decision["action"] != "APPROVE"):
        raise DomainError("REVIEW_REQUIRED", "Not an approvable version")
    if report["version"] != current_version or decision["version"] != current_version:
        raise DomainError("REPORT_VERSION_STALE", "Report version has changed")
    if (decision["report_version_id"] != report["report_version_id"]
            or decision["content_hash"] != report["content_hash"]):
        raise DomainError("REPORT_VERSION_STALE", "Report content does not match")
    if decision["reviewer_id"] != actor.get("actor_id"):
        raise DomainError("FORBIDDEN_ROLE", "Decision was not made by actor")
    return {
        **report, "status": "APPROVED", "approved_by": actor["actor_id"],
        "approved_at": decision["decided_at"],
    }


def check_share(
    report: dict, decision: dict, grant: dict, actor: dict,
    latest_version: int, now: datetime, audit_mode: str, *, findings: list[dict],
) -> None:
    if now.tzinfo is None:
        raise DomainError("SOURCE_NOT_ALLOWED", "Aware clock required")
    if audit_mode not in ("L1", "L2") or report["audit_mode"] != audit_mode:
        raise DomainError("SOURCE_NOT_ALLOWED", "L0 and unknown tiers cannot be shared")
    require_access(actor, report["tenant_id"], "share")
    if any(x["tenant_id"] != report["tenant_id"] for x in (decision, grant)):
        raise DomainError("FORBIDDEN_TENANT", "Share is cross-tenant")
    if report["status"] != "APPROVED" or decision["action"] != "APPROVE":
        raise DomainError("REPORT_NOT_APPROVED", "Report has not been approved")
    if (report["approved_by"] != decision["reviewer_id"]
            or report["approved_at"] != decision["decided_at"]):
        raise DomainError("REPORT_NOT_APPROVED", "Approval attribution mismatch")
    if report["content_hash"] != report_content_hash(report, findings):
        raise DomainError("REPORT_VERSION_STALE", "Report content has changed")
    if (report["version"] != latest_version
            or decision["version"] != latest_version):
        raise DomainError("REPORT_VERSION_STALE", "Share references older version")
    if any(x["report_version_id"] != report["report_version_id"] for x in (decision, grant)):
        raise DomainError("REPORT_VERSION_STALE", "Share report version mismatch")
    if (decision["content_hash"] != report["content_hash"]
            or grant["content_hash"] != report["content_hash"]):
        raise DomainError("REPORT_VERSION_STALE", "Share content hash mismatch")
    validate_existing_grant(grant, now)
    if not grant["subject_ref"] or not re.fullmatch(r"[a-f0-9]{64}", grant["token_hash"]):
        raise DomainError("SOURCE_NOT_ALLOWED", "Invalid grant details")


def validate_existing_grant(grant: dict, now: datetime) -> None:
    """Time/revocation predicate only; access must also call check_share."""
    if now.tzinfo is None:
        raise DomainError("SOURCE_NOT_ALLOWED", "Aware clock required")
    if (grant["status"] != "ACTIVE" or grant["revoked_at"] is not None
            or parse_time(grant["expires_at"]) <= now
            or parse_time(grant["issued_at"]) > now):
        raise DomainError("SHARE_EXPIRED", "Grant expired or revoked")
