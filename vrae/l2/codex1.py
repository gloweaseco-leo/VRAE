"""Pinned producer contract inspection; never upgrades exports into Guard authority."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .report import deny

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class HeldDiagnosis:
    """Server-held expectations, acquired independently from the submitted export."""
    tenant_id: str
    run_id: str
    industry_ref: str
    pack_ref: str
    diagnosis_ref: str
    export_sha256: str


def inspect_export(raw: bytes, held: HeldDiagnosis) -> dict[str, Any]:
    """Read a pinned offline example, with local-only schema resolution.

    This function deliberately cannot issue a ReportVersion, an approval, task
    assignment or access grant. Source/Guard replay belongs to the accepted
    producer's verify(data, pack, expected_*_ref=server_held_refs), not JSON Schema.
    """
    if len(raw) > 4_000_000 or hashlib.sha256(raw).hexdigest() != held.export_sha256:
        deny('L2_EXPORT_PIN_MISMATCH')
    try:
        data = json.loads(raw)
        schema = json.loads((ROOT/'contracts/l2_consumer/BuyerDiagnosis.upstream-v1.schema.json').read_text(encoding='utf-8'))
        resources = []
        for path in (ROOT/'contracts/v1').glob('*.schema.json'):
            item = json.loads(path.read_text(encoding='utf-8'))
            resources.append((item['$id'], Resource.from_contents(item)))
        registry: Registry = Registry().with_resources(resources)
        Draft202012Validator(schema, registry=registry, format_checker=FormatChecker()).validate(data)
        json.dumps(data, allow_nan=False)
    except Exception:
        # Includes unknown references: Registry has no network retrieval callback.
        deny('L2_EXPORT_CONTRACT_INVALID')
    expected = {'tenant_id': held.tenant_id, 'run_id': held.run_id,
                'industry_ref': held.industry_ref, 'expected_pack_ref': held.pack_ref,
                'diagnosis_ref': held.diagnosis_ref}
    if any(data.get(k) != v for k, v in expected.items()):
        deny('L2_EXPORT_CONTEXT_MISMATCH')
    return {'assurance': 'OFFLINE_CONTRACT_INSPECTED_NOT_NATIVE_REPLAYED',
            'formal_human_review': False, 'task_assignment': None,
            'report_version': None, 'approval': None,
            'buyer_tasks': data['procurement_chains'],
            'observations': data['assessments'], 'rfq': data['rfq_packets'],
            'coverage': data['industry_rule_coverage'],
            'source_facts': data['source_facts'], 'limitations': data['limitations']}
