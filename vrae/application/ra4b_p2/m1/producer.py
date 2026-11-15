"""Complete evidence, deterministic bounded L1 claims, unchanged DISC Guard."""

import base64
from dataclasses import dataclass
import json
import hashlib

from vrae.evidence import build_pack, EvidencePack
from vrae.findings import build_findings, FindingPackage
from vrae.interpretation.disc_report_v1 import binding, catalog, validate
from vrae.reporting.common import digest
from vrae.reporting.disc_report_v1 import ReportDraft, build_draft
from vrae.reporting.disc_report_v1.policy import proposals_for
from vrae.rules import execute
from ..producer import encode, capture_digest, CandidateDenied


@dataclass(frozen=True)
class Output:
    source: bytes
    report: bytes
    html: bytes
    binding: bytes


def select_facts(facts):
    """Keep every failure fact; bound editorial positives to one per rule.

    Report's existing three-problem selection remains responsible for which
    eligible issues are shown. Full catalog, package and execution are retained.
    Fail closed if failure representatives themselves exceed the existing cap.
    """
    failures = [
        f
        for f in facts
        if f["proof_kind"] in ("CAPTURED_CTA_HTTP_FAILURE", "CAPTURED_DISC_HTTP_FAILURE")
    ]
    positives = []
    for rule in ("INFO-01", "TRUST-01", "SEO-01"):
        matches = [f for f in facts if f["rule_id"] == rule and f not in failures]
        if matches:
            positives.append(sorted(matches, key=encode)[0])
    chosen = sorted(failures, key=encode) + positives
    if len(chosen) > 16:
        raise CandidateDenied("M1_FAILURE_SET_EXCEEDS_GUARD_CAP")
    return chosen


