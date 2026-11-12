"""Only accepted frozen captures; all new policy/object/actor metadata TEST_ONLY."""

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import json
from pathlib import Path

from vrae.evidence import EvidencePack
from vrae.findings import FindingPackage
from vrae.reporting import build_draft
from vrae.reporting.common import digest as native_digest
from vrae.reviewing import (
    CoverageAcknowledgementProposal,
    InMemoryReviewSimulation,
    ReviewCommandProposal,
    SyntheticTrust,
    TestOnlyActor,
    build_target,
)
from vrae.reviewing.canonical import SOURCE_LIMIT, canonical, sha
from vrae.reviewing.target import FINDING_KEYS, SIMULATION

NOW = datetime(2026, 11, 12, 12, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Inputs:
    document: bytes
    html: bytes
    source: bytes
    trust: SyntheticTrust
    target: object


@lru_cache(maxsize=8)
def inputs(case="404", version=1):
    raw = json.loads((Path(__file__).parent / "fixtures" / (case + ".json")).read_bytes())
    s, held = raw["source"], raw["held"]
    p = held["pins"]
    pack = EvidencePack.load(
        s["pack"],
        {k: base64.b64decode(v, validate=True) for k, v in s["objects_base64"].items()},
        expected_ref=p["expected_pack_ref"],
    )
    package = FindingPackage.load(s["package"], pack, **{k: p[k] for k in FINDING_KEYS})
    if version != 1:
        # Explicit new SYNTHETIC version via existing public producer. No original
        # fixture, source bytes, original Guard or frozen production code modified.
        s["metadata"]["version"] = version
        p["expected_metadata_sha256"] = native_digest(s["metadata"])
    draft = build_draft(pack, package, s["guard_inputs"], s["metadata"], **p)
    if version == 1:
        assert draft.ref == held["expected_draft_ref"]
        assert sha(draft.html_bytes) == held["expected_html_sha256"]
        assert sha(draft._payload) == held["expected_payload_sha256"]
    else:
        held.update(
            expected_draft_ref=draft.ref,
            expected_html_sha256=sha(draft.html_bytes),
            expected_payload_sha256=sha(draft._payload),
        )
    source = canonical(s, limit=SOURCE_LIMIT)
    held["expected_source_sha256"] = sha(source)
    scope = p["expected_scope"]
    policy = {
        "kind": "TEST_ONLY_POLICY_SNAPSHOT",
        "scope": scope,
        "allowed_purpose": "OFFLINE_REVIEW_SIMULATION",
        "current_authorization": "NOT_IMPLEMENTED",
    }
    artifact = (
        f"synthetic-object://{scope['tenant_id']}/{s['metadata']['report_id']}/"
        f"v{version}/{sha(draft.html_bytes)}"
    )
    trust = SyntheticTrust(SIMULATION, canonical(held), canonical(policy), artifact)
    target = build_target(draft._payload, draft.html_bytes, source, trust=trust)
    return Inputs(draft._payload, draft.html_bytes, source, trust, target)


def actor(target, **overrides):
    t = target.document
    data = dict(
        label="TEST_ONLY_ACTOR",
        tenant_id=t["tenant_id"],
        actor_id="test-only-reviewer",
        role="REVIEWER",
        assigned_reports=(t["report_id"],),
        synthetic_verified=True,
    )
    return TestOnlyActor(**(data | overrides))


def command(target, action="APPROVE_CANDIDATE", key="synthetic-key-0001"):
    t = target.document
    review = t["kind"] == "L1_NATIVE"
    data = {
        "contract_version": "ra3d-review-proposal-offline-v1",
        "kind": "REVIEW_COMMAND_PROPOSAL" if review else "COVERAGE_ACK_PROPOSAL",
        "tenant_id": t["tenant_id"],
        "report_id": t["report_id"],
        "report_version": t["report_version"],
        "target_digest": target.target_digest,
        "expected_review_seq": 0,
        "idempotency_key": key,
        "reason": None,
        "dispositions": [
            {
                **{k: c[k] for k in ("guard_ref", "binding_ref", "pointer")},
                "disposition": c["allowed_acceptance"],
            }
            for c in t["claims"]
        ],
        "sections": [
            {"section_id": s, "target_digest": target.target_digest, "acknowledged": True}
            for s in t["required_sections"]
        ],
    }
    if review:
        data["action"] = action
        if action in ("REQUEST_CHANGES", "REJECT"):
            data["reason"] = (
                "Review the specifically located impact expression before any future use."
            )
            d = next(x for x in data["dispositions"] if x["disposition"] == "ACCEPT_AS_HYPOTHESIS")
            d["disposition"] = "CHANGE_REQUESTED" if action == "REQUEST_CHANGES" else "REJECTED"
        return ReviewCommandProposal(canonical(data, limit=131_072))
    data.update(checked_scope=t["scope_digest"], remaining_unknowns=t["limitations_digest"])
    return CoverageAcknowledgementProposal(canonical(data, limit=131_072))


def ledger(i):
    engine = InMemoryReviewSimulation(simulation_label="OFFLINE_TEST_ONLY_NON_DURABLE")
    t = engine.publish(i.document, i.html, i.source, trust=i.trust)
    assert t.payload == i.target.payload
    return engine


def submit(engine, target, proposal=None, *, who=None, now=NOW):
    t = target.document
    return engine.submit(
        t["tenant_id"],
        t["report_id"],
        actor(target) if who is None else who,
        command(target) if proposal is None else proposal,
        synthetic_now=now,
    )
