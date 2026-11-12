"""Source-replayed, versioned review sidecar for explicit synthetic use only."""

import base64
from dataclasses import dataclass
from functools import lru_cache
import re

from vrae.domain.reviews import report_content_hash
from vrae.evidence import EvidencePack
from vrae.findings import FindingPackage
from vrae.reporting import ReportDraft
from vrae.reporting.renderer import asset_hash

from .canonical import SOURCE_LIMIT, canonical, digest, parse, refuse, sha, shape

SIMULATION = "TEST_ONLY_ACCEPTED_SYNTHETIC_SOURCE"
CONTRACT = "ra3d-review-target-offline-v1"
FINDING_KEYS = (
    "expected_pack_ref",
    "expected_execution_ref",
    "expected_package_ref",
    "expected_builder_version",
    "expected_evaluator_version",
)
SECTIONS = ("coverage.v1", "limitations.v1", "full_preview.v1", "business_boundaries.v1")


@dataclass(frozen=True, slots=True)
class SyntheticTrust:
    """Explicitly synthetic caller-held pins; NEVER a real policy/object authority.

    held includes the independently captured original payload/source SHA. It is
    supplied outside the draft; uploading a draft cannot supply its own trust.
    policy and artifact are test-only stand-ins, never external capabilities.
    """

    label: str
    held: bytes
    policy: bytes
    artifact_ref: str


@dataclass(frozen=True, slots=True)
class ReviewTarget:
    """Immutable bytes. Direct construction is unverified; validate before use."""

    payload: bytes

    @property
    def document(self):
        return parse(self.payload)

    @property
    def target_digest(self):
        return digest("target", self.document)


def displayed_claims(document):
    result = []
    for index, issue in enumerate(document["issues"]):
        result.append((f"/issues/{index}/fact_claim", issue["fact_claim"]))
        result.extend(
            (f"/issues/{index}/proposals/{role}", issue["proposals"][role])
            for role in ("impact", "action", "recheck")
        )
    result.extend(
        (f"/positive_source_claims/{i}", c)
        for i, c in enumerate(document["positive_source_claims"])
    )
    return result


def _trust(trust, source_raw, document, html):
    if type(trust) is not SyntheticTrust or trust.label != SIMULATION:
        refuse("D_TRUST_INPUT_REQUIRED")
    held = parse(trust.held)
    shape(
        held,
        (
            "pins",
            "expected_draft_ref",
            "expected_html_sha256",
            "expected_issue_count",
            "expected_payload_sha256",
            "expected_source_sha256",
        ),
    )
    if (
        sha(document) != held["expected_payload_sha256"]
        or sha(html) != held["expected_html_sha256"]
    ):
        refuse("D_ARTIFACT_TAMPER")
    if sha(source_raw) != held["expected_source_sha256"]:
        refuse("D_SOURCE_INTEGRITY")
    policy = parse(trust.policy)
    shape(policy, ("kind", "scope", "allowed_purpose", "current_authorization"))
    if (
        policy["kind"] != "TEST_ONLY_POLICY_SNAPSHOT"
        or policy["scope"] != held["pins"]["expected_scope"]
        or policy["allowed_purpose"] != "OFFLINE_REVIEW_SIMULATION"
        or policy["current_authorization"] != "NOT_IMPLEMENTED"
    ):
        refuse("D_POLICY_UNTRUSTED")
    return held, policy


