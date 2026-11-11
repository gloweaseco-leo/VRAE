"""Structural evidence provenance and rule-result guards, no model inference."""

from .errors import DomainError

VALID_RESULTS = {
    "PASS", "FAIL_WITH_EVIDENCE", "UNKNOWN",
    "ACCESS_BLOCKED", "NOT_APPLICABLE",
}


def validate_evidence_graph(
    snapshot: dict, evidence: dict, observation: dict, finding: dict
) -> None:
    tenant = snapshot["tenant_id"]
    run = snapshot["run_id"]
    for item in (evidence, observation, finding):
        if item["tenant_id"] != tenant:
            raise DomainError("FORBIDDEN_TENANT", "Mixed-tenant evidence")
        if item["run_id"] != run:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Mixed-run evidence")
    if evidence["snapshot_id"] != snapshot["snapshot_id"]:
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "Evidence snapshot not found")
    if evidence["certainty"] == "OBSERVED" and (
        snapshot["status"] != "FETCHED"
        or not snapshot.get("sha256")
        or not evidence.get("checksum")
    ):
        raise DomainError(
            "EVIDENCE_INSUFFICIENT", "Observed facts require a fetched, hashed snapshot"
        )
    evidence_ids = {evidence["evidence_id"]} if evidence["certainty"] == "OBSERVED" else set()
    result = observation["result"]
    if result not in VALID_RESULTS:
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "Unknown rule result")
    if result in ("PASS", "FAIL_WITH_EVIDENCE"):
        if observation["kind"] != "OBJECTIVE" or not observation["evidence_ids"]:
            raise DomainError("EVIDENCE_INSUFFICIENT", "Objective rule needs evidence")
        if not set(observation["evidence_ids"]) <= evidence_ids:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Fabricated evidence ID")
    elif observation["kind"] != "UNKNOWN" or observation["evidence_ids"]:
        raise DomainError("EVIDENCE_INSUFFICIENT", "Unobserved cannot be objective")
    if finding["observation_id"] != observation["observation_id"]:
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "Unknown observation")
    if finding["rule_version"] != observation["rule_version"]:
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "Rule versions do not match")
    if finding["kind"] == "OBSERVATION":
        if result not in ("PASS", "FAIL_WITH_EVIDENCE"):
            raise DomainError("EVIDENCE_INSUFFICIENT", "Unknown is not a finding fact")
        if not finding["evidence_ids"] or not set(finding["evidence_ids"]) <= evidence_ids:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Finding evidence unresolved")
    elif finding["kind"] == "UNKNOWN":
        if result not in ("UNKNOWN", "ACCESS_BLOCKED", "NOT_APPLICABLE"):
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Unknown result mismatch")
        if finding["evidence_ids"]:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Unknown may not cite facts")
    elif finding["kind"] in ("HYPOTHESIS", "RECOMMENDATION"):
        if not set(finding["evidence_ids"]) <= evidence_ids:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Unsupported citation")
    else:
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "Unknown finding category")


def classify_rule(observed: bool | None, evidence_ids: list[str]) -> str:
    """Tiny RA-0 rule-result contract, not the RA-2 16-rule implementation."""
    if observed is None:
        return "UNKNOWN"
    if not evidence_ids:
        return "UNKNOWN"
    return "PASS" if observed else "FAIL_WITH_EVIDENCE"


def validate_ai_references(
    interpretation: dict, known_observation_ids: set[str], known_evidence_ids: set[str]
) -> None:
    if not set(interpretation["observation_ids"]) <= known_observation_ids:
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "AI invented an observation ID")
    if not set(interpretation["evidence_ids"]) <= known_evidence_ids:
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "AI invented an evidence ID")
    if interpretation["status"] == "VALIDATED" and not interpretation["observation_ids"]:
        raise DomainError("EVIDENCE_INSUFFICIENT", "No observations to interpret")
    if interpretation["status"] == "NOT_RUN" and any((
        interpretation["hypotheses"], interpretation["recommendations"],
        interpretation["model_id"] is not None,
        interpretation["input_tokens"] is not None,
        interpretation["output_tokens"] is not None,
    )):
        raise DomainError("MODEL_SCHEMA_INVALID", "Unrun model cannot emit interpretations")
    # Semantics of natural-language claims remain RA-3 human/semantic validation.


def validate_ai_scoped_references(
    interpretation: dict, observations: list[dict], evidence: list[dict]
) -> None:
    """Disallow cross-tenant/run aliasing even if an evidence ID happens to match."""
    tenant = interpretation["tenant_id"]
    run = interpretation["run_id"]
    for item in observations + evidence:
        if item["tenant_id"] != tenant:
            raise DomainError("FORBIDDEN_TENANT", "Cross-tenant AI evidence")
        if item["run_id"] != run:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Cross-run AI evidence")
    observed_ids = {item["evidence_id"] for item in evidence
                    if item["certainty"] == "OBSERVED" and item.get("checksum")}
    if len({item["evidence_id"] for item in evidence}) != len(evidence):
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "Ambiguous evidence IDs")
    if len({item["observation_id"] for item in observations}) != len(observations):
        raise DomainError("EVIDENCE_REFERENCE_INVALID", "Ambiguous observation IDs")
    for observation in observations:
        if not set(observation["evidence_ids"]) <= observed_ids:
            raise DomainError("EVIDENCE_REFERENCE_INVALID", "Unresolved observation evidence")
    validate_ai_references(
        interpretation,
        {item["observation_id"] for item in observations},
        observed_ids,
    )
