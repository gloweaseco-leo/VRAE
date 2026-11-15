"""Replay fresh authorized capture input through the accepted DISC chain.

These are consistency candidates, never DB COMMIT receipts or authorization.
The missing low-role source/commit/read ports must be independently approved;
neither this module nor a caller-provided lease can replace those checks.
"""

from dataclasses import asdict, dataclass, field
import base64
from datetime import datetime
import hashlib
import json
import re
from uuid import UUID

from vrae.collection.manifest import CaptureBundle, document_hash
from vrae.collection.policy import SourceAccess
from vrae.evidence import build_pack
from vrae.findings import build_findings
from vrae.interpretation.disc_report_v1 import binding, catalog, validate
from vrae.reporting.common import digest
from vrae.reporting.disc_report_v1 import ReportDraft, build_draft
from vrae.reporting.disc_report_v1.policy import proposals_for
from vrae.rules import execute

VERSION = "ra4b-p2-generated-candidate-v1"
AUTHORITY = "CONSISTENCY_CANDIDATE_NOT_COMMITTED_NOT_APPROVED"


class CandidateDenied(ValueError):
    """Closed error vocabulary, never raw pages or lease tokens."""


def encode(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def require(condition):
    if not condition:
        raise CandidateDenied("S2_LEASE_CONTEXT_DENIED")


def capture_digest(capture):
    capture.verify()
    return document_hash(
        {
            "manifest": capture.manifest,
            "objects": {
                k: hashlib.sha256(v).hexdigest() for k, v in sorted(capture.objects.items())
            },
        }
    )


@dataclass(frozen=True)
class LeaseContext:
    tenant_id: str
    request_id: str
    run_id: str
    job_id: str
    worker: str
    lease_token: str = field(repr=False)
    lease_seq: int
    lease_until: str
    origin_epoch: int
    source_ref: str
    reference_sha256: str
    input_sha256: str
    policy_id: str
    policy_version: int
    policy_sha256: str
    created_at: str

    def check(self, now):
        try:
            expected = {"ra4b_test_a_worker": "tenant-test", "ra4b_test_b_worker": "tenant-beta"}
            require(expected.get(self.worker) == self.tenant_id)
            for value in (self.request_id, self.run_id, self.job_id, self.lease_token):
                require(type(value) is str and str(UUID(value)) == value)
            require(len({self.request_id, self.run_id, self.job_id}) == 3)
            require(type(self.lease_seq) is int and 1 <= self.lease_seq <= 3)
            require(type(self.origin_epoch) is int and 0 < self.origin_epoch < 2**63)
            require(type(self.policy_version) is int and self.policy_version > 0)
            require(now.tzinfo is not None)
            until = datetime.fromisoformat(self.lease_until.replace("Z", "+00:00"))
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            require(until.tzinfo is not None and created.tzinfo is not None)
            require(created <= now < until and (until - created).total_seconds() <= 30)
            require(re.fullmatch(r"[A-Za-z0-9_.-]{3,128}", self.source_ref))
            require(re.fullmatch(r"[A-Za-z0-9_.-]{3,128}", self.policy_id))
            for value in (self.reference_sha256, self.input_sha256, self.policy_sha256):
                require(type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value))
        except Exception:
            raise CandidateDenied("S2_LEASE_CONTEXT_DENIED") from None

    def private_binding(self):
        result = asdict(self)
        token = result.pop("lease_token")
        result["lease_token_sha256"] = hashlib.sha256(token.encode()).hexdigest()
        return result


@dataclass(frozen=True)
class GeneratedCandidate:
    _payload: bytes = field(repr=False)
    _html: bytes = field(repr=False)
    _source: bytes = field(default=b"", repr=False)

    @property
    def private_document(self):
        return json.loads(self._payload)

    @property
    def ref(self):
        return "s2c-" + hashlib.sha256(self._payload).hexdigest()

    def verify(self, capture, access, context, *, now):
        rebuilt = generate(capture, access, context, now=now)
        if (
            self._payload != rebuilt._payload
            or self._html != rebuilt._html
            or self._source != rebuilt._source
        ):
            raise CandidateDenied("S2_CANDIDATE_REPLAY_MISMATCH")
        return rebuilt


