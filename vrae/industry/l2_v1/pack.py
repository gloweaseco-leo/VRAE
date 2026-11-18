"""Trusted versioned IndustryPack configuration, separate from SourcePolicy."""

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from vrae.evidence import EvidenceError

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


@dataclass(frozen=True, slots=True)
class IndustryPins:
    """Independently held tenant configuration selection; not access authority."""
    industry_ref: str
    tenant_id: str
    version: str = '1.1.0'
    profile_id: str = 'industrial'


def load_s2(*, tenant_id=None, version='1.1.0', profile_id='industrial'):
    """Add a pinned overlay to the same IndustryPack; original load() stays v1."""
    try:
        if type(version) is not str or version != '1.1.0' or type(profile_id) is not str:
            raise ValueError('VERSION_OR_PROFILE')
        parent = load()
        overlay = json.loads((DIRECTORY / 's2-1.1.0.json').read_text(encoding='utf-8'))
        if (overlay['version'] != version or overlay['parent_version'] != parent['profile']['version']
                or document_hash(parent['industry_pack']) != overlay['parent_pack_sha256']
                or document_hash(parent['profile']) != overlay['parent_profile_sha256']
                or profile_id not in overlay['profiles']):
            raise ValueError('PARENT_OR_PROFILE')
        parent = load(tenant_id=tenant_id)
        industry, profile = deepcopy(parent['industry_pack']), deepcopy(parent['profile'])
        industry.update(version=version, methodology_version='V1.1-L2-industrial-' + version)
        profile['version'] = version
        profile['labels'].update(overlay['labels'])
        profile['record_types'].update(overlay['record_types'])
        profile['rules'].extend(overlay['s2_rules'])
        profile['s2'] = overlay
        profile['selected_profile_id'] = profile_id
        industry['applicable_rule_ids'] = [r['rule_id'] for r in profile['rules']]
        industry['critical_attributes'] += ['source-declared data revision and specification conditions',
                                            'source-declared identifier namespace and identifier']
        validate_contract('IndustryPack', industry)
        result = {'industry_pack': industry, 'profile': profile,
                  'parent_industry_ref': parent['industry_ref']}
        result['industry_ref'] = 'ip-' + document_hash(result)
        return result
    except Exception as exc:
        raise EvidenceError('S2_INDUSTRY_CONFIGURATION') from exc
