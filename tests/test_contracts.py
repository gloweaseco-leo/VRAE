"""Schema correctness, structured positive/negative fixtures and interface inventory."""

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from vrae.domain.contracts import ROOT, load_schema, validate_contract

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"
VALID = json.loads((FIXTURES / "valid.json").read_text())
INVALID = json.loads((FIXTURES / "invalid.json").read_text())


@pytest.mark.parametrize("path", sorted(ROOT.glob("*.schema.json")), ids=lambda x: x.stem)
def test_schemas_are_valid_2020_12(path: Path) -> None:
    Draft202012Validator.check_schema(json.loads(path.read_text()))


@pytest.mark.parametrize("case", VALID, ids=lambda c: c["schema"])
def test_valid_structured_samples(case: dict) -> None:
    validate_contract(case["schema"], case["data"])


@pytest.mark.parametrize("case", INVALID, ids=lambda c: c["schema"] + ":" + c["reason"])
def test_invalid_structured_samples_are_rejected(case: dict) -> None:
    with pytest.raises(ValidationError):
        validate_contract(case["schema"], case["data"])


def test_openapi_is_contract_only_and_references_real_schemas() -> None:
    spec = yaml.safe_load((ROOT / "openapi.yaml").read_text())
    assert spec["openapi"] == "3.1.0"
    assert spec["servers"] == []
    expected = {
        "/v1/audit-requests", "/v1/audits/{audit_id}",
        "/v1/audits/{audit_id}/report",
        "/v1/audits/{audit_id}/review-decisions",
        "/v1/reports/{report_id}/share-grants",
        "/v1/audits/{audit_id}/sales-handoffs", "/v1/health",
    }
    assert set(spec["paths"]) == expected
    def refs(node: object) -> list[str]:
        if isinstance(node, dict):
            return ([node["$ref"]] if "$ref" in node else []) + [
                ref for child in node.values() for ref in refs(child)
            ]
        if isinstance(node, list):
            return [ref for child in node for ref in refs(child)]
        return []
    for ref in refs(spec):
        if ref.startswith("./"):
            assert (ROOT / ref[2:]).exists(), ref


def test_python_json_schema_authority_same_required_fields() -> None:
    for case in VALID:
        schema = load_schema(case["schema"])
        assert set(case["data"]) == set(schema["required"])
        assert schema["additionalProperties"] is False


def test_unknown_cost_not_implicitly_zero_in_contract() -> None:
    sample = next(c["data"] for c in VALID if c["schema"] == "UsageRecord")
    assert sample["amount"] is None
    assert sample["input_tokens"] is None
    assert sample["cost_status"] == "UNKNOWN"
    validate_contract("UsageRecord", sample)


def test_industry_pack_is_schema_versioned_and_extensible() -> None:
    p = json.loads((ROOT.parents[1] / "industry-packs" / "industrial_parts.v1.json").read_text())
    validate_contract("IndustryPack", p)
    another = {**p, "industry_id": "solar_equipment", "critical_attributes": ["wattage"]}
    validate_contract("IndustryPack", another)


def test_no_execution_state_means_business_conversion() -> None:
    run_enum = load_schema("AuditRun")["properties"]["status"]["enum"]
    assert "APPROVED" not in run_enum
    assert "SHARE_GRANTED" not in run_enum
    assert "E2" not in run_enum and "E3" not in run_enum
