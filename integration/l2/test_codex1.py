"""Actual pinned C1 data, not a fabricated producer success."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from vrae.l2.codex1 import HeldDiagnosis, inspect_export
from vrae.l2.report import L2Denied

ROOT = Path(__file__).resolve().parents[2]/'fixtures/l2/codex1-contract-v1'


def sample():
    raw = (ROOT/'diagnosis.json').read_bytes()
    held = HeldDiagnosis(**json.loads((ROOT/'held.json').read_text(encoding='utf-8')),
                         export_sha256=hashlib.sha256(raw).hexdigest())
    return raw, held


def test_real_contract_projection_preserves_unknown_and_review_status():
    raw, held = sample()
    view = inspect_export(raw, held)
    assert len(view['source_facts']) == 81 and len(view['observations']) == 19
    assert view['report_version'] is None and view['approval'] is None
    assert view['assurance'] == 'OFFLINE_CONTRACT_INSPECTED_NOT_NATIVE_REPLAYED'
    assert all(c['engineering_fit']=='UNKNOWN' and not c['inquiry_submitted'] for c in view['buyer_tasks'])
    assert all(a['possible_buyer_impact']['status']=='HUMAN_REVIEW_REQUIRED' for a in view['observations'])


def test_export_cannot_supply_authority_or_replace_held_context():
    raw, held = sample()
    with pytest.raises(L2Denied, match='PIN_MISMATCH'):
        inspect_export(raw+b' ', held)
    with pytest.raises(L2Denied, match='CONTEXT_MISMATCH'):
        inspect_export(raw, replace(held, tenant_id='other-tenant'))
    data = json.loads(raw)
    data['approval_status'] = 'APPROVED'
    edited = json.dumps(data).encode()
    with pytest.raises(L2Denied, match='CONTRACT_INVALID'):
        inspect_export(edited, replace(held, export_sha256=hashlib.sha256(edited).hexdigest()))
