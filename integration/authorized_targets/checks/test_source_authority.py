"""Exact source/admin permissions; production and controlled realms never mix."""

from copy import deepcopy
from datetime import datetime, UTC, timedelta
import asyncio
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from contracts.l2_launch.contract import canonical
from integration.authorized_targets import source_authority as authority
from integration.authorized_targets.egress import ScopedResolver
from vrae.collection.errors import CollectionError


@pytest.fixture
def grant(monkeypatch):
    key = Ed25519PrivateKey.generate()
    now = datetime.now(UTC)
    registry = {
        "keys": {
            "admin": {
                "public": key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
                "role": "SOURCE_ADMIN",
                "source_class": "CONTROLLED_NON_CUSTOMER",
                "revoked": False,
            }
        }
    }
    monkeypatch.setattr(authority, "root_document", lambda path: registry)
    plan = {
        "tenant_id": "tenant-configurable",
        "target_id": "target-configurable",
        "source_class": "CONTROLLED_NON_CUSTOMER",
        "origin": "https://configured.test",
        "exact_paths": ["/", "/robots.txt"],
        "limits": {"task_seconds": 20},
        "terms_reference": "controlled-terms",
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "policy": {"authorization_reference": "controlled-authority"},
    }
    doc = {
        k: deepcopy(plan[k])
        for k in ("tenant_id", "target_id", "source_class", "origin", "exact_paths", "limits")
    }
    doc.update(
        contract="vrae.target-authorization.v2",
        reference="controlled-authority",
        plan_sha256="1" * 64,
        purpose="READONLY_DIAGNOSIS",
        methods=["GET", "HEAD"],
        legal_reference="controlled-noncustomer-ownership",
        terms_reference="controlled-terms",
        robots="ENFORCE",
        not_before=(now - timedelta(minutes=1)).isoformat(),
        expires_at=plan["expires_at"],
        retention_until=(now + timedelta(hours=2)).isoformat(),
        destination_ips=["93.184.216.20"],
    )

    def sign(d):
        return {"key_id": "admin", "document": d, "signature": key.sign(canonical(d)).hex()}

    return plan, doc, registry, sign


def test_signed_exact_target_activates(grant):
    plan, doc, registry, sign = grant
    assert authority.authorization(sign(doc), plan, plan_sha256="1" * 64) == doc


@pytest.mark.parametrize(
    "field,value",
    [
        ("origin", "https://other.test"),
        ("tenant_id", "tenant-other"),
        ("target_id", "other-target"),
        ("exact_paths", ["/", "/robots.txt", "/extra"]),
        ("purpose", "BROAD_CRAWL"),
        ("methods", ["POST"]),
        ("terms_reference", "other-terms"),
        ("robots", "IGNORE"),
        ("legal_reference", ""),
        ("plan_sha256", "2" * 64),
        ("destination_ips", ["169.254.169.254"]),
        ("limits", {"task_seconds": 120}),
    ],
)
def test_even_signed_scope_cannot_widen_plan(grant, field, value):
    plan, doc, registry, sign = grant
    doc[field] = value
    with pytest.raises((authority.AuthorityDenied, CollectionError)):
        authority.authorization(sign(doc), plan, plan_sha256="1" * 64)


def test_signature_tamper_revoked_and_foreign_keys(grant):
    plan, doc, registry, sign = grant
    envelope = sign(doc)
    envelope["document"]["purpose"] = "changed"
    with pytest.raises(authority.AuthorityDenied):
        authority.authorization(envelope, plan, plan_sha256="1" * 64)
    envelope = sign(doc)
    registry["keys"]["admin"]["revoked"] = True
    with pytest.raises(authority.AuthorityDenied):
        authority.authorization(envelope, plan, plan_sha256="1" * 64)


def test_controlled_key_cannot_authorize_customer(grant):
    plan, doc, registry, sign = grant
    plan["source_class"] = doc["source_class"] = "CUSTOMER"
    with pytest.raises(authority.AuthorityDenied):
        authority.authorization(sign(doc), plan, plan_sha256="1" * 64)


@pytest.mark.parametrize("field,delta", [("expires_at", -2), ("not_before", 120)])
def test_time_window_is_current(grant, field, delta):
    plan, doc, registry, sign = grant
    doc[field] = (datetime.now(UTC) + timedelta(seconds=delta)).isoformat()
    with pytest.raises(authority.AuthorityDenied):
        authority.authorization(sign(doc), plan, plan_sha256="1" * 64)


def test_dns_entire_answer_must_fit_signed_addresses():
    r = ScopedResolver(["93.184.216.53"], ["93.184.216.20"])

    class Rotated:
        async def resolve(self, host):
            return ("93.184.216.20", "93.184.216.21")

    r.resolver = Rotated()
    with pytest.raises(CollectionError, match="SSRF_BLOCKED"):
        asyncio.run(r.resolve("configured.test"))
