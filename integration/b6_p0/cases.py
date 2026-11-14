"""Actual PG16 reads and unchanged DB fingerprints around each P0 operation."""

from copy import deepcopy
from dataclasses import replace
import time
import pytest

from vrae.b6_p0 import Candidate, DeliveryAuthorizationGate, B6Denied, intended_envelope
from vrae.b6_p0.contracts import canonical, parse, sha
from vrae.b6_p0.preview import render
from vrae.b6_p0.delivery import OPERATIONS
from .support import no_egress


def reseal(d):
    d=deepcopy(d)
    d.pop("content_digest",None)
    d.pop("private_html_sha256",None)
    html=render(d)
    d["private_html_sha256"]=sha(html)
    d["content_digest"]=sha(canonical(d))
    return canonical(d),html


@pytest.mark.parametrize("case",["404","200"])
def test_actual_signed_reviewer_original_roundtrip_no_writes(runtime,case):
    sid=runtime.login(case)
    before=runtime.fingerprint()
    with no_egress() as attempts:
        package=runtime.service.prepare(sid)
        assert runtime.service.verify(sid,package.candidate.payload,package.private_html)==package
        envelope=intended_envelope(package.candidate)
        gate=DeliveryAuthorizationGate()
        assert parse(gate.consume_intended_envelope(envelope.payload))["decision"]=="DENY"
    assert attempts==[]
    d=package.candidate.document
    assert len(d["findings"])==(1 if case=="404" else 0)
    assert len(d["coverage"]["claims"])==(2 if case=="404" else 3)
    assert d["pins"]["native_content_hash"] is not None if case=="404" else d["pins"]["native_content_hash"] is None
    binding=runtime.bindings["task-"+case]
    with runtime.reader.request(binding) as snapshot:
        raw=snapshot["raw"]
        assert sha(raw[("HTML","html")])==d["pins"]["original_html_sha256"]
        assert sha(raw[("SOURCE","source")])==d["pins"]["source_sha256"]
        assert sha(raw[("GUARD","guard")])==d["pins"]["guard_sha256"]
        for citation in [f["citation"] for f in d["findings"]]+d["coverage"]["claims"]:
            actual=next(e for e in snapshot["dossier"]["evidence"] if e["pointer"]==citation["claim_pointer"])
            body=actual["body"].encode()
            assert sha(body)==citation["body_sha256"]
            assert sha(body[citation["byte_start"]:citation["byte_end"]])==citation["quote_sha256"]
            assert sha(canonical(actual["claim"]))==citation["claim_sha256"]
        for original in raw.values():
            assert original not in package.candidate.payload and original not in package.private_html
    for secret in runtime.secrets+list(runtime.state["runtime_passwords"].values()):
        assert secret.encode() not in package.candidate.payload+package.private_html
    assert runtime.fingerprint()==before
    runtime.observation={"case":case,"candidate_digest":d["content_digest"],"private_html_sha256":sha(package.private_html),
                         "findings":len(d["findings"]),"coverage_claims":len(d["coverage"]["claims"]),
                         "pins":d["pins"],"classification":d["classifications"],"external_network_attempts":0,
                         "business_mutations":0,"delivery_receipt":parse(gate.sink.records[0])}
    (runtime.private / "candidate.json").write_bytes(package.candidate.payload)
    (runtime.private / "preview.html").write_bytes(package.private_html)
    (runtime.private / "intended-envelope.json").write_bytes(envelope.payload)


@pytest.mark.parametrize("bad",["tenant","report","version","source-run","target","ref","issuer","subject","role",
                                "policy-id","policy-version","policy-expired","policy-revoked","cookie",
                                "anchor-expired","anchor-revoked","assignment"])
def test_wrong_current_subject_scope_policy_or_anchor_denies(runtime,bad):
    sid=runtime.login()
    p=runtime.service.policies["task-404"]
    if bad in {"tenant","report","version","source-run","target","ref"}:
        keys={"tenant":("tenant","tenant-other"),"report":("report","report-other"),"version":("version",2),
              "source-run":("source_run","other-run"),"target":("target_digest","f"*64),"ref":("ref_id","other-ref")}
        key,value=keys[bad]
        p=replace(p,location=replace(p.location,**{key:value}))
    elif bad in {"issuer","subject","role"}:
        p=replace(p,**{bad:"other"})
    elif bad=="policy-id":
        p=replace(p,policy_id="pol-other")
    elif bad=="policy-version":
        p=replace(p,policy_version=2)
    elif bad=="policy-expired":
        p=replace(p,expires=int(time.time())-1)
    elif bad=="policy-revoked":
        p=replace(p,active=False)
    elif bad=="cookie":
        sid="A"*43
    elif bad.startswith("anchor"):
        runtime.store.boundary.anchor=replace(runtime.store.boundary.anchor,**({"expires":int(time.time())-1} if bad=="anchor-expired" else {"available":False}))
    else:
        runtime.store.boundary.assignments=(replace(runtime.bindings["task-404"],active=False),)
    runtime.service.policies["task-404"]=p
    before=runtime.fingerprint()
    with no_egress() as attempts, pytest.raises(B6Denied) as caught:
        runtime.service.prepare(sid)
    assert str(caught.value)=="B6_CURRENT_ACCESS_DENIED" and not attempts
    assert runtime.fingerprint()==before


