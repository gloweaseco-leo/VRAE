"""Offline acceptance inputs for the explicitly versioned DISC report route."""

from tests.reporting.synthetic import base_pins
from tests.rules.synthetic import site
from tests.rules.test_journey import journey_pack
from vrae.findings import build_findings
from vrae.interpretation.disc_report_v1 import VERSION as GUARD_VERSION
from vrae.interpretation.disc_report_v1 import binding, catalog, validate
from vrae.reporting.common import digest
from vrae.reporting.disc_report_v1.policy import VERSION, RENDERER_VERSION, proposals_for
from vrae.rules import execute


def inputs(rule="DISC-01", status=404, **capture_options):
    pack = (
        site(status, **capture_options)
        if rule == "DISC-01"
        else journey_pack(stage=2, status=status, **capture_options)
    )
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version="ra2b6-1.0.0")
    package = build_findings(pack, execution, **base_pins(pack, execution))
    source_pins = {
        **base_pins(pack, execution),
        "expected_package_ref": package.ref,
        "expected_guard_version": GUARD_VERSION,
        "expected_scope": {
            k: pack.document[k] for k in ("tenant_id", "run_id", "policy_id", "policy_version")
        },
    }
    facts = catalog(pack, package, **source_pins)
    bundles = []
    for index, fact in enumerate(facts["facts"]):
        interpretation = {
            "schema_version": "1.0",
            **{k: pack.document[k] for k in ("tenant_id", "run_id")},
            "interpretation_id": "disc-offline-" + str(index),
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
                context=facts["context"],
            )
        ]
        if fact["proof_kind"] in ("CAPTURED_DISC_HTTP_FAILURE", "CAPTURED_CTA_HTTP_FAILURE"):
            for kind, text in proposals_for(fact["rule_id"]).values():
                field = "recommendations" if kind == "RECOMMENDATION" else "hypotheses"
                pointer = f"/{field}/{len(interpretation[field])}"
                interpretation[field].append(text)
                bindings.append(
                    binding(
                        pointer=pointer,
                        text=text,
                        claim_type=kind,
                        fact=fact,
                        context=facts["context"],
                    )
                )
        bundles.append(
            {
                "interpretation": interpretation,
                "bindings": bindings,
                "guard": validate(interpretation, bindings, pack, package, **source_pins).document,
            }
        )
    metadata = {
        "report_id": "disc-offline-report",
        "version": 1,
        "created_at": "2026-11-14T23:00:00Z",
        "created_by": "offline-review-operator",
        "mode": "SYNTHETIC_PRIVATE_PREVIEW",
        "finding_selection": None,
    }
    pins = {
        **source_pins,
        "expected_guard_refs": [b["guard"]["guard_ref"] for b in bundles],
        "expected_metadata_sha256": digest(metadata),
        "expected_reporting_version": VERSION,
        "expected_renderer_version": RENDERER_VERSION,
    }
    return pack, package, bundles, metadata, pins