def produce(capture, access, context, *, now):
    context.check(now)
    if capture_digest(capture) != context.input_sha256:
        raise CandidateDenied("M1_CAPTURE_PIN")
    for p in capture.manifest["pages"]:
        access.check(p["snapshot"]["url"])
    if digest(access.provider()) != context.policy_sha256:
        raise CandidateDenied("M1_POLICY_PIN")
    pack = build_pack([capture])
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version="ra2b6-1.0.0")
    pins = dict(
        expected_pack_ref=pack.ref,
        expected_execution_ref=execution["execution_ref"],
        expected_builder_version="ra2c3-1.0.0",
        expected_evaluator_version="ra2b6-1.0.0",
    )
    package = build_findings(pack, execution, **pins)
    pins.update(
        expected_package_ref=package.ref,
        expected_guard_version="ra3b-disc-1.0.0",
        expected_scope={
            k: getattr(context, k) for k in ("tenant_id", "run_id", "policy_id", "policy_version")
        },
    )
    full = catalog(pack, package, **pins)
    chosen = select_facts(full["facts"])
    bundles = []
    failures = [
        f
        for f in chosen
        if f["proof_kind"] in ("CAPTURED_CTA_HTTP_FAILURE", "CAPTURED_DISC_HTTP_FAILURE")
    ]
    positives = [f for f in chosen if f not in failures]
    groups = [[f] for f in failures] + ([positives] if positives else [])
    for n, group in enumerate(groups):
        doc = dict(
            schema_version="1.0",
            tenant_id=context.tenant_id,
            run_id=context.run_id,
            interpretation_id="m1-" + str(n),
            observation_ids=sorted({f["observation_id"] for f in group}),
            evidence_ids=sorted({f["source"]["citation"]["evidence_ref"] for f in group}),
            hypotheses=[],
            recommendations=[],
            missing_information=[],
            model_id=None,
            input_tokens=None,
            output_tokens=None,
            status="VALIDATED",
        )
        bound = []
        for fact in group:
            pointer = "/hypotheses/" + str(len(doc["hypotheses"]))
            doc["hypotheses"].append(fact["statement"])
            bound.append(
                binding(
                    pointer=pointer,
                    text=fact["statement"],
                    claim_type="OBJECTIVE_SOURCE_FACT",
                    fact=fact,
                    context=full["context"],
                )
            )
            if fact["proof_kind"] in ("CAPTURED_CTA_HTTP_FAILURE", "CAPTURED_DISC_HTTP_FAILURE"):
                for kind, text in proposals_for(fact["rule_id"]).values():
                    field = "recommendations" if kind == "RECOMMENDATION" else "hypotheses"
                    pointer = "/" + field + "/" + str(len(doc[field]))
                    doc[field].append(text)
                    bound.append(
                        binding(
                            pointer=pointer,
                            text=text,
                            claim_type=kind,
                            fact=fact,
                            context=full["context"],
                        )
                    )
        guard = validate(doc, bound, pack, package, **pins)
        bundles.append(dict(interpretation=doc, bindings=bound, guard=guard.document))
    metadata = dict(
        report_id="job-" + context.job_id,
        version=1,
        created_at=context.created_at,
        created_by=context.worker,
        mode="SYNTHETIC_PRIVATE_PREVIEW",
        finding_selection=None,
    )
    pins.update(
        expected_guard_refs=[b["guard"]["guard_ref"] for b in bundles],
        expected_metadata_sha256=digest(metadata),
        expected_reporting_version="ra3c-disc-1.0.0",
        expected_renderer_version="ra3c-disc-html-1.0.0",
    )
    draft = build_draft(pack, package, bundles, metadata, **pins)
    # Selection is explicit provenance alongside the full immutable evidence.
    source = dict(
        pack=pack.document,
        package=package.document,
        guard_inputs=bundles,
        metadata=metadata,
        objects_base64={k: base64.b64encode(v).decode() for k, v in pack.objects.items()},
        editorial_selection=dict(
            version="m1-relevant-facts-v1",
            # Retain the complete canonical catalog as a scalar, avoiding a
            # second deep SQL canonical walk alongside the complete pack.
            full_catalog_json=encode(full["facts"]).decode(),
            full_catalog_sha256=hashlib.sha256(encode(full["facts"])).hexdigest(),
            selected_facts=chosen,
            omitted_positive_facts=len(full["facts"]) - len(chosen),
            full_evidence_retained=True,
        ),
    )
    result = Output(
        encode(source), draft._payload, draft.html_bytes, encode(context.private_binding())
    )
    # Native construction verified every Guard. Independently replay once at
    # the commit boundary (and again on each authorized read), not twice here.
    return result


def replay(output):
    s = json.loads(output.source)
    d = json.loads(output.report)
    pins = d["pins"]
    objects = {k: base64.b64decode(v, validate=True) for k, v in s["objects_base64"].items()}
    pack = EvidencePack.load(s["pack"], objects, expected_ref=pins["expected_pack_ref"])
    keys = (
        "expected_pack_ref",
        "expected_execution_ref",
        "expected_package_ref",
        "expected_builder_version",
        "expected_evaluator_version",
    )
    package = FindingPackage.load(s["package"], pack, **{k: pins[k] for k in keys})
    proof_pins = {k: pins[k] for k in (*keys, "expected_guard_version", "expected_scope")}
    full = catalog(pack, package, **proof_pins)["facts"]
    selection = s["editorial_selection"]
    if selection != dict(
        version="m1-relevant-facts-v1",
        full_catalog_json=encode(full).decode(),
        full_catalog_sha256=hashlib.sha256(encode(full)).hexdigest(),
        selected_facts=select_facts(full),
        omitted_positive_facts=len(full) - len(select_facts(full)),
        full_evidence_retained=True,
    ):
        raise CandidateDenied("M1_EDITORIAL_SELECTION")
    ReportDraft.load(
        d,
        output.html,
        pack,
        package,
        s["guard_inputs"],
        s["metadata"],
        expected_draft_ref=d["draft_ref"],
        **pins,
    )
    return d