@pytest.mark.parametrize("sql_text",[
    "UPDATE ra4a_private.principals SET enabled=false WHERE db_role='p2b1_test_a_reviewer'",
    "UPDATE ra4a_private.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'",
    "UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'",
])
def test_revoked_actual_pg_reviewer_cannot_package(runtime,sql_text):
    sid=runtime.login()
    original=runtime.before
    with runtime.connect() as control:
        control.execute(sql_text)
    runtime.before=runtime.fingerprint()
    runtime.observation={"trusted_control_revocation":True,"prior_fingerprint":original,
                         "product_baseline_after_revocation":runtime.before}
    with pytest.raises(B6Denied):
        runtime.service.prepare(sid)
    assert runtime.fingerprint()==runtime.before


@pytest.mark.parametrize("kind",["SOURCE","HTML","GUARD","DRAFT","TARGET","MANIFEST"])
def test_real_pg_original_rejects_altered_independent_pins(runtime,kind):
    sid=runtime.login()
    loc=runtime.bindings["task-404"].location
    pin=runtime.reader.pins[loc]
    if kind=="MANIFEST":
        pin=replace(pin,manifest_sha256="f"*64)
    elif kind=="TARGET":
        pin=replace(pin,target_sha256="f"*64)
    else:
        desc=tuple({**d,"sha256":"f"*64} if d["kind"]==kind else d for d in pin.descriptors)
        pin=replace(pin,descriptors=desc)
    runtime.reader.pins[loc]=pin
    with pytest.raises(B6Denied):
        runtime.service.prepare(sid)
    assert runtime.fingerprint()==runtime.before


@pytest.mark.parametrize("field",["source_sha256","original_html_sha256","guard_sha256","manifest_sha256",
                                  "target_digest","native_content_hash","citation","guard-ref","report-version"])
def test_caller_rehash_cannot_replace_current_original(runtime,field):
    sid=runtime.login()
    d=runtime.service.prepare(sid).candidate.document
    if field=="citation":
        d["findings"][0]["citation"]["byte_start"]+=1
    elif field=="guard-ref":
        d["findings"][0]["citation"]["guard_ref"]="cg-"+"f"*64
        d["pins"]["guard_refs"].append("cg-"+"f"*64)
    elif field=="report-version":
        d["pins"]["report_version"]+=1
    else:
        d["pins"][field]="f"*64
    raw,html=reseal(d)
    # The forged candidate remains internally well-formed and self-consistent;
    # only fresh real PG provenance comparison is allowed to reject/accept it.
    assert Candidate(raw).document
    with no_egress() as attempts, pytest.raises(B6Denied):
        runtime.service.verify(sid,raw,html)
    assert not attempts and runtime.fingerprint()==runtime.before


@pytest.mark.parametrize("attack",["APPROVED","ShareGrant","person","owner-token","expired-token","revoked-token",
                                   "cross-tenant-recipient","public-link","email","VF-domain","sender","replay"])
def test_all_live_operations_are_denied_without_mutations_or_egress(runtime,attack):
    sid=runtime.login()
    package=runtime.service.prepare(sid)
    envelope=intended_envelope(package.candidate)
    values={"APPROVED":{"ReportVersion":{"status":"APPROVED"}},
            "ShareGrant":{"ShareGrant":{"status":"ACTIVE","token_hash":"a"*64}},
            "person":{"native_decision":{"person_id":"synthetic-person","action":"APPROVE"}},
            "owner-token":{"owner_token":"forged-owner-bearer","role":"OWNER"},
            "expired-token":{"token":"synthetic-expired","expires_at":"2000-01-01T00:00:00Z"},
            "revoked-token":{"token":"synthetic-revoked","revoked":True},
            "cross-tenant-recipient":{"tenant_id":"other-tenant","recipient":"synthetic-other@recipient.invalid"},
            "public-link":{"url":"https://public-synthetic.invalid/report"},
            "email":{"recipient":"synthetic-owner@recipient.invalid"},
            "VF-domain":{"endpoint":"https://vf-synthetic.invalid/handoff"},
            "sender":{"sender":{"webhook":"https://sender-synthetic.invalid/","credential":"forged-secret"}},
            "replay":parse(envelope.payload)}
    raw=canonical(values[attack])
    gate=DeliveryAuthorizationGate()
    before=runtime.fingerprint()
    with no_egress() as attempts:
        for operation in sorted(OPERATIONS):
            receipt=gate.attempt(operation,raw)
            assert gate.attempt(operation,raw)==receipt
            d=parse(receipt)
            assert d["decision"]=="DENY" and d["sent"] is False and d["allowed"] is False
            assert all(d[k] is None for k in ("grant","token","recipient","external_url","native_decision","outbox_event"))
            assert b"synthetic-owner@" not in receipt and b"forged-secret" not in receipt and b"https://" not in receipt
    assert attempts==[] and runtime.fingerprint()==before
    runtime.observation={"attack":attack,"operations_denied":len(OPERATIONS),"replays_denied":len(OPERATIONS),
                         "external_network_attempts":0,"grant_or_token_count":0,"delivery_or_outbox_mutations":0}


