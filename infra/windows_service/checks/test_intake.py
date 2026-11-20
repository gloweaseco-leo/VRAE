"""Intake syntax and original frozen permission/idempotency compatibility."""
from datetime import datetime, UTC, timedelta
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from infra.windows_service import intake
from integration.authorized_targets.authority import check_submission
from contracts.l2_launch.contract import digest


def consent():
    return {"version":intake.CONSENT,"read_only_authorized":True,"model_data_notice":True}


@pytest.mark.parametrize("url",[
    "http://owner.example.com/","https://127.0.0.1/","https://localhost/",
    "https://owner.example.com:8443/","https://a.internal/","https://a.test/",
    "https://user:password@owner.example.com/","https://owner.example.com/../admin",
])
def test_no_unsafe_url_reaches_dns_or_issuer(url):
    with pytest.raises(Exception):
        intake.scope({"url":url,"paths":[],"consent":consent()})


def test_consent_cannot_be_inferred_from_url_or_invitation():
    with pytest.raises(intake.Denied):
        intake.scope({"url":"https://owner.example.com/","paths":[],"consent":{
            **consent(),"read_only_authorized":False}})
    with pytest.raises(intake.Denied):
        intake.scope({"url":"https://owner.example.com/","paths":["/a","/b","/c"],"consent":consent()})


def test_new_url_submission_passes_original_verifier_and_retries_are_stable(monkeypatch):
    now=datetime.now(UTC)
    end=(now+timedelta(minutes=20)).isoformat()
    policy={"schema_version":"1.0","tenant_id":"tenant-test","policy_id":"policy-domain",
        "policy_version":1,"mode":"OWNER_AUTHORIZED_DEEP","permitted_hosts":["owner.example.com"],
        "scope_paths":["/"],"authorization_reference":"auth-domain","expires_at":end,
        "revoked_at":None,"created_at":(now-timedelta(minutes=1)).isoformat()}
    plan={"tenant_id":"tenant-test","target_id":"target-domain","origin":"https://owner.example.com",
        "exact_paths":["/robots.txt","/"],"policy":policy,"revoked":False,"expires_at":end,
        "execution_profile":"ADMIN_TARGET_V2","authorization_kind":"ADMIN_AUTHORIZED_READONLY"}
    inv={"tenant_id":"tenant-test","subject_ref":"subject-a","reference":"invitation-a",
         "target_ids":["target-domain"],"expires_at":end,"revoked":False}
    actor={"tenant_id":"tenant-test","subject_ref":"subject-a","invitation_ref":"invitation-a","invitation":inv}
    binding={"tenant_id":"tenant-test"}
    private_key=Ed25519PrivateKey.generate()
    monkeypatch.setattr(intake,"key",lambda _:private_key)
    monkeypatch.setattr(intake,"authorization",lambda *a,**k:None)
    monkeypatch.setattr(intake.store,"invoke",lambda *a,**k:{
        "plan":plan,"source_authorization":{},"plan_sha256":"0"*64})
    body={"url":"https://owner.example.com/","idempotency_key":"valid-retry-0001",
          "accepted_at":now.isoformat(),"consent_version":intake.CONSENT,"language":"zh"}
    first=intake.signed_submission(binding,actor,body,"cookie","csrf")
    second=intake.signed_submission(binding,actor,body,"cookie","csrf")
    assert first==second
    keys={"permission":{"public":private_key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex(),
        "tenant":"tenant-test","role":"PERMISSION_AUTHORITY","subject":"vrae-operator-permission","revoked":False}}
    original_intent=check_submission(first,plan,inv,actor,keys)
    assert original_intent==digest(first)
    variant=intake.signed_submission(binding,actor,{**body,"language":"en"},"cookie","csrf")
    assert check_submission(variant,plan,inv,actor,keys)!=original_intent
    with pytest.raises(intake.Denied):
        intake.signed_submission(binding,actor,{**body,"url":"https://owner.example.com/outside"},"cookie","csrf")



def test_signed_deployment_replacement_preserves_read_only_permissions(tmp_path):
    path=tmp_path/"deployment.json"
    path.write_bytes(b"old-signed-document")
    path.chmod(0o444)
    previous=path.stat().st_ino
    intake.replace_deployment(path,b"new-signed-document")
    assert path.read_bytes()==b"new-signed-document"
    assert path.stat().st_ino!=previous
    assert path.stat().st_mode&0o777==0o444
    assert sorted(p.name for p in tmp_path.iterdir())==["deployment.json"]


def test_tcp_dns_still_checks_complete_a_and_aaaa_answers(monkeypatch):
    import asyncio
    from integration.authorized_targets.dns_transport import DNSResolver
    import dns.asyncresolver
    from vrae.collection.errors import CollectionError
    calls=[]
    class Answers:
        async def resolve(self,host,kind,**kwargs):
            calls.append((host,kind,kwargs["tcp"]))
            return ["93.184.216.20"] if kind=="A" else ["::1"]
    resolver=DNSResolver(["8.8.8.8"],tcp=True)
    monkeypatch.setattr(dns.asyncresolver.Resolver,"resolve",Answers.resolve)
    with pytest.raises(CollectionError,match="SSRF_BLOCKED"):
        asyncio.run(resolver.resolve("owned.example.com"))
    assert calls==[("owned.example.com.","A",True),("owned.example.com.","AAAA",True)]
