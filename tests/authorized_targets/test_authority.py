"""Permission boundaries that need no network or customer credentials."""

from copy import deepcopy
from datetime import datetime, UTC, timedelta
from types import SimpleNamespace
import pytest
from contracts.l2_launch.contract import Refused
from integration.authorized_targets.authority import check_submission, service_binding, token_hash
from integration.authorized_targets.capture import components
from integration.l2_launch.g1.fixtures import submission
from tests.collection.test_security import fixture
from tests.authorized_targets.issuer import Issuer


def setup():
    now = datetime.now(UTC)
    t = "tenant-configured"
    issuer = Issuer(t)
    p = fixture("SourcePolicy")
    p.update(
        tenant_id=t,
        permitted_hosts=["configured.test"],
        authorization_reference="controlled-auth",
        created_at=(now - timedelta(minutes=1)).isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
    )
    request = fixture("AuditRequest")
    request.update(tenant_id=t, site_url="https://configured.test/")
    body, _ = submission(SimpleNamespace(audit=request, policy=p), issuer)
    inv = {
        "tenant_id": t,
        "reference": body["invitation_ref"],
        "subject_ref": body["subject_ref"],
        "target_ids": ["target-configured"],
        "revoked": False,
        "expires_at": p["expires_at"],
    }
    plan = {
        "tenant_id": t,
        "target_id": "target-configured",
        "origin": "https://configured.test",
        "revoked": False,
        "expires_at": p["expires_at"],
        "authorization_kind": "CONTROLLED_NON_CUSTOMER",
        "policy": p,
        "terms_reference": "controlled-terms",
        "exact_paths": ["/", "/robots.txt"],
        "retain_raw_html": False,
    }
    actor = {"tenant_id": t, "subject_ref": body["subject_ref"]}
    return body, plan, inv, actor, issuer


def test_configured_tenant_is_not_fixed_fixture_tenant():
    body, plan, inv, actor, issuer = setup()
    assert len(check_submission(body, plan, inv, actor, issuer.public())) == 64


@pytest.mark.parametrize(
    "change", ["subject", "tenant", "target", "expired", "revoked", "signature", "l2"]
)
def test_authority_denials(change):
    body, plan, inv, actor, issuer = setup()
    if change == "subject":
        actor["subject_ref"] = "different-subject"
    if change == "tenant":
        actor["tenant_id"] = "tenant-other"
    if change == "target":
        inv["target_ids"] = []
    if change == "expired":
        inv["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    if change == "revoked":
        inv["revoked"] = True
    if change == "signature":
        body["language"] = "en"
    if change == "l2":
        body["command"]["request"]["audit_mode"] = "L2"
    with pytest.raises(Refused):
        check_submission(body, plan, inv, actor, issuer.public())


def test_self_asserted_customer_egress_flags_never_enable_connections():
    body, plan, inv, actor, issuer = setup()
    plan["authorization_kind"] = "EXPLICIT_CUSTOMER_AUTHORIZATION"
    flags = {
        "kind": "AUTHORIZED_CUSTOMER_EGRESS",
        "deadline": plan["expires_at"],
        "owner_deployment_go": True,
        "target_legal_authorization_verified": True,
        "parent_firewall_attested": True,
    }
    with pytest.raises(PermissionError, match="LIVE_CAPTURE_DISABLED"):
        components(
            body["command"]["request"], lambda: plan["policy"], plan, "run-configured", flags
        )


def test_service_bindings_cannot_be_selected_by_request_tenant():
    a = {"tenant_id": "tenant-alpha", "service_sha256": token_hash("one")}
    b = {"tenant_id": "tenant-beta", "service_sha256": token_hash("two")}
    assert service_binding("Bearer one", [a, b]) is a
    with pytest.raises(Refused):
        service_binding("Bearer other", [a, b])
    with pytest.raises(Refused):
        service_binding("Bearer one", [a, deepcopy(a)])
