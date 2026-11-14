"""Schema fixtures are untrusted bytes, never evidence, identity or authority."""

from copy import deepcopy
import pytest

from vrae.b6_p0.contracts import (Candidate, IntendedEnvelope, B6Denied, CLASSIFICATIONS,
                                  WARNINGS, canonical, parse, sha)
from vrae.b6_p0.delivery import DeliveryAuthorizationGate, DenyOnlySink, OPERATIONS
from vrae.b6_p0.envelope import intended_envelope
from vrae.b6_p0.preview import PrivatePackage, render


def shape_fixture(kind="PRIVATE_COVERAGE_ONLY"):
    """Only a shape fixture: no claim that its placeholder hashes have sources."""
    h="0"*64
    core={"contract_version":"b6-private-handoff-v1","kind":kind,"status":"NOT_APPROVED",
          "workflow_state":"DRAFT" if kind=="PRIVATE_COVERAGE_ONLY" else "REVIEW_REQUIRED",
          "authority":"TEST_ONLY_PRIVATE_PREVIEW","approval_proven":False,"shareable":False,
          "delivery_allowed":False,"external_visibility":False,"native_decision":None,"real_recipient":None,
          "pins":{"tenant_id":"tenant-shape","report_id":"report-shape","report_version":1,
                  "source_run_id":"run-shape","ref_id":"ref-shape","target_digest":h,"target_sha256":h,
                  "manifest_sha256":h,"source_sha256":h,"original_html_sha256":h,"draft_sha256":h,
                  "guard_sha256":h,"guard_refs":["cg-"+h],"pack_ref":"ep-shape","package_ref":"fp-shape",
                  "native_content_hash":None if kind=="PRIVATE_COVERAGE_ONLY" else h},
          "findings":[],"coverage":{"scope_sha256":h,"recorded_coverage_sha256":h,"claims":[],
                                      "unchecked_scope":"UNKNOWN","zero_findings_are_not_approval":True,
                                      "business_outcomes":"UNVERIFIED_NO_E2_E3"},
          "recipient_policy":{"tenant_id":"tenant-shape","policy_id":"pol-shape","policy_version":1,
                              "location_sha256":h,"principal_binding_sha256":h,
                              "mode":"OWNER_CONSENT_AND_LEGAL_REVIEW_REQUIRED","owner_consent":None,
                              "legal_basis":None,"recipient":None},
          "classifications":CLASSIFICATIONS,"warnings":WARNINGS}
    if kind=="L1_DRAFT_CANDIDATE":
        core["findings"]=[{"finding_id":"finding-shape","rule_id":"CTA-02",
                           "classification":"CAPTURED_STATIC_CONTACT_FAILURE","http_status":404,
                           "citation":{"claim_pointer":"/issues/0/fact_claim","guard_ref":"cg-"+h,
                                       "claim_sha256":h,"evidence_ref":"ev-shape","source_ref":"src-shape",
                                       "body_sha256":h,"byte_start":0,"byte_end":1,"quote_sha256":h}}]
    html=render(core)
    core["private_html_sha256"]=sha(html)
    core["content_digest"]=sha(canonical(core))
    return Candidate(canonical(core)),html


def rehash(d):
    d=deepcopy(d)
    d.pop("content_digest",None)
    d["content_digest"]=sha(canonical(d))
    return canonical(d)


@pytest.mark.parametrize("raw",[b'{"x":1,"x":2}',b'{"nested":{"x":1,"x":2}}',b'{"x":NaN}',
                                b'{"x":1.5}',b'\xff',b'{} ',b'{"a":',b'['*40+b']'*40,b'x'*131073])
def test_parser_is_bounded_duplicate_free_and_canonical(raw):
    with pytest.raises(B6Denied):
        parse(raw)


