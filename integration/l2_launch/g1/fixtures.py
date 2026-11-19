"""New per-run synthetic VF requests, signed by separate trusted fixture authority."""

from copy import deepcopy
from datetime import datetime, UTC, timedelta
import hashlib
import secrets
from uuid import uuid4
from contracts.l2_launch.contract import VERSION as CORE, digest, permission_document, validate
from contracts.l2_launch.vf_b import VERSION, submission_document


def submission(plan, authority):
    now = datetime.now(UTC)
    uid = uuid4().hex
    request = deepcopy(plan.audit)
    request.update(
        request_id="vf-request-" + uid,
        audit_id="vf-audit-" + uid,
        idempotency_key="g1-idem-" + uid,
        requested_at=now.isoformat(),
    )
    command = {
        "contract_version": CORE,
        "request": request,
        "permission_reference": {
            "reference": plan.policy["authorization_reference"],
            "consent_version": "G1-SYNTHETIC-SCAN-CONSENT-1",
            "consent_sha256": digest("G1 synthetic diagnosis consent; no real target permission"),
        },
    }
    command["permission_reference"]["proof"] = authority.sign(
        "permission", "permission", permission_document(command, plan.policy)
    )
    value = {
        "contract_version": VERSION,
        "command": command,
        "normalized_host": request["site_url"].split("/")[2],
        "language": "zh",
        "subject_ref": "g1-recipient-" + uid,
        "invitation_ref": "g1-invitation-" + uid,
        "diagnosis_consent": {
            "consent_version": command["permission_reference"]["consent_version"],
            "accepted_at": now.isoformat(),
            "text_sha256": command["permission_reference"]["consent_sha256"],
        },
    }
    value["submission_proof"] = authority.sign(
        "permission", "permission", submission_document(value)
    )
    invitation = {
        "tenant_id": "tenant-test",
        "subject_ref": value["subject_ref"],
        "policy_sha256": digest(plan.policy),
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
        "revoked": False,
        "request_sha256": digest(request),
    }
    validate("VFSubmit", value)
    return value, invitation


def return_grant(ref, subject, policy, authority, *, seconds=240):
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    grant = {
        "contract_version": VERSION,
        "tenant_id": "tenant-test",
        "audit_ref": ref,
        "subject_ref": subject,
        "audience": "vf-bff-return",
        "purpose": "DIAGNOSIS_RETURN_ONLY",
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        "policy_sha256": digest(policy),
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=seconds)).isoformat(),
        "revoked": False,
    }
    validate("VFReturnGrant", grant)
    return token, grant, authority.sign("owner", "share", grant)