def _claim_manifest(d, pack, source):
    manifest, identities = [], set()
    bundles = {b["guard"]["guard_ref"]: b for b in source["guard_inputs"]}
    for path, c in displayed_claims(d):
        identity = (c["guard_ref"], c["binding_ref"], c["pointer"])
        if identity in identities:
            refuse("D_CLAIM_AMBIGUOUS")
        identities.add(identity)
        b = bundles[c["guard_ref"]]
        binding = next(x for x in b["bindings"] if x["binding_ref"] == c["binding_ref"])
        status = next(x for x in b["guard"]["claims"] if x["binding_ref"] == c["binding_ref"])
        if (
            binding["pointer"] != c["pointer"]
            or binding["fact"] != c["fact"]
            or binding["text"] != c["text"]
            or status["status"] != c["status"]
        ):
            refuse("D_CLAIM_CEILING")
        source_fact = c["fact"]["source"]
        citation = source_fact["citation"]
        resolved = pack.resolve(citation["evidence_ref"], expected_pack_ref=pack.ref)
        start, end = source_fact["byte_start"], source_fact["byte_end"]
        raw = resolved["content"]
        if (
            type(raw) is not bytes
            or type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= len(raw)
            or raw[start:end] != source_fact["quote"].encode("utf-8")
            or resolved["evidence"]["source_ref"] != citation["source_ref"]
            or resolved["evidence"]["snapshot_ref"] != citation["snapshot_ref"]
        ):
            refuse("D_SOURCE_INTEGRITY")
        expected = {
            "OBJECTIVE_SOURCE_FACT": ("SOURCE_FACT_BINDING_VERIFIED", "ACK_LITERAL_FACT"),
            "HYPOTHESIS": ("HUMAN_REVIEW_REQUIRED", "ACCEPT_AS_HYPOTHESIS"),
            "RECOMMENDATION": ("HUMAN_REVIEW_REQUIRED", "ACCEPT_AS_PROPOSED_ACTION"),
        }
        pair = expected.get(c["claim_type"])
        if pair is None or c["status"] != pair[0]:
            refuse("D_CLAIM_CEILING")
        manifest.append(
            {
                "guard_ref": c["guard_ref"],
                "binding_ref": c["binding_ref"],
                "pointer": c["pointer"],
                "document_pointer": path,
                "claim_type": c["claim_type"],
                "machine_status": c["status"],
                "allowed_acceptance": pair[1],
                "text_sha256": sha(c["text"].encode("utf-8")),
                "fact_sha256": sha(canonical(c["fact"])),
                "evidence_ref": citation["evidence_ref"],
                "source_ref": citation["source_ref"],
                "byte_start": start,
                "byte_end": end,
                "source_object_sha256": sha(raw),
            }
        )
    return manifest


