"""Versioned graph bytes for the HELD registration delta, never a live writer.

The object is untrusted until a genuine DB seal/finish/commit receipt exists.
This adapter independently replays the DISC draft; it never relabels it as an
old accepted-fixture target or changes the original B3/private-byte validators.
"""

import base64
from dataclasses import dataclass
import json

from vrae.evidence import EvidencePack
from vrae.findings import FindingPackage
from vrae.persistence.private_bytes import Artifact, descriptors
from vrae.reporting.disc_report_v1 import ReportDraft
from vrae.reporting.disc_report_v1.renderer import CSS, RENDERER_VERSION, asset_hash
from vrae.reviewing.canonical import canonical, digest, SOURCE_LIMIT, sha
from vrae.reviewing.target import _claim_manifest, SECTIONS
from .producer import CandidateDenied, GeneratedCandidate, encode

AUTHORITY = "TEST_ONLY_WORKER_GENERATED_SOURCE"
VERSION = "ra4b-p2-generated-target-v1"


@dataclass(frozen=True)
class GeneratedGraph:
    target: bytes
    manifest: bytes
    artifacts: tuple[Artifact, ...]

    @property
    def target_digest(self):
        return digest("target", json.loads(self.target))


def assemble(candidate: GeneratedCandidate):
    doc = candidate.private_document
    d = doc["report"]
    s = json.loads(candidate._source)
    p = d["pins"]
    if doc["committed"] or doc["commit_receipt"] is not None:
        raise CandidateDenied("S2_NOT_AN_AUTHORIZED_COMMIT_RECEIPT")
    objects = {k: base64.b64decode(v, validate=True) for k, v in s["objects_base64"].items()}
    pack = EvidencePack.load(s["pack"], objects, expected_ref=p["expected_pack_ref"])
    finding_keys = (
        "expected_pack_ref",
        "expected_execution_ref",
        "expected_package_ref",
        "expected_evaluator_version",
        "expected_builder_version",
    )
    package = FindingPackage.load(s["package"], pack, **{k: p[k] for k in finding_keys})
    draft = ReportDraft.load(
        d,
        candidate._html,
        pack,
        package,
        s["guard_inputs"],
        s["metadata"],
        expected_draft_ref=doc["draft_ref"],
        **p,
    )
    if sha(encode(d)) != doc["report_sha256"] or sha(candidate._html) != doc["html_sha256"]:
        raise CandidateDenied("S2_GRAPH_HASH_MISMATCH")
    native = d["native_report_version"]
    binding = doc["binding"]
    target = {
        "contract_version": VERSION,
        "authority": AUTHORITY,
        "kind": "L1_NATIVE" if native else "COVERAGE_ONLY",
        **d["scope"],
        "report_id": d["metadata"]["report_id"],
        "report_version": d["metadata"]["version"],
        "native_content_hash": native["content_hash"] if native else None,
        "native_report_version_id": native["report_version_id"] if native else None,
        "draft_ref": draft.ref,
        "draft_payload_sha256": sha(encode(d)),
        "editorial_content_sha256": d["editorial_content_sha256"],
        "html_sha256": sha(candidate._html),
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
        "source_record_sha256": sha(candidate._source),
        "guard_inputs_sha256": d["guard_inputs_sha256"],
        "builder_version": p["expected_builder_version"],
        "evaluator_version": p["expected_evaluator_version"],
        "guard_version": p["expected_guard_version"],
        "reporting_version": d["reporting_version"],
        "editorial_version": d["editorial_version"],
        "renderer_version": d["renderer_version"],
        "model_provenance": [
            {
                "guard_ref": b["guard"]["guard_ref"],
                "mode": "SYNTHETIC_NO_MODEL_NOT_RUN",
                "model_id": None,
                "interpretation_sha256": sha(encode(b["interpretation"])),
            }
            for b in s["guard_inputs"]
        ],
        "artifact_ref": "private-generated://"
        + binding["tenant_id"]
        + "/"
        + d["metadata"]["report_id"]
        + "/v1/"
        + sha(candidate._html),
        "claims": _claim_manifest(d, pack, s),
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
        "generated_binding": binding,
        "candidate_sha256": sha(candidate._payload),
    }
    raw = canonical(target)
    artifacts = [
        Artifact("DRAFT", "draft", encode(d)),
        Artifact("HTML", "html", candidate._html),
        Artifact("SOURCE", "source", candidate._source),
        Artifact("PACK", "pack", canonical(s["pack"], limit=SOURCE_LIMIT)),
        Artifact("PACKAGE", "package", canonical(s["package"], limit=SOURCE_LIMIT)),
        Artifact("GUARD", "guard", canonical(s["guard_inputs"], limit=SOURCE_LIMIT)),
        Artifact("METADATA", "metadata", canonical(s["metadata"], limit=SOURCE_LIMIT)),
        Artifact("CSS", "css", (RENDERER_VERSION + "\n" + CSS).encode()),
        Artifact("TARGET", "target", raw),
    ]
    artifacts.extend(Artifact("SOURCE_OBJECT", k, v) for k, v in objects.items())
    artifacts = sorted(artifacts, key=lambda a: (a.kind, a.key))
    if (
        len(artifacts) > 137
        or sum(len(a.raw) for a in artifacts) > 64000000
        or any(len(a.raw) > 8000000 for a in artifacts)
    ):
        raise CandidateDenied("S2_GRAPH_BOUND")
    return GeneratedGraph(
        raw, canonical(descriptors(artifacts), limit=SOURCE_LIMIT), tuple(artifacts)
    )
