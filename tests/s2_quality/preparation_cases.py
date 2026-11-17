"""Preparation integrity adversaries; no Worker/browser/Gold result is fabricated."""
from copy import deepcopy
import socket

import pytest

from integration.l2_ops.s2_acceptance_prepare import build_plan, verify_plan, PlanError


def test_preparation_is_offline_and_keeps_real_identity_unknown(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("UNEXPECTED_NETWORK")
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    plan = build_plan()
    assert verify_plan(plan)["runtime_acceptance"] is False
    assert {c["site_type"] for c in plan["catalog"]} == {
        "STATIC", "CMS", "SPA", "MULTI_SKU", "MULTILINGUAL"
    }
    assert all(v is None for lane in plan["future_lanes"]
               for v in lane["actual_runtime_identity"].values())
    assert len(plan["industrial_cases"]) == 9
    assert all(c["observed"] is None for c in plan["adversarial_requirements"])


@pytest.mark.parametrize("attack", [
    "claim_runtime_pass", "invent_pack", "drop_scope", "alter_raw_fixture",
    "unknown_to_pass", "invent_gold", "allow_merge", "erase_model_limit",
])
def test_preparation_tampering_never_becomes_runtime_or_gold_proof(attack):
    value = deepcopy(build_plan())
    if attack == "claim_runtime_pass":
        value["runtime_acceptance"] = True
    elif attack == "invent_pack":
        value["future_lanes"][0]["actual_runtime_identity"]["pack_ref"] = "fake-pack"
    elif attack == "drop_scope":
        value["catalog"][0]["scope_before_capture"].pop()
    elif attack == "alter_raw_fixture":
        value["catalog"][0]["fixture_routes"][0]["body_sha256"] = "0" * 64
    elif attack == "unknown_to_pass":
        unit = next(u for c in value["catalog"] for u in c["authored_expectations_not_gold"]
                    if u["expected"] == "UNKNOWN")
        unit["expected"] = "PASS"
    elif attack == "invent_gold":
        value["gold"]["new_verified"] = 32
    elif attack == "allow_merge":
        value["dependency_gate"]["merge_permission"] = True
    else:
        value["model_calls"] = 1
    with pytest.raises(PlanError, match="PREPARATION_PLAN_CHANGED"):
        verify_plan(value)
