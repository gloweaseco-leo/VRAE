"""DISC version of the accepted report projection, sharing native contracts and helpers."""

import hashlib
from urllib.parse import urlsplit
from vrae.domain.contracts import validate_contract
from vrae.domain.evidence import validate_evidence_graph
from vrae.domain.reviews import report_content_hash
from vrae.reporting.common import detach, digest, display_text, encode, fail
from vrae.reporting.draft import SOURCE_PIN_KEYS, PIN_KEYS, TASKS, _metadata
from vrae.reporting.editorial import LIMITATIONS


def _claims(guard_inputs, pack, package, pins, *, _disc=False):
    from vrae.interpretation.disc_report_v1 import GuardResult as DiscGuardResult
    from vrae.interpretation.disc_report_v1 import catalog as disc_catalog

    guard_type, source_catalog = (DiscGuardResult, disc_catalog)
    pack.verify(expected_ref=pins["expected_pack_ref"])
    sources = pack.document["sources"]
    if len(sources) != 1 or sources[0]["kind"] != "CaptureManifest":
        fail("REPORT_SINGLE_CAPTURE_REQUIRED")
    if (
        not isinstance(guard_inputs, list)
        or len(guard_inputs) > 16
        or (not isinstance(pins["expected_guard_refs"], list))
        or (len(pins["expected_guard_refs"]) != len(guard_inputs))
        or (len(set(pins["expected_guard_refs"])) != len(guard_inputs))
    ):
        fail("REPORT_GUARD_PINS")
    source_pins = {k: pins[k] for k in SOURCE_PIN_KEYS}
    known = source_catalog(pack, package, **source_pins)
    known_facts = {encode(f) for f in known["facts"]}
    claims = []
    for bundle, expected in zip(guard_inputs, pins["expected_guard_refs"]):
        if set(bundle) != {"interpretation", "bindings", "guard"}:
            fail("REPORT_GUARD_SHAPE")
        verified = guard_type.load(
            bundle["guard"],
            bundle["interpretation"],
            bundle["bindings"],
            pack,
            package,
            expected_guard_ref=expected,
            **source_pins,
        )
        if bundle["interpretation"]["status"] != "VALIDATED":
            fail("REPORT_GUARD_NOT_VALIDATED")
        if any(
            (
                bundle["interpretation"][k] is not None
                for k in ("model_id", "input_tokens", "output_tokens")
            )
        ):
            fail("REPORT_SYNTHETIC_MODEL_MODE")
        by_pointer = {b["pointer"]: b for b in bundle["bindings"]}
        for result in verified.document["claims"]:
            b = by_pointer[result["pointer"]]
            if result["status"] not in ("SOURCE_FACT_BINDING_VERIFIED", "HUMAN_REVIEW_REQUIRED"):
                fail("REPORT_CLAIM_REJECTED")
            if (
                encode(b["fact"]) not in known_facts
                or b["binding_ref"] != result["binding_ref"]
                or b["binding_ref"]
                != "cb-" + digest({k: v for k, v in b.items() if k != "binding_ref"})
            ):
                fail("REPORT_CLAIM_INTEGRITY")
            field, index = result["pointer"].split("/")[1:]
            if b["text"] != bundle["interpretation"][field][int(index)]:
                fail("REPORT_CLAIM_INTEGRITY")
            display_text(b["text"], 2000)
            display_text(b["fact"]["source"]["quote"])
            if result["status"] == "SOURCE_FACT_BINDING_VERIFIED":
                if (
                    b["claim_type"] != "OBJECTIVE_SOURCE_FACT"
                    or b["text"] != b["fact"]["statement"]
                ):
                    fail("REPORT_OBJECTIVE_CEILING")
            else:
                from .policy import proposals_for

                proposals = proposals_for(b["fact"]["rule_id"])
                if (b["claim_type"], b["text"]) not in set(proposals.values()):
                    fail("REPORT_UNSUPPORTED_PROSE")
            claims.append(
                {
                    "guard_ref": verified.ref,
                    "binding_ref": b["binding_ref"],
                    "pointer": b["pointer"],
                    "status": result["status"],
                    "claim_type": b["claim_type"],
                    "text": b["text"],
                    "fact": b["fact"],
                }
            )
    return claims


