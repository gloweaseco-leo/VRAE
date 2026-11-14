"""Current accepted signed Reviewer -> original PG bytes -> private projection.

There is no HTTP, fixture fallback, APP credential, SET ROLE or business write.
Trusted control-plane policy/session objects never come from a browser DTO.
"""

from dataclasses import asdict, dataclass, field
from importlib import import_module

from vrae.domain.reviews import report_content_hash
from vrae.persistence.private_bytes import Locator

from .contracts import (Candidate, CLASSIFICATIONS, WARNINGS, canonical, deny, sha)
from .preview import PrivatePackage, render


@dataclass(frozen=True)
class RecipientPolicyDescriptor:
    issuer: str
    subject: str = field(repr=False)
    role: str
    location: Locator
    policy_id: str
    policy_version: int
    expires: int
    active: bool = True


def _citation(entry):
    c = entry["claim"]
    raw = entry["body"].encode("utf-8")
    start, end = entry["byte_start"], entry["byte_end"]
    if (c["status"] != "SOURCE_FACT_BINDING_VERIFIED" or not 0 <= start < end <= len(raw)
            or raw[start:end] != entry["quote"].encode("utf-8") or sha(raw) != entry["body_sha256"]):
        deny("B6_SOURCE_BINDING_DENIED")
    return {
        "claim_pointer": entry["pointer"], "guard_ref": c["guard_ref"],
        "claim_sha256": sha(canonical(c)), "evidence_ref": entry["citation"]["evidence_ref"],
        "source_ref": entry["citation"]["source_ref"], "body_sha256": sha(raw),
        "byte_start": start, "byte_end": end, "quote_sha256": sha(raw[start:end]),
    }


def _project(snapshot, binding, policy):
    # Called only inside the accepted Reader.request transaction, after original
    # NativeVerifier/Guard and exact descriptor pins have passed, never on JSON input.
    dossier, raw = snapshot["dossier"], snapshot["raw"]
    d, loc = dossier["document"], binding.location
    scope = d["scope"]
    if (scope != {"tenant_id": loc.tenant, "run_id": loc.source_run,
                  "policy_id": policy.policy_id, "policy_version": policy.policy_version}
            or d["metadata"]["report_id"] != loc.report or d["metadata"]["version"] != loc.version
            or not d["private"] or d["shareable"] or d["approval_status"] != "NOT_APPROVED"
            or len(d["issues"]) > 3):
        deny("B6_SOURCE_BINDING_DENIED")
    native = d["native_report_version"]
    if native is not None:
        if (not d["issues"] or native["status"] != "REVIEW_REQUIRED"
                or native["approved_by"] is not None or native["approved_at"] is not None
                or native["content_hash"] != report_content_hash(native, [i["finding"] for i in d["issues"]])):
            deny("B6_SOURCE_BINDING_DENIED")
    elif d["issues"]:
        deny("B6_SOURCE_BINDING_DENIED")
    by_pointer = {e["pointer"]: e for e in dossier["evidence"]}
    findings = []
    for index, issue in enumerate(d["issues"]):
        fact = issue["fact_claim"]["fact"]
        if fact["proof_kind"] != "CAPTURED_CTA_HTTP_FAILURE" or fact["rule_id"] != "CTA-02":
            deny("B6_SOURCE_BINDING_DENIED")
        findings.append({"finding_id": issue["finding"]["finding_id"], "rule_id": fact["rule_id"],
                         "classification": "CAPTURED_STATIC_CONTACT_FAILURE",
                         "http_status": issue["target_response"]["http_status"],
                         "citation": _citation(by_pointer[f"/issues/{index}/fact_claim"])})
    pins = {
        "tenant_id": loc.tenant, "report_id": loc.report, "report_version": loc.version,
        "source_run_id": loc.source_run, "ref_id": loc.ref_id, "target_digest": loc.target_digest,
        "target_sha256": sha(raw[("TARGET", "target")]), "manifest_sha256": snapshot["pin"].manifest_sha256,
        "source_sha256": sha(raw[("SOURCE", "source")]), "original_html_sha256": sha(raw[("HTML", "html")]),
        "draft_sha256": sha(raw[("DRAFT", "draft")]), "guard_sha256": sha(raw[("GUARD", "guard")]),
        "guard_refs": d["pins"]["expected_guard_refs"], "pack_ref": d["pins"]["expected_pack_ref"],
        "package_ref": d["pins"]["expected_package_ref"], "native_content_hash": native["content_hash"] if native else None,
    }
    core = {
        "contract_version": "b6-private-handoff-v1", "kind": "L1_DRAFT_CANDIDATE" if findings else "PRIVATE_COVERAGE_ONLY",
        "status": "NOT_APPROVED", "workflow_state": "REVIEW_REQUIRED" if findings else "DRAFT",
        "authority": "TEST_ONLY_PRIVATE_PREVIEW", "approval_proven": False, "shareable": False,
        "delivery_allowed": False, "external_visibility": False, "native_decision": None, "real_recipient": None,
        "pins": pins, "findings": findings,
        "coverage": {"scope_sha256": sha(canonical(scope)), "recorded_coverage_sha256": sha(canonical(d["recorded_coverage"])),
                     "claims": [_citation(e) for e in dossier["evidence"] if e["pointer"].startswith("/positive_source_claims/")],
                     "unchecked_scope": "UNKNOWN", "zero_findings_are_not_approval": True, "business_outcomes": "UNVERIFIED_NO_E2_E3"},
        "recipient_policy": {"tenant_id": loc.tenant, "policy_id": policy.policy_id, "policy_version": policy.policy_version,
                             "location_sha256": sha(canonical(asdict(loc))),
                             "principal_binding_sha256": sha(canonical([binding.issuer, binding.subject, binding.db_role, asdict(loc)])),
                             "mode": "OWNER_CONSENT_AND_LEGAL_REVIEW_REQUIRED", "owner_consent": None,
                             "legal_basis": None, "recipient": None},
        "classifications": CLASSIFICATIONS, "warnings": WARNINGS,
    }
    html = render(core)
    core["private_html_sha256"] = sha(html)
    core["content_digest"] = sha(canonical(core))
    return PrivatePackage(Candidate(canonical(core)), html)