def generate(capture: CaptureBundle, access: SourceAccess, context: LeaseContext, *, now: datetime):
    context.check(now)
    if type(capture) is not CaptureBundle or type(access) is not SourceAccess:
        raise CandidateDenied("S2_CAPTURE_POLICY_REQUIRED")
    # Detach the mutable caller-owned bundle before any replay or hashing.
    capture = CaptureBundle(json.loads(encode(capture.manifest)), dict(capture.objects))
    scope = {k: capture.manifest[k] for k in ("tenant_id", "run_id", "policy_id", "policy_version")}
    expected = {k: getattr(context, k) for k in scope}
    if scope != expected or capture_digest(capture) != context.input_sha256:
        raise CandidateDenied("S2_AUTHORIZED_INPUT_MISMATCH")
    access.check(access.start_url)
    if document_hash(access.provider()) != context.policy_sha256:
        raise CandidateDenied("S2_POLICY_VERSION_MISMATCH")
    if (
        access.audit["tenant_id"] != context.tenant_id
        or access.audit["source_policy_ref"] != context.policy_id
        or access.audit["source_policy_version"] != context.policy_version
    ):
        raise CandidateDenied("S2_POLICY_SCOPE_MISMATCH")
    for page in capture.manifest["pages"]:
        access.check(page["snapshot"]["url"])
    pack = build_pack([capture])
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version="ra2b6-1.0.0")
    base = {
        "expected_pack_ref": pack.ref,
        "expected_execution_ref": execution["execution_ref"],
        "expected_builder_version": "ra2c3-1.0.0",
        "expected_evaluator_version": "ra2b6-1.0.0",
    }
    package = build_findings(pack, execution, **base)
    source_pins = {
        **base,
        "expected_package_ref": package.ref,
        "expected_guard_version": "ra3b-disc-1.0.0",
        "expected_scope": scope,
    }
    bundles = []
    source_catalog = catalog(pack, package, **source_pins)
    for index, fact in enumerate(source_catalog["facts"]):
        interpretation: dict = {
            "schema_version": "1.0",
            "tenant_id": context.tenant_id,
            "run_id": context.run_id,
            "interpretation_id": "s2-generated-" + str(index),
            "observation_ids": [fact["observation_id"]],
            "evidence_ids": [fact["source"]["citation"]["evidence_ref"]],
            "hypotheses": [fact["statement"]],
            "recommendations": [],
            "missing_information": [],
            "model_id": None,
            "input_tokens": None,
            "output_tokens": None,
            "status": "VALIDATED",
        }
        bindings = [
            binding(
                pointer="/hypotheses/0",
                text=fact["statement"],
                claim_type="OBJECTIVE_SOURCE_FACT",
                fact=fact,
                context=source_catalog["context"],
            )
        ]
        if fact["proof_kind"] in ("CAPTURED_CTA_HTTP_FAILURE", "CAPTURED_DISC_HTTP_FAILURE"):
            for kind, text in proposals_for(fact["rule_id"]).values():
                key = "recommendations" if kind == "RECOMMENDATION" else "hypotheses"
                pointer = "/" + key + "/" + str(len(interpretation[key]))
                interpretation[key].append(text)
                bindings.append(
                    binding(
                        pointer=pointer,
                        text=text,
                        claim_type=kind,
                        fact=fact,
                        context=source_catalog["context"],
                    )
                )
        guard = validate(interpretation, bindings, pack, package, **source_pins)
        bundles.append(
            {"interpretation": interpretation, "bindings": bindings, "guard": guard.document}
        )
    metadata = {
        "report_id": "job-" + context.job_id,
        "version": 1,
        "created_at": context.created_at,
        "created_by": context.worker,
        "mode": "SYNTHETIC_PRIVATE_PREVIEW",
        "finding_selection": None,
    }
    pins = {
        **source_pins,
        "expected_guard_refs": [b["guard"]["guard_ref"] for b in bundles],
        "expected_metadata_sha256": digest(metadata),
        "expected_reporting_version": "ra3c-disc-1.0.0",
        "expected_renderer_version": "ra3c-disc-html-1.0.0",
    }
    draft = build_draft(pack, package, bundles, metadata, **pins)
    ReportDraft.load(
        draft.document,
        draft.html_bytes,
        pack,
        package,
        bundles,
        metadata,
        expected_draft_ref=draft.ref,
        **pins,
    )
    result = {
        "contract_version": VERSION,
        "authority": AUTHORITY,
        "committed": False,
        "commit_receipt": None,
        "reviewer_assignment": None,
        "native_approval": None,
        "share_grant": None,
        "binding": context.private_binding(),
        "scope": scope,
        "versions": {
            "evaluator": "ra2b6-1.0.0",
            "builder": "ra2c3-1.0.0",
            "guard": "ra3b-disc-1.0.0",
            "report": "ra3c-disc-1.0.0",
            "renderer": "ra3c-disc-html-1.0.0",
        },
        "evidence_pack_ref": pack.ref,
        "evidence_sha256": document_hash(pack.document),
        "rule_execution_ref": execution["execution_ref"],
        "execution_sha256": document_hash(execution),
        "finding_package_ref": package.ref,
        "finding_sha256": document_hash(package.document),
        "guard_refs": pins["expected_guard_refs"],
        "guard_sha256": [document_hash(b["guard"]) for b in bundles],
        "draft_ref": draft.ref,
        "report": draft.document,
        "report_sha256": document_hash(draft.document),
        "html_sha256": hashlib.sha256(draft.html_bytes).hexdigest(),
    }
    source = {
        "pack": pack.document,
        "objects_base64": {k: base64.b64encode(v).decode() for k, v in pack.objects.items()},
        "package": package.document,
        "guard_inputs": bundles,
        "metadata": metadata,
    }
    return GeneratedCandidate(encode(result), draft.html_bytes, encode(source))