@lru_cache(maxsize=4)
def _replay_bytes(document: bytes, html: bytes, source_raw: bytes, trust: SyntheticTrust, assets):
    """Replay supplied bytes against separately held synthetic source/object pins.

    No fetch, model call, clock, actor, approval or persistence occurs here.
    Native loaders perform their existing read-only contract schema checks.
    """
    try:
        d = parse(document, limit=SOURCE_LIMIT)
        s = parse(source_raw, limit=SOURCE_LIMIT)
        held, policy = _trust(trust, source_raw, document, html)
        p = held["pins"]
        objects = {k: base64.b64decode(v, validate=True) for k, v in s["objects_base64"].items()}
        pack = EvidencePack.load(s["pack"], objects, expected_ref=p["expected_pack_ref"])
        package = FindingPackage.load(s["package"], pack, **{k: p[k] for k in FINDING_KEYS})
        loaded = ReportDraft.load(
            d,
            html,
            pack,
            package,
            s["guard_inputs"],
            s["metadata"],
            expected_draft_ref=held["expected_draft_ref"],
            **p,
        )
        if loaded._payload != document or len(d["issues"]) != held["expected_issue_count"]:
            refuse("D_ARTIFACT_TAMPER")
        if not d["private"] or d["shareable"] or d["approval_status"] != "NOT_APPROVED":
            refuse("D_PRIVATE_ONLY")
        native = d["native_report_version"]
        if native is not None:
            if (
                not d["issues"]
                or native["status"] != "REVIEW_REQUIRED"
                or native["approved_by"] is not None
                or native["approved_at"] is not None
                or report_content_hash(native, [i["finding"] for i in d["issues"]])
                != native["content_hash"]
            ):
                refuse("D_NATIVE_BINDING")
        elif d["issues"] or d["kind"] != "PRIVATE_COVERAGE_SUMMARY":
            refuse("D_COVERAGE_NOT_REPORT")
        scope, metadata = p["expected_scope"], d["metadata"]
        artifact = (
            f"synthetic-object://{scope['tenant_id']}/{metadata['report_id']}/"
            f"v{metadata['version']}/{sha(html)}"
        )
        if trust.artifact_ref != artifact:
            refuse("D_OBJECT_REQUIRED")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", scope["tenant_id"]):
            refuse("D_SCOPE")
        manifest = _claim_manifest(d, pack, s)
        model = []
        for bundle, ref in zip(s["guard_inputs"], p["expected_guard_refs"]):
            interpretation = bundle["interpretation"]
            if interpretation["model_id"] is not None:
                refuse("D_PROVENANCE_INVALID")
            model.append(
                {
                    "guard_ref": ref,
                    "mode": "SYNTHETIC_NO_MODEL_NOT_RUN",
                    "model_id": None,
                    "gateway_version": None,
                    "prompt_version": None,
                    "interpretation_sha256": sha(canonical(interpretation)),
                    "limitation": "NOT_RECORDED_NO_LIVE_MODEL_NO_HUMAN_APPROVAL",
                }
            )
        payload = {
            "contract_version": CONTRACT,
            "authority": SIMULATION,
            "kind": "L1_NATIVE" if native else "COVERAGE_ONLY",
            **scope,
            "report_id": metadata["report_id"],
            "report_version": metadata["version"],
            "policy_snapshot_sha256": sha(canonical(policy)),
            "native_report_version_id": native["report_version_id"] if native else None,
            "native_content_hash": native["content_hash"] if native else None,
            "native_sha256": sha(canonical(native)),
            "draft_ref": loaded.ref,
            "draft_payload_sha256": sha(document),
            "editorial_content_sha256": d["editorial_content_sha256"],
            "html_sha256": sha(html),
            "renderer_asset_sha256": asset_hash(),
            "evidence_pack_ref": pack.ref,
            "execution_ref": p["expected_execution_ref"],
            "finding_package_ref": package.ref,
            "ordered_guard_refs": p["expected_guard_refs"],
            "source_manifest_sha256": sha(
                canonical(
                    {
                        "pack_ref": pack.ref,
                        "document": pack.document,
                        "objects": [
                            {"object_key": k, "content_sha256": sha(v), "length_bytes": len(v)}
                            for k, v in sorted(objects.items())
                        ],
                    },
                    limit=SOURCE_LIMIT,
                )
            ),
            "source_record_sha256": sha(source_raw),
            "guard_inputs_sha256": d["guard_inputs_sha256"],
            "builder_version": p["expected_builder_version"],
            "evaluator_version": p["expected_evaluator_version"],
            "guard_version": p["expected_guard_version"],
            "reporting_version": d["reporting_version"],
            "editorial_version": d["editorial_version"],
            "renderer_version": d["renderer_version"],
            "model_provenance": model,
            "artifact_ref": artifact,
            "claims": manifest,
            "required_sections": list(SECTIONS),
            "scope_digest": digest(
                "coverage",
                {
                    "pages": d["examined_pages"],
                    "recorded_coverage": d["recorded_coverage"],
                    "journey": d["buyer_journey"],
                },
            ),
            "limitations_digest": digest("limitations", d["limitations"]),
        }
        return ReviewTarget(canonical(payload))
    except Exception as exc:
        from .canonical import ReviewError

        if isinstance(exc, ReviewError):
            raise
        refuse("D_SOURCE_REPLAY")


def validate_target(target: ReviewTarget, document, html, source_raw, *, trust):
    rebuilt = build_target(document, html, source_raw, trust=trust)
    if (
        type(target) is not ReviewTarget
        or type(target.payload) is not bytes
        or target.payload != rebuilt.payload
    ):
        refuse("D_TARGET_STALE")
    return rebuilt


def build_target(document: bytes, html: bytes, source_raw: bytes, *, trust: SyntheticTrust):
    """Bounded memo of successful complete replay, keyed by ALL immutable bytes.

    Accepted engine/schema source is fixed by D1, not a hot-reload runtime.
    No failed replay, actor, current-policy authorization, time, version-ledger
    state or decision is cached. Changed assets or any input byte miss the memo.
    """
    if type(trust) is not SyntheticTrust or trust.label != SIMULATION:
        refuse("D_TRUST_INPUT_REQUIRED")
    for raw in (document, html, source_raw):
        if type(raw) is not bytes or len(raw) > SOURCE_LIMIT:
            refuse("D_JSON_BOUND")
    for raw in (trust.held, trust.policy):
        if type(raw) is not bytes or len(raw) > 65_536:
            refuse("D_TRUST_INPUT_REQUIRED")
    if type(trust.artifact_ref) is not str or len(trust.artifact_ref) > 512:
        refuse("D_OBJECT_REQUIRED")
    return _replay_bytes(document, html, source_raw, trust, asset_hash())
