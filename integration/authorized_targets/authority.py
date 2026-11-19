"""Configured issuer/tenant bindings; invitations never grant report release."""

from datetime import datetime, UTC
import hashlib
import hmac
from contracts.l2_launch.contract import Refused, digest, validate, check_permission
from contracts.l2_launch.vf_b import submission_document
from integration.l2_launch.g1.fixture_keys import verifier


def now():
    return datetime.now(UTC)


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def check_submission(body, plan, invitation, principal, keys):
    validate("VFSubmit", body)
    request = body["command"]["request"]
    if principal["tenant_id"] != plan["tenant_id"] or request["audit_mode"] not in ("L0", "L1"):
        raise Refused("SOURCE_NOT_ALLOWED")
    policy = plan["policy"]
    if plan["revoked"] or now() >= datetime.fromisoformat(plan["expires_at"]):
        raise Refused("POLICY_REQUIRED")
    if (
        invitation["revoked"]
        or invitation["tenant_id"] != principal["tenant_id"]
        or invitation["subject_ref"] != principal["subject_ref"]
        or body["subject_ref"] != principal["subject_ref"]
        or body["invitation_ref"] != invitation["reference"]
        or plan["target_id"] not in invitation["target_ids"]
        or now() >= datetime.fromisoformat(invitation["expires_at"])
    ):
        raise Refused("FORBIDDEN_ROLE")
    if request["site_url"] != plan["origin"] + "/":
        raise Refused("SOURCE_NOT_ALLOWED")
    if plan.get("execution_profile") == "ADMIN_TARGET_V2":
        if plan["authorization_kind"] != "ADMIN_AUTHORIZED_READONLY":
            raise Refused("POLICY_REQUIRED")
    elif plan["authorization_kind"] not in (
        "CONTROLLED_NON_CUSTOMER",
        "EXPLICIT_CUSTOMER_AUTHORIZATION",
    ):
        raise Refused("POLICY_REQUIRED")
    # Permission and independent diagnostic consent remain the frozen G0 ports.
    check_permission(
        body["command"],
        policy,
        {
            "tenant_id": principal["tenant_id"],
            "actor_id": principal["subject_ref"],
            "role": "SERVICE",
        },
        verifier(keys),
        now(),
    )
    consent = body["diagnosis_consent"]
    permission = body["command"]["permission_reference"]
    if (
        consent["consent_version"] != permission["consent_version"]
        or consent["text_sha256"] != permission["consent_sha256"]
    ):
        raise Refused("POLICY_REQUIRED")
    if (
        not datetime.fromisoformat(policy["created_at"])
        <= datetime.fromisoformat(consent["accepted_at"])
        <= now()
    ):
        raise Refused("POLICY_REQUIRED")
    verifier(keys).verify(
        body["submission_proof"],
        "permission",
        submission_document(body),
        principal["tenant_id"],
        now(),
    )
    return digest(body)


def service_binding(header, bindings):
    if type(header) is not str or not header.startswith("Bearer "):
        raise Refused("FORBIDDEN_ROLE")
    value = header[7:]
    found = [
        entry
        for entry in bindings
        if hmac.compare_digest(token_hash(value), entry["service_sha256"])
    ]
    if len(found) != 1:
        raise Refused("FORBIDDEN_ROLE")
    return found[0]