class PrivateHandoffReader:
    def __init__(self, sessions, policies):
        # Optional application adapters are loaded only at the real PG seam.
        # Pure contract imports do not load the application's optional runtime.
        session_type = import_module("apps.operator_console.b5a_sessions").SessionStore
        if (type(sessions) is not session_type or type(policies) is not dict
                or any(type(p) is not RecipientPolicyDescriptor for p in policies.values())
                or set(policies) != set(sessions.bindings)):
            deny("B6_CURRENT_ACCESS_DENIED")
        self.sessions, self.policies = sessions, dict(policies)

    def _current(self, sid, expected=None):
        session = self.sessions.require(sid)
        if expected is not None and session is not expected:
            deny("B6_CURRENT_ACCESS_DENIED")
        policy = self.policies.get(session.task_id)
        if (policy is None or policy.active is not True or type(policy.expires) is not int
                or policy.expires <= self.sessions.clock() or policy.issuer != session.binding.issuer
                or policy.subject != session.subject or policy.role != session.binding.db_role
                or policy.location != session.binding.location):
            deny("B6_CURRENT_ACCESS_DENIED")
        return session, policy

    def prepare(self, sid):
        with self.sessions.lock:
            try:
                session, policy = self._current(sid)
                reader = self.sessions.readers[session.binding.db_role]
                reader_type = import_module("apps.operator_console.b5a_reader").ReviewerReader
                if type(reader) is not reader_type:
                    deny("B6_CURRENT_ACCESS_DENIED")

                def current():
                    self._current(sid, session)

                with reader.request(session.binding, recheck=current) as snapshot:
                    package = _project(snapshot, session.binding, policy)
                current()
                return package
            except Exception:
                # No SQL error, cookie, subject, source or untrusted string escapes.
                deny("B6_CURRENT_ACCESS_DENIED")

    def verify(self, sid, candidate_bytes, private_html):
        try:
            submitted = PrivatePackage(Candidate(candidate_bytes), private_html)
            actual = self.prepare(sid)
            if (submitted.candidate.payload != actual.candidate.payload
                    or submitted.private_html != actual.private_html):
                deny("B6_SOURCE_BINDING_DENIED")
            return actual
        except Exception:
            deny("B6_SOURCE_BINDING_DENIED")