def test_zero_findings_cannot_become_an_approved_or_invented_l1(runtime):
    sid=runtime.login("200")
    p=runtime.service.prepare(sid)
    d=p.candidate.document
    assert not d["findings"] and d["pins"]["native_content_hash"] is None
    d["kind"]="L1_DRAFT_CANDIDATE"
    d["workflow_state"]="REVIEW_REQUIRED"
    d["pins"]["native_content_hash"]="f"*64
    cite=deepcopy(d["coverage"]["claims"][0])
    cite["claim_pointer"]="/issues/0/fact_claim"
    d["findings"]=[{"finding_id":"forged-finding","rule_id":"CTA-02","classification":"CAPTURED_STATIC_CONTACT_FAILURE","http_status":404,"citation":cite}]
    raw,html=reseal(d)
    assert Candidate(raw).document
    with pytest.raises(B6Denied):
        runtime.service.verify(sid,raw,html)
    d["status"]="APPROVED"
    assert parse(DeliveryAuthorizationGate().attempt("CREATE_GRANT",canonical(d)))["decision"]=="DENY"
    assert runtime.fingerprint()==runtime.before


@pytest.mark.parametrize("raw",[b'{"contract_version":"x","contract_version":"y"}',b'{"pins":{"tenant_id":"x","tenant_id":"y"}}',b'x'*131073])
def test_malformed_or_duplicate_candidate_rejected_no_db_change(runtime,raw):
    sid=runtime.login()
    with pytest.raises(B6Denied):
        runtime.service.verify(sid,raw,b"private")
    assert runtime.fingerprint()==runtime.before


def test_pg_role_cannot_widen_or_mutate_business_or_originals(runtime):
    import psycopg
    with runtime.settings().connect() as role:
        assert role.execute("SELECT session_user,current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user").fetchone()==("p2b1_test_a_reviewer","p2b1_test_a_reviewer",False,False)
        for query in ("SET ROLE postgres","SET ROLE ra4a_test_a_app","SELECT * FROM ra4a_bytes.objects",
                      "UPDATE ra4a_bytes.objects SET raw=raw","SELECT * FROM ra4a_review_test.audit",
                      "DELETE FROM ra4a_review_test.outbox","UPDATE ra4a_private.assignments SET active=true"):
            with pytest.raises(psycopg.Error) as caught:
                role.execute(query)
            assert caught.value.sqlstate=="42501"
            runtime.events.append({"event":"actual_low_role_denied","sqlstate":caught.value.sqlstate})
    assert runtime.fingerprint()==runtime.before


def test_anchor_revoked_during_actual_original_read_never_returns_package(runtime):
    sid=runtime.login()
    events=runtime.reader.audit
    seen=[]

    def revoke(value):
        events(value)
        if value["event"]=="native_original_verified":
            seen.append(True)
            runtime.store.boundary.anchor=replace(runtime.store.boundary.anchor,available=False)

    runtime.reader.audit=revoke
    with pytest.raises(B6Denied):
        runtime.service.prepare(sid)
    assert seen and runtime.fingerprint()==runtime.before


def test_real_single_use_login_token_replay_is_denied(runtime):
    sid=runtime.login()
    assert runtime.service.prepare(sid).candidate.document["status"]=="NOT_APPROVED"
    from apps.operator_console.contracts import ConsoleError
    with pytest.raises(ConsoleError):
        runtime.store.login(*runtime.last_login)
    assert runtime.fingerprint()==runtime.before


@pytest.mark.parametrize("bad",["expired-token","wrong-issuer","wrong-subject","extra-owner-claim"])
def test_actual_signed_invalid_login_cannot_create_candidate(runtime,bad):
    from apps.operator_console.contracts import ConsoleError
    now=int(time.time())
    changes={"expired-token":{"exp":now-30,"iat":now-60,"nbf":now-60},
             "wrong-issuer":{"iss":"https://wrong-synthetic-issuer.invalid"},
             "wrong-subject":{"sub":"other-synthetic-subject"},
             "extra-owner-claim":{"role":"OWNER"}}[bad]
    with pytest.raises(ConsoleError):
        runtime.login(changes=changes)
    assert not runtime.store.sessions and runtime.fingerprint()==runtime.before


def test_network_guard_rejects_before_actual_dns(runtime):
    import socket
    with no_egress() as attempts, pytest.raises(RuntimeError,match="B6_EXTERNAL_NETWORK_DENIED"):
        socket.getaddrinfo("b6-egress-selfcheck.invalid",443)
    assert attempts==["socket.getaddrinfo"] and runtime.fingerprint()==runtime.before