def _issues(package, claims, selection, *, _disc=False):
    kinds = {"CTA-02": "CAPTURED_CTA_HTTP_FAILURE"}
    from .policy import PROOF_KINDS

    kinds = PROOF_KINDS
    objective = [
        c
        for c in claims
        if c["status"] == "SOURCE_FACT_BINDING_VERIFIED"
        and c["fact"]["proof_kind"] in kinds.values()
    ]
    groups: dict[tuple, list] = {}
    unsupported = 0
    for item in package.document["items"]:
        if item["outcome"] != "FAIL_WITH_EVIDENCE":
            continue
        finding, row = (item["finding"], item["provenance"])
        matches = [c for c in objective if c["fact"]["observation_id"] == finding["observation_id"]]
        if item["rule_id"] not in kinds:
            unsupported += 1
            continue
        if len(matches) != 1:
            fail("REPORT_MISSING_OR_AMBIGUOUS_FACT")
        claim = matches[0]
        bridge = item["guard_bridge"]
        validate_evidence_graph(
            bridge["native_snapshot"],
            bridge["native_evidence"],
            bridge["guard_observation"],
            finding,
        )
        target = row["target_response"]
        if (
            finding["kind"] != "OBSERVATION"
            or target["http_status"] not in (404, 410)
            or encode(target) != encode(claim["fact"]["source"]["target_response"])
            or (claim["fact"]["rule_id"] != item["rule_id"])
            or (claim["fact"]["proof_kind"] != kinds[item["rule_id"]])
        ):
            fail("REPORT_EDGE_INTEGRITY")
        proposals = {}
        from .policy import proposals_for

        editorial = proposals_for(item["rule_id"])
        for role, (kind, text) in editorial.items():
            matches = [
                c
                for c in claims
                if c["status"] == "HUMAN_REVIEW_REQUIRED"
                and c["claim_type"] == kind
                and (c["text"] == text)
                and (encode(c["fact"]) == encode(claim["fact"]))
            ]
            if len(matches) != 1:
                fail("REPORT_MISSING_OR_AMBIGUOUS_PROPOSAL")
            proposals[role] = matches[0]
        key = (item["rule_id"], target["final_url"] or target["url"], target["http_status"])
        source = row.get("source_page", row.get("homepage"))
        if source is None:
            fail("REPORT_EDGE_INTEGRITY")
        groups.setdefault(key, []).append(
            {
                "finding": finding,
                "fact_claim": claim,
                "proposals": proposals,
                "native_bridge": bridge,
                "source_page": source,
                "target_response": target,
                "coverage_note": item["coverage_note"],
            }
        )
    representatives = [
        sorted(items, key=lambda x: x["finding"]["finding_id"])[0]
        for _, items in sorted(groups.items())
    ]
    if selection is not None:
        by_id = {i["finding"]["finding_id"]: i for items in groups.values() for i in items}
        if not set(selection) <= by_id.keys():
            fail("REPORT_SELECTION")
        chosen = [by_id[k] for k in selection]
        keys = {
            (i["fact_claim"]["fact"]["rule_id"],)
            + (
                i["target_response"]["final_url"] or i["target_response"]["url"],
                i["target_response"]["http_status"],
            )
            for i in chosen
        }
        if len(keys) != len(chosen):
            fail("REPORT_DUPLICATE_ISSUE")
    else:
        chosen = representatives[:3]
    return (chosen, len(representatives) - len(chosen), unsupported)


