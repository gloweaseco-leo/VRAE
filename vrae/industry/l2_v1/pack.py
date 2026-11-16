"""Trusted versioned IndustryPack configuration, separate from SourcePolicy."""

import json
from pathlib import Path

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / "industry-packs/l2-industrial-v1"


def load(*, tenant_id=None):
    industry = json.loads((DIRECTORY / "IndustryPack.json").read_text(encoding="utf-8"))
    profile = json.loads((DIRECTORY / "profile.json").read_text(encoding="utf-8"))
    if tenant_id is not None:
        # Tenant-bound configuration, never data-read/DB authority. Callers pin
        # this ref from their authenticated server context before diagnosis.
        industry["tenant_id"] = tenant_id
    validate_contract("IndustryPack", industry)
    if industry["applicable_rule_ids"] != [r["rule_id"] for r in profile["rules"]]:
        raise ValueError("INDUSTRY_PROFILE_INTEGRITY")
    return {"industry_pack": industry, "profile": profile,
            "industry_ref": "ip-" + document_hash({"industry_pack": industry, "profile": profile})}
