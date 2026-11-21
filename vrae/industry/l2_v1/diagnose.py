"""Replayable industrial buyer-task analysis over native guarded source facts.

The existing Collector/EvidencePack/RuleExecution/FindingPackage/Guard remain
the source authority. This module projects procurement comparisons and questions,
not a new report, authorization, score, engineering approval or fact store.
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal
import re

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.evidence import EvidenceError
from vrae.findings import build_findings
from vrae.findings.builder import _bridge
from vrae.interpretation.disc_report_v1 import binding, catalog, validate
from vrae.reporting.common import encode
from vrae.rules.patch_execution import execute
from .pack import load
from .contracts import validate_export

VERSION = "l2-industrial-1.0.0"
PATCH_VERSION = "l2-industrial-1.0.1"
SOURCE_VERSIONS = {VERSION: ("ra2b6-1.0.0", "ra2c3-1.0.0"),
                   PATCH_VERSION: ("ra2b6-1.0.1", "ra2c3-1.0.1"),
                   "l2-industrial-1.0.2": ("ra2b6-1.0.2", "ra2c3-1.0.2"),
                   "l2-industrial-1.0.3": ("ra2b6-1.0.3", "ra2c3-1.0.3"),
                   "l2-industrial-1.0.4": ("ra2b6-1.0.4", "ra2c3-1.0.4"),
                   "l2-industrial-1.0.5": ("ra2b6-1.0.5", "ra2c3-1.0.5"),
                   "l2-industrial-1.0.6": ("ra2b6-1.0.5", "ra2c3-1.0.5")}
IMPACTS = {
    "IND-SELECTION": "The recorded route and model labels may help a buyer shortlist this item; actual navigation usability and SKU identity have not been independently verified.",
    "IND-SPEC": "Unresolved model-specific specification fields may require clarification before a technical comparison; unobserved alternative datasheets may supply them.",
    "IND-DUTY": "A mismatch between source-listed values and the stated duty may require another model or engineering clarification; a scalar match alone cannot establish the operating point.",
    "IND-FIT": "The buyer may need supplier engineering review of the medium, operating envelope and installation before selecting this model.",
    "IND-PROOF": "Supplier-stated proof context may need current documents and independent verification before procurement acceptance; supplier qualification has not been determined.",
    "IND-RFQ": "Unresolved buyer inputs may prevent a precise quotation until clarified; neither an actual quotation delay nor inquiry delivery has been observed.",
}


def denied():
    raise EvidenceError("L2_INDUSTRY_INTEGRITY") from None


def normalized(text):
    return " ".join(text.split()).casefold()


def source_chain(pack, expected_pack_ref, *, diagnostic_version=VERSION):
    if diagnostic_version in ('l2-industrial-1.0.5', 'l2-industrial-1.0.6'):
        from vrae.rules.replay_scope import execution_scope
        with execution_scope(pack):
            return _source_chain(pack, expected_pack_ref, diagnostic_version=diagnostic_version)
    return _source_chain(pack, expected_pack_ref, diagnostic_version=diagnostic_version)


def _source_chain(pack, expected_pack_ref, *, diagnostic_version):
    if diagnostic_version not in SOURCE_VERSIONS:
        denied()
    evaluator, builder = SOURCE_VERSIONS[diagnostic_version]
    execution = execute(pack, expected_pack_ref=expected_pack_ref, evaluator_version=evaluator)
    pins = dict(expected_pack_ref=expected_pack_ref, expected_execution_ref=execution["execution_ref"],
                expected_evaluator_version=evaluator, expected_builder_version=builder)
    package = build_findings(pack, execution, **pins)
    pins.update(expected_package_ref=package.ref, expected_guard_version="ra3b-disc-1.0.0",
                expected_scope={k: pack.document[k] for k in ("tenant_id", "run_id", "policy_id", "policy_version")})
    known = catalog(pack, package, **pins)
    facts = known["facts"]
    if len(facts) > 256:
        denied()
    # Native AIInterpretation has uniqueItems for literal statements. Preserve
    # every page's separate provenance instead of deduplicating repeated labels.
    groups: list[list] = [[]]
    for fact in facts:
        target = next((g for g in groups if fact["statement"] not in {f["statement"] for f in g}), None)
        if target is None:
            target = []
            groups.append(target)
        target.append(fact)
    if len(groups) > 16:
        denied()
    bundles = []
    for index, group in enumerate(groups):
        interpretation = dict(schema_version="1.0", tenant_id=execution["tenant_id"], run_id=execution["run_id"],
                              interpretation_id="industrial-source-" + str(index), status="VALIDATED" if group else "NOT_RUN",
                              model_id=None, input_tokens=None, output_tokens=None,
                              observation_ids=sorted({f["observation_id"] for f in group}),
                              evidence_ids=sorted({f["source"]["citation"]["evidence_ref"] for f in group}),
                              hypotheses=[f["statement"] for f in group], recommendations=[], missing_information=[])
        bindings = [binding(pointer="/hypotheses/" + str(i), text=f["statement"],
                            claim_type="OBJECTIVE_SOURCE_FACT", fact=f, context=known["context"])
                    for i, f in enumerate(group)]
        guard = validate(interpretation, bindings, pack, package, **pins)
        if any(c["status"] != "SOURCE_FACT_BINDING_VERIFIED" for c in guard.document["claims"]):
            denied()
        bundles.append(dict(interpretation=interpretation, bindings=bindings, guard=guard.document))
    return execution, package, facts, bundles


def records(facts, profile):
    """Pair only replayed INFO-01 label/value citations; never parse new facts."""
    pages: dict[str, dict] = {}
    for fact in facts:
        if fact["rule_id"] != "INFO-01":
            continue
        c = fact["source"]["citation"]
        page = pages.setdefault(c["url"], {"url": c["url"], "pairs": {}, "fields": {}, "name_ref": None})
        if c["fact_role"] == "NAME":
            page["name_ref"] = fact["fact_ref"]
        else:
            page["pairs"].setdefault(c["field_index"], {})[c["fact_role"]] = fact
    for page in pages.values():
        for pair in page["pairs"].values():
            if set(pair) != {"SPEC_LABEL", "SPEC_VALUE"}:
                continue
            label = pair["SPEC_LABEL"]["source"]["citation"]["text"]
            value = pair["SPEC_VALUE"]["source"]["citation"]["text"]
            keys = [key for key, aliases in profile["labels"].items()
                    if normalized(label) in {normalized(a) for a in aliases}]
            for key in keys:
                if key in page["fields"]:
                    # Aliases colliding on a canonical field are ambiguous.
                    page["fields"][key] = None
                else:
                    page["fields"][key] = {"text": value, "fact_refs": [pair[r]["fact_ref"] for r in ("SPEC_LABEL", "SPEC_VALUE")]}
        page.pop("pairs")
    return list(pages.values())


def field(record, key):
    return record["fields"].get(key) if record else None


def text(record, key):
    value = field(record, key)
    return value["text"].strip() if value else None


def refs(record, *keys):
    return sorted({r for k in keys if field(record, k) for r in field(record, k)["fact_refs"]})


def quantity(value, profile):
    if value is None:
        return None
    m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z0-9/]+)", value)
    if m is None or m[2] not in profile["units"] or len(m[1]) > 20:
        return None
    dimension, factor = profile["units"][m[2]]
    return dimension, Decimal(m[1]) * Decimal(factor)


def usable(record, key):
    value = field(record, key)
    if value and normalized(value["text"]) not in {"tbd", "n/a", "unknown", "on request", "contact us", "not specified", "-"}:
        return value
    return None


def matching(records_, kind, model):
    matches = [r for r in records_ if normalized(text(r, "record_type") or "") == normalized(kind)
               and model in [m.strip() for m in (text(r, "models") or "").split(",")]]
    return matches[0] if len(matches) == 1 else None


def product_family(record, profile):
    declared = normalized(text(record, "family") or "")
    supported = [family for family, aliases in profile["family_aliases"].items()
                 if declared in {normalized(a) for a in aliases}]
    return supported[0] if len(supported) == 1 else None


def analyze(pack, execution, facts, profile):
    pages = records(facts, profile)
    by_ref = {f["fact_ref"]: f for f in facts}
    scope = {k: pack.document[k] for k in ("tenant_id", "run_id")}
    assessments: list[dict] = []
    rfq_packets = []
    rule_map = {r["rule_id"]: r for r in profile["rules"]}
    native_rows = [row for r in execution["executions"] for row in r["observations"]]

    def add(rule_id, model, result, statement, reason, fact_refs=(), *, details=None, recommendation=None):
        # One native Evidence graph plus explicit inseparable related-source
        # edges: the legacy graph validator is intentionally single-Evidence.
        related = sorted(set(fact_refs))
        objective = result in ("PASS", "FAIL_WITH_EVIDENCE")
        if any(r not in by_ref for r in related) or (objective and not related):
            denied()
        evidence_ids = [by_ref[related[0]]["source"]["citation"]["evidence_ref"]] if objective else []
        observation = dict(schema_version="1.0", **scope, rule_id=rule_id, rule_version="1.0.0",
                           result=result, kind="OBJECTIVE" if objective else "UNKNOWN", evidence_ids=evidence_ids,
                           statement=statement, coverage_note="Captured source declarations and configured procurement checks only; not whole-site absence, engineering fit, authenticated qualification or business outcome.")
        identity = dict(observation=observation, model=model, related=related, reason=reason)
        observation["observation_id"] = "obs-" + document_hash(identity)
        if any(a["observation"]["observation_id"] == observation["observation_id"] for a in assessments):
            # Missing scalar pairs can have identical UNKNOWN wording and no
            # evidence. Preserve each configured comparison with its context;
            # never merge it away or bypass the report's unique-ID guard.
            identity["assessment_details"] = details or {}
            observation["observation_id"] = "obs-" + document_hash(identity)
            if any(a["observation"]["observation_id"] == observation["observation_id"] for a in assessments):
                denied()
        validate_contract("Observation", observation)
        finding = dict(schema_version="1.0", **scope, observation_id=observation["observation_id"],
                       kind="OBSERVATION" if objective else "UNKNOWN", evidence_ids=[], statement=statement,
                       buyer_task=rule_map[rule_id]["task"], severity=None, rule_version="1.0.0")
        finding["finding_id"] = "finding-" + document_hash(finding)
        bridge = _bridge(pack, observation, finding)
        finding["finding_id"] = "finding-" + document_hash({k: v for k, v in finding.items() if k != "finding_id"})
        validate_contract("Finding", finding)
        proposals = []
        if recommendation:
            proposal = dict(finding, kind="RECOMMENDATION", statement=recommendation, evidence_ids=[])
            proposal["finding_id"] = "finding-" + document_hash(proposal)
            validate_contract("Finding", proposal)
            proposals.append({"finding": proposal, "status": "HUMAN_REVIEW_REQUIRED"})
        impact = dict(finding, kind="HYPOTHESIS", evidence_ids=[], statement=IMPACTS[rule_id])
        impact["finding_id"] = "finding-" + document_hash({k: v for k, v in impact.items() if k != "finding_id"})
        validate_contract("Finding", impact)
        assessments.append(dict(model=model, observation=observation, finding=finding, reason=reason,
                                source_fact_refs=related, guard_bridge=bridge, details=details or {},
                                possible_buyer_impact={"finding": impact, "status": "HUMAN_REVIEW_REQUIRED"},
                                recommendations=proposals, semantic_approval=False))

    products = [r for r in pages if normalized(text(r, "record_type") or "") == normalized(profile["record_types"]["product"])
                or (text(r, "record_type") is None and text(r, "model") and product_family(r, profile))]
    if not products:
        add("IND-SELECTION", None, "UNKNOWN", "No unambiguous supported product table was available to this parser.", "NO_SUPPORTED_PRODUCT_RECORD")
    for product in products:
        model, family = text(product, "model"), product_family(product, profile)
        if model is None or family not in profile["families"] or sum(text(p, "model") == model for p in products) != 1:
            add("IND-SELECTION", model, "UNKNOWN", "Product identity or configured family applicability is unresolved.", "IDENTITY_OR_FAMILY_AMBIGUOUS")
            continue
        spec = profile["families"][family]
        paths = [r for r in native_rows if r["observation"]["rule_id"] == "DISC-02"
                 and r["observation"]["result"] == "PASS" and r.get("target_response", {}).get("url") == product["url"]]
        add("IND-SELECTION", model, "PASS" if paths else "UNKNOWN",
            "A replayed category-to-product path reaches this source-declared model and family." if paths else "A model was observed but its category-to-product route was not proven.",
            "NATIVE_PATH_AND_DECLARED_MODEL" if paths else "PATH_NOT_OBSERVED", refs(product, "model", "family"),
            details={"native_path_observation_ids": [p["observation"]["observation_id"] for p in paths]})
        missing = [key for key in spec["critical"] if field(product, key) is None]
        unusable = [key for key in spec["critical"] if field(product, key) is not None and (usable(product, key) is None
                    or (key in spec["dimensions"] and (quantity(text(product, key), profile) is None
                        or quantity(text(product, key), profile)[0] != spec["dimensions"][key])))]
        add("IND-SPEC", model, "UNKNOWN" if missing or unusable else "PASS",
            "Some configured procurement attributes were not unambiguously usable; this does not establish absence." if missing or unusable else "Configured procurement attributes have source values and supported units where required; correctness is unverified.",
            "ATTRIBUTE_COVERAGE_GAP" if missing or unusable else "CONFIGURED_ATTRIBUTES_OBSERVED", refs(product, *spec["critical"]),
            details={"family": family, "observed_attributes": {k: field(product, k) for k in spec["critical"] if field(product, k)}, "not_observed": missing, "unusable_values": unusable},
            recommendation="Request the unresolved specification fields and linked datasheet from the supplier; retain the supplied revision for comparison.")
        application = matching(pages, profile["record_types"]["application"], model)
        for attribute, duty, direction in spec["comparisons"]:
            actual, required = quantity(text(product, attribute), profile), quantity(text(application, duty), profile)
            proof = refs(product, attribute) + refs(application, duty, "models")
            comparable = actual is not None and required is not None and actual[0] == required[0]
            if not comparable:
                result, statement, reason = "UNKNOWN", "No unambiguous model-linked scalar pair with supported matching units is available.", "SCALAR_OR_SCENARIO_UNRESOLVED"
            else:
                satisfied = actual[1] >= required[1] if direction == "at_least" else actual[1] == required[1]
                result = "PASS" if satisfied else "FAIL_WITH_EVIDENCE"
                statement = f"Source-listed {attribute} {text(product, attribute)} {'meets' if satisfied else 'does not meet'} the configured scalar comparison to scenario {text(application, duty)}; this is not engineering fit confirmation."
                reason = "LISTED_SCALAR_COMPARISON_ONLY" if satisfied else "EXPLICIT_SOURCE_SCALAR_CONFLICT"
            add("IND-DUTY", model, result, statement, reason, proof,
                details={"attribute": attribute, "scenario_field": duty, "comparison": direction, "fit_status": "UNKNOWN"},
                recommendation="Confirm the selected operating point and limits with the supplier before using this model; request an alternative if the stated duty cannot be met.")
        add("IND-FIT", model, "UNKNOWN", "Catalog values do not establish application suitability or safe operation.", "ENGINEERING_VERIFICATION_REQUIRED",
            refs(product, "model"), details={"questions": spec["fit_unknowns"], "medium_source": text(application, "duty_medium"), "engineering_fit": "UNKNOWN"},
            recommendation="Obtain supplier engineering confirmation for the stated medium, operating envelope and installation; do not substitute a catalog comparison for that review.")
        if family == "valve":
            add("IND-DUTY", model, "NOT_APPLICABLE", "Motor electrical comparison is outside this declared valve profile; actuator requirements were not established.", "PROFILE_EXCLUDES_MOTOR_COMPARISON", refs(product, "family"), details={"attribute": "motor_electrical"})
        supplier = matching(pages, profile["record_types"]["supplier"], model)
        proof_fields = ("models", "issuer", "certificate", "valid_until")
        validity = text(supplier, "valid_until")
        try:
            expiry = date.fromisoformat(validity) if validity else None
        except ValueError:
            expiry = None
        supplier_refs = refs(supplier, "valid_until")
        captured_at = by_ref[supplier_refs[0]]["source"]["citation"]["observed_at"] if supplier_refs else pack.document["snapshots"][0]["observed_at"]
        captured = date.fromisoformat(captured_at[:10])
        result = "UNKNOWN" if expiry is None else "FAIL_WITH_EVIDENCE" if expiry < captured else "PASS"
        add("IND-PROOF", model, result, "The supplier-stated validity date precedes the capture date; neither certificate authenticity nor actual supplier qualification is established." if result == "FAIL_WITH_EVIDENCE" else "A supplier-stated validity date is not earlier than capture; authenticity remains UNKNOWN." if result == "PASS" else "Proof validity could not be compared; no qualification defect is asserted.",
            "SOURCE_DATE_PRECEDES_CAPTURE" if result == "FAIL_WITH_EVIDENCE" else "SOURCE_PROOF_CONTEXT_ONLY", refs(supplier, *proof_fields),
            details={"declared_issuer": text(supplier, "issuer"), "declared_reference": text(supplier, "certificate"), "declared_valid_until": validity, "independent_authentication": "UNKNOWN"},
            recommendation="Ask for a current model-relevant certificate and independently verify issuer, scope and validity before treating it as supplier proof.")
        guide = matching(pages, profile["record_types"]["rfq"], model)
        source_labels = [v.strip() for v in (text(guide, "rfq_fields") or "").split(",") if v.strip()]
        required = []
        for label in source_labels:
            canonical = [k for k, aliases in profile["labels"].items() if normalized(label) in {normalized(v) for v in aliases}]
            required.append(canonical[0] if len(canonical) == 1 else label)
        # Only the source-declared input names are required. Unknown names stay
        # unresolved instead of silently reducing a supplier's requirements.
        available = {"model": field(product, "model")}
        for key in required:
            if key != "model":
                available[key] = usable(application, key)
        missing = [k for k in required if not available.get(k)]
        contact = [r for r in native_rows if r["observation"]["rule_id"] == "CTA-02"
                   and r["observation"]["result"] == "PASS" and r.get("source_page", {}).get("url") == product["url"]]
        add("IND-RFQ", model, "PASS" if required and not missing and contact else "UNKNOWN",
            "The declared RFQ inputs and a product-context contact GET path were observed; no message was sent." if required and not missing and contact else "The RFQ packet has unresolved buyer inputs or route coverage; no failed inquiry or website defect is asserted.",
            "RFQ_INPUTS_AND_NATIVE_GET_PATH" if required and not missing and contact else "RFQ_INPUT_OR_PATH_GAP",
            refs(guide, "models", "rfq_fields") + refs(product, "model"),
            details={"required_by_source": required, "source_required_labels": source_labels, "missing_buyer_inputs": missing, "native_contact_observation_ids": [r["observation"]["observation_id"] for r in contact]},
            recommendation="Fill the unresolved buyer inputs, attach the selected model and operating conditions, and have a human review the inquiry before sending.")
        rfq_packets.append({"model": model, "source_guide_fact_refs": refs(guide, "models", "rfq_fields"), "source_required_labels": source_labels, "inputs": available,
                            "missing_buyer_inputs": missing, "requirements_status": "OBSERVED" if required else "UNKNOWN",
                            "contact_observation_ids": [r["observation"]["observation_id"] for r in contact], "submission_performed": False})
    return assessments, rfq_packets


def procurement_projection(assessments, profile):
    """Reference the same Observations; no parallel evidence or aggregate score."""
    coverage = []
    for rule in profile["rules"]:
        rows = [a for a in assessments if a["observation"]["rule_id"] == rule["rule_id"]]
        coverage.append({"rule_id": rule["rule_id"], "status": "EXECUTED" if rows else "UNKNOWN_INPUT_UNAVAILABLE",
                         "observation_ids": [a["observation"]["observation_id"] for a in rows],
                         "observed_results": sorted({a["observation"]["result"] for a in rows})})
    phases = [("PRODUCT_DISCOVERY", ["IND-SELECTION"]), ("PRODUCT_AND_SPECIFICATION", ["IND-SPEC"]),
              ("APPLICATION_REVIEW", ["IND-DUTY", "IND-FIT"]), ("SUPPLIER_PROOF_CONTEXT", ["IND-PROOF"]),
              ("CONTACT_AND_RFQ", ["IND-RFQ"])]
    chains = []
    for model in sorted({a["model"] for a in assessments if a["model"] is not None}):
        stages = []
        for phase, rules in phases:
            rows = [a for a in assessments if a["model"] == model and a["observation"]["rule_id"] in rules]
            stages.append({"stage": phase, "observation_ids": [a["observation"]["observation_id"] for a in rows],
                           "finding_ids": [a["finding"]["finding_id"] for a in rows],
                           "observed_results": sorted({a["observation"]["result"] for a in rows}),
                           "coverage": "EXECUTED" if rows else "UNKNOWN_INPUT_UNAVAILABLE"})
        chains.append({"model": model, "identity_basis": "SOURCE_DECLARED_MODEL_TEXT_ONLY", "stages": stages,
                       "engineering_fit": "UNKNOWN", "supplier_authentication": "UNKNOWN", "inquiry_submitted": False})
    return chains, coverage


def diagnose(pack, *, expected_pack_ref, expected_industry_ref, diagnostic_version=VERSION):
    if diagnostic_version == 'l2-industrial-1.0.6':
        from vrae.rules.replay_scope import execution_scope
        with execution_scope(pack):
            return _diagnose(pack, expected_pack_ref=expected_pack_ref,
                expected_industry_ref=expected_industry_ref, diagnostic_version=diagnostic_version)
    return _diagnose(pack, expected_pack_ref=expected_pack_ref,
                    expected_industry_ref=expected_industry_ref, diagnostic_version=diagnostic_version)


def _diagnose(pack, *, expected_pack_ref, expected_industry_ref, diagnostic_version):
    config = load(tenant_id=pack.document["tenant_id"])
    if config["industry_ref"] != expected_industry_ref or config["industry_pack"]["tenant_id"] != pack.document["tenant_id"]:
        denied()
    execution, package, facts, bundles = source_chain(
        pack, expected_pack_ref, diagnostic_version=diagnostic_version)
    assessments, rfq_packets = analyze(pack, execution, facts, config["profile"])
    chains, rule_coverage = procurement_projection(assessments, config["profile"])
    result = dict(schema_version="1.0", diagnostic_version=diagnostic_version, diagnostic_depth="L2",
                  **{k: pack.document[k] for k in ("tenant_id", "run_id")}, industry_ref=expected_industry_ref,
                  industry_pack=config["industry_pack"], profile=config["profile"], expected_pack_ref=pack.ref,
                  native_execution_ref=execution["execution_ref"], native_package_ref=package.ref,
                  source_guard_refs=[b["guard"]["guard_ref"] for b in bundles], source_facts=facts, source_guard_inputs=bundles,
                  native_report_engine_version="ra3c-disc-1.0.0", native_report_draft_ref=None,
                  native_report_scope="Business data for the existing reviewer/report consumer; this adapter does not create a ReportVersion, HTML renderer or approval.",
                  assessments=assessments, rfq_packets=rfq_packets, procurement_chains=chains, industry_rule_coverage=rule_coverage, recorded_coverage=pack.document["coverage"],
                  buyer_journey=execution.get("journeys", []), private=True, approval_status="NOT_APPROVED", shareable=False,
                  semantic_approval=False, limitations=["OFFLINE_RECORDED_SOURCE_NOT_CURRENT_AUTHORIZATION", "ADAPTER_HAS_NO_NETWORK_CAPABILITY", "SOURCE_DECLARATION_NOT_AUTHENTICITY", "SCALAR_COMPARISON_NOT_ENGINEERING_FIT", "UNKNOWN_NEVER_MEANS_SITE_ABSENCE", "NO_INQUIRY_SUBMISSION_OR_BUSINESS_OUTCOME", "L2_DEPTH_REUSES_EXISTING_BOUNDED_CAPTURE_NO_POLICY_EXPANSION"])
    if diagnostic_version == 'l2-industrial-1.0.6':
        from .procurement import build as procurement_review
        result['procurement_review'] = procurement_review(pack, execution, config['profile'], expected_industry_ref)
    result["diagnosis_ref"] = "l2-" + document_hash(result)
    if len(encode(result)) > 4_000_000:
        denied()
    try:
        validate_export(result)
    except Exception:
        denied()
    return result


def verify(result, pack, *, expected_result_ref, expected_pack_ref, expected_industry_ref):
    try:
        if result["diagnosis_ref"] != expected_result_ref:
            denied()
        rebuilt = diagnose(pack, expected_pack_ref=expected_pack_ref, expected_industry_ref=expected_industry_ref,
                           diagnostic_version=result["diagnostic_version"])
        if encode(deepcopy(result)) != encode(rebuilt):
            denied()
    except Exception:
        denied()