@pytest.mark.parametrize("kind",["PRIVATE_COVERAGE_ONLY","L1_DRAFT_CANDIDATE"])
def test_shape_and_sealed_html_roundtrip_without_authority(kind):
    c,html=shape_fixture(kind)
    assert Candidate(c.payload)==c
    assert PrivatePackage(c,html).candidate.document["delivery_allowed"] is False
    assert b"NOT APPROVED" in html and b"<script" not in html and b"https://" not in html
    assert intended_envelope(c)==IntendedEnvelope(intended_envelope(c).payload)
    # Even a syntactically valid candidate cannot acquire delivery authority.
    receipt=parse(DeliveryAuthorizationGate().consume_intended_envelope(intended_envelope(c).payload))
    assert receipt["decision"]=="DENY" and receipt["grant"] is None
    with pytest.raises(B6Denied):
        PrivatePackage(c,html+b"changed")


@pytest.mark.parametrize("key,value",[("authority","OWNER"),("approval_proven",True),("shareable",True),
                                      ("delivery_allowed",True),("external_visibility",True),
                                      ("native_decision",{"status":"APPROVED"}),("real_recipient","synthetic@recipient.invalid"),
                                      ("raw_source","<a>private</a>"),("guard",{}),("token","forged"),
                                      ("status","APPROVED"),("warnings",[])])
def test_rehash_does_not_open_closed_permission_or_privacy_fields(key,value):
    d=shape_fixture()[0].document
    d[key]=value
    with pytest.raises(B6Denied):
        Candidate(rehash(d))


def test_no_more_than_three_findings_or_invalid_intervals_or_cross_tenant():
    d=shape_fixture("L1_DRAFT_CANDIDATE")[0].document
    for change in ("four","interval","tenant"):
        altered=deepcopy(d)
        if change=="four":
            altered["findings"]=[{**deepcopy(d["findings"][0]),"finding_id":"finding-"+str(i)} for i in range(4)]
        elif change=="interval":
            altered["findings"][0]["citation"]["byte_end"]=0
        else:
            altered["recipient_policy"]["tenant_id"]="other-tenant"
        with pytest.raises(B6Denied):
            Candidate(rehash(altered))


@pytest.mark.parametrize("operation",sorted(OPERATIONS))
def test_all_delivery_operations_deny_forged_approved_grant_and_recipient(operation):
    raw=canonical({"report":{"status":"APPROVED"},"ShareGrant":{"status":"ACTIVE","token_hash":"a"*64},
                   "owner":{"role":"OWNER","person_id":"forged-person"},"recipient":"synthetic@recipient.invalid", 
                   "sender":"https://vf-synthetic.invalid/handoff","secret":"forged-owner-bearer"})
    gate=DeliveryAuthorizationGate()
    a=gate.attempt(operation,raw)
    assert gate.attempt(operation,raw)==a and len(gate.sink.records)==1
    d=parse(a)
    assert d["decision"]=="DENY" and d["allowed"] is False and d["sent"] is False
    assert all(d[k] is None for k in ("grant","token","recipient","external_url","native_decision","outbox_event"))
    assert b"synthetic@" not in a and b"vf-synthetic" not in a and b"forged-owner" not in a


@pytest.mark.parametrize("operation,raw",[("https://vf-synthetic.invalid",b'{}'),("SEND",b'{"x":1,"x":2}'),
                                         ("SEND",b'['*40+b']'*40),("SEND",b'x'*131073),(None,None),(True,{}),
                                         ("ISSUE_TOKEN",b'{"token":"expired","revoked":true}')])
def test_invalid_or_expired_or_revoked_inputs_always_deny(operation,raw):
    d=parse(DeliveryAuthorizationGate().attempt(operation,raw))
    assert d["decision"]=="DENY" and d["token"] is None


def test_no_sender_injection_and_only_denial_receipts_enter_finite_sink():
    with pytest.raises(ValueError):
        DeliveryAuthorizationGate(sink=lambda _:None)
    gate=DeliveryAuthorizationGate()
    with pytest.raises(AttributeError):
        gate.sink=lambda _:None
    with pytest.raises(B6Denied):
        DenyOnlySink()._record(b'{}')
    for i in range(300):
        assert parse(gate.attempt("SEND",canonical({"sequence":i})))["sent"] is False
    assert len(gate.sink.records)==256
