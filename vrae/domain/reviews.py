"""Immutable report approval and revocable sharing contract."""

from datetime import datetime

from .access import require_access
from .errors import DomainError
from .policy import parse_time


def approve_version(
    report: dict, decision: dict, actor: dict, current_version: int,
    verified_finding_ids: set[str],
) -> dict:
    require_access(actor, report["tenant_id"], "review")
    if (not report["finding_ids"]
            or not set(report["finding_ids"]) <= verified_finding_ids):
        raise DomainError("EVIDENCE_INSUFFICIENT", "No verified findings for approval")
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
    latest_version: int, now: datetime, audit_mode: str,
) -> None:
    if audit_mode not in ("L1", "L2"):
        raise DomainError("SOURCE_NOT_ALLOWED", "L0 and unknown tiers cannot be shared")
    require_access(actor, report["tenant_id"], "share")
    if any(x["tenant_id"] != report["tenant_id"] for x in (decision, grant)):
        raise DomainError("FORBIDDEN_TENANT", "Share is cross-tenant")
    if report["status"] != "APPROVED" or decision["action"] != "APPROVE":
        raise DomainError("REPORT_NOT_APPROVED", "Report has not been approved")
    if (report["version"] != latest_version
            or decision["version"] != latest_version):
        raise DomainError("REPORT_VERSION_STALE", "Share references older version")
    if any(x["report_version_id"] != report["report_version_id"] for x in (decision, grant)):
        raise DomainError("REPORT_VERSION_STALE", "Share report version mismatch")
    if (decision["content_hash"] != report["content_hash"]
            or grant["content_hash"] != report["content_hash"]):
        raise DomainError("REPORT_VERSION_STALE", "Share content hash mismatch")
    if (grant["status"] != "ACTIVE" or grant["revoked_at"] is not None
            or parse_time(grant["expires_at"]) <= now
            or parse_time(grant["issued_at"]) > now):
        raise DomainError("SHARE_EXPIRED", "Share is expired/revoked/not yet valid")
    if not grant["subject_ref"] or len(grant["token_hash"]) != 64:
        raise DomainError("SOURCE_NOT_ALLOWED", "Invalid grant details")


def validate_existing_grant(grant: dict, now: datetime) -> None:
    if (grant["status"] != "ACTIVE" or grant["revoked_at"] is not None
            or parse_time(grant["expires_at"]) <= now):
        raise DomainError("SHARE_EXPIRED", "Grant expired or revoked")