def _project(pack, package, guard_inputs, metadata, pins, *, _disc=False):
    from . import policy, renderer

    report_version, renderer_version = (policy.VERSION, policy.RENDERER_VERSION)
    editorial_version = policy.EDITORIAL_VERSION
    asset = renderer.asset_hash
    pins, metadata, guard_inputs = (detach(pins), detach(metadata), detach(guard_inputs))
    if (
        set(pins) != PIN_KEYS
        or pins["expected_reporting_version"] != report_version
        or pins["expected_renderer_version"] != renderer_version
    ):
        fail("REPORT_PIN_VERSION")
    _metadata(metadata, pins)
    claims = _claims(guard_inputs, pack, package, pins, _disc=True)
    issues, omitted, unsupported = _issues(
        package, claims, metadata["finding_selection"], _disc=True
    )
    positives = []
    for rule in ("INFO-01", "TRUST-01", "SEO-01"):
        values = [
            c
            for c in claims
            if c["status"] == "SOURCE_FACT_BINDING_VERIFIED"
            and c["fact"]["rule_id"] == rule
            and (c["fact"]["observation_result"] == "PASS")
        ]
        if values:
            positives.append(values[0])
    pages = []
    for source in pack.document["sources"]:
        if source["kind"] != "CaptureManifest":
            fail("REPORT_CAPTURE_KIND")
        for page in source["document"]["pages"]:
            snapshot = page["snapshot"]
            for key in ("url", "final_url"):
                if snapshot[key] is not None:
                    display_text(snapshot[key], 2048)
            pages.append(
                {
                    "url": snapshot["url"],
                    "final_url": snapshot["final_url"],
                    "captured_at": snapshot["captured_at"],
                    "role": page["role"],
                    "status": snapshot["status"],
                    "http_status": page["http_status"],
                    "error_code": page["error"]["code"] if page["error"] else None,
                }
            )
    if not pages or len(pages) > 128:
        fail("REPORT_CAPTURE_SCOPE")
    for issue in issues:
        for value in (
            issue["source_page"]["url"],
            issue["target_response"]["url"],
            issue["fact_claim"]["fact"]["source"]["citation"]["raw_href"],
        ):
            display_text(value, 2048)
    execution = package.document["rule_execution"]
    journey = []
    for task, label, rules in TASKS:
        rows = [
            {
                "rule_id": r["rule_id"],
                "observation_id": row["observation"]["observation_id"],
                "result": row["observation"]["result"],
            }
            for r in execution["executions"]
            if r["rule_id"] in rules
            for row in r["observations"]
        ]
        journey.append({"task": task, "label": label, "observations": rows})
    native = None
    if issues:
        native = {
            "schema_version": "1.0",
            **{k: pins["expected_scope"][k] for k in ("tenant_id", "run_id")},
            "report_id": metadata["report_id"],
            "report_version_id": "rv-" + digest({"metadata": metadata, "source_pins": pins}),
            "version": metadata["version"],
            "content_hash": "0" * 64,
            "status": "REVIEW_REQUIRED",
            "finding_ids": [i["finding"]["finding_id"] for i in issues],
            "created_by": metadata["created_by"],
            "created_at": metadata["created_at"],
            "approved_by": None,
            "approved_at": None,
            "audit_mode": "L1",
        }
        native["content_hash"] = report_content_hash(native, [i["finding"] for i in issues])
        validate_contract("ReportVersion", native)
    document = {
        "reporting_version": report_version,
        "renderer_version": renderer_version,
        "renderer_asset_sha256": asset(),
        "editorial_version": editorial_version,
        "metadata": metadata,
        "pins": pins,
        "guard_inputs_sha256": digest({"bundles": guard_inputs}),
        "scope": pins["expected_scope"],
        "kind": "L1_REPORT_DRAFT" if issues else "PRIVATE_COVERAGE_SUMMARY",
        "private": True,
        "approval_status": "NOT_APPROVED",
        "shareable": False,
        "semantic_approval": False,
        "native_report_version": native,
        "site_host": urlsplit(pages[0]["url"]).hostname,
        "examined_pages": pages,
        "issues": issues,
        "positive_source_claims": positives,
        "buyer_journey": journey,
        "omitted_eligible_issues": omitted,
        "unsupported_rule_findings": unsupported,
        "recorded_coverage": package.document["coverage"],
        "limitations": LIMITATIONS,
        "content_basis": "C3_FIELDS_AND_REPLAYED_PER_CLAIM_GUARD_NOT_EXTERNAL_AUTHENTICITY",
        "model_limitation": "SYNTHETIC_PROPOSALS_NO_PROVIDER_CALL_NO_SEMANTIC_APPROVAL",
    }
    document["editorial_content_sha256"] = digest(document)
    html = renderer.render_document(document)
    document["html_sha256"] = hashlib.sha256(html).hexdigest()
    document["draft_ref"] = "rd-" + digest(document)
    return (document, html)
