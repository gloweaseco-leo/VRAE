"""Complete synthetic byte graphs. No DB driver, actor or self-attested trust."""

import base64
from dataclasses import dataclass
import re

from vrae.reporting.renderer import CSS, RENDERER_VERSION
from vrae.reviewing import ReviewTarget, SyntheticTrust, build_target, validate_target
from vrae.reviewing.canonical import SOURCE_LIMIT, TARGET_LIMIT, canonical, parse, sha
from .contracts import PersistenceError


@dataclass(frozen=True)
class Artifact:
    kind: str
    key: str
    raw: bytes


@dataclass(frozen=True)
class ByteGraph:
    """Direct construction is unverified. External provenance is required on use."""

    ref_id: str
    target: bytes
    artifacts: tuple[Artifact, ...]
    manifest: bytes
    trust: SyntheticTrust


@dataclass(frozen=True)
class Locator:
    tenant: str
    source_run: str
    report: str
    version: int
    ref_id: str
    target_digest: str


def descriptors(artifacts):
    return [
        {"key": a.key, "kind": a.kind, "length": len(a.raw), "sha256": sha(a.raw)}
        for a in sorted(artifacts, key=lambda a: (a.kind, a.key))
    ]


def assemble(ref_id, document, html, source, *, trust):
    if type(ref_id) is not str or not re.fullmatch(r"[a-zA-Z0-9_.-]{3,96}", ref_id):
        raise PersistenceError("P2A_REFERENCE_INVALID")
    target = build_target(document, html, source, trust=trust)
    validate_target(target, document, html, source, trust=trust)
    s = parse(source, limit=SOURCE_LIMIT)
    artifacts = [
        Artifact("DRAFT", "draft", document),
        Artifact("HTML", "html", html),
        Artifact("SOURCE", "source", source),
        Artifact("PACK", "pack", canonical(s["pack"], limit=SOURCE_LIMIT)),
        Artifact("PACKAGE", "package", canonical(s["package"], limit=SOURCE_LIMIT)),
        Artifact("GUARD", "guard", canonical(s["guard_inputs"], limit=SOURCE_LIMIT)),
        Artifact("METADATA", "metadata", canonical(s["metadata"], limit=SOURCE_LIMIT)),
        Artifact("CSS", "css", (RENDERER_VERSION + "\n" + CSS).encode()),
        Artifact("TARGET", "target", target.payload),
    ]
    artifacts.extend(
        Artifact("SOURCE_OBJECT", k, base64.b64decode(v, validate=True))
        for k, v in s["objects_base64"].items()
    )
    artifacts = sorted(artifacts, key=lambda a: (a.kind, a.key))
    if len(artifacts) > 137 or sum(len(a.raw) for a in artifacts) > 64_000_000:
        raise PersistenceError("P2A_GRAPH_BOUND")
    if any(len(a.raw) > (TARGET_LIMIT if a.kind == "TARGET" else SOURCE_LIMIT) for a in artifacts):
        raise PersistenceError("P2A_GRAPH_BOUND")
    return ByteGraph(
        ref_id,
        target.payload,
        tuple(artifacts),
        canonical(descriptors(artifacts), limit=SOURCE_LIMIT),
        trust,
    )


def locator(graph):
    t = ReviewTarget(graph.target)
    d = t.document
    return Locator(
        d["tenant_id"],
        d["run_id"],
        d["report_id"],
        d["report_version"],
        graph.ref_id,
        t.target_digest,
    )


def verify(candidate, *, provenance):
    """Never take pins/trust from the stored candidate."""
    if type(candidate) is not ByteGraph or type(provenance) is not ByteGraph:
        raise PersistenceError("P2A_INDEPENDENT_PROVENANCE_REQUIRED")
    expected = {(a.kind, a.key): a.raw for a in provenance.artifacts}
    rebuilt = assemble(
        provenance.ref_id,
        expected[("DRAFT", "draft")],
        expected[("HTML", "html")],
        expected[("SOURCE", "source")],
        trust=provenance.trust,
    )
    if provenance != rebuilt or candidate.ref_id != provenance.ref_id:
        raise PersistenceError("P2A_PROVENANCE_INVALID")
    # Includes exact complete source object set, original JSON/HTML/CSS/Guard bytes,
    # target and sealed manifest, not only the naked target/ref digest.
    if (
        candidate.target != rebuilt.target
        or candidate.artifacts != rebuilt.artifacts
        or candidate.manifest != rebuilt.manifest
    ):
        raise PersistenceError("P2A_PRIVATE_BYTES_INTEGRITY")
    raw = {(a.kind, a.key): a.raw for a in candidate.artifacts}
    validate_target(
        ReviewTarget(candidate.target),
        raw[("DRAFT", "draft")],
        raw[("HTML", "html")],
        raw[("SOURCE", "source")],
        trust=provenance.trust,
    )
    return rebuilt


def production_store_port(*args, **kwargs):
    raise PersistenceError("P2A_PRODUCTION_IDENTITY_OBJECT_REVIEW_DENIED")
