"""A literal source anchor never upgrades an UNKNOWN rule into PASS."""
from dataclasses import replace
import hashlib

from integration.s3_offline.fixture import context, NOW
from tests.s2_contract.batch2_fixtures import fixture
from vrae.industry.l2_v1 import diagnose, load
from vrae.l2.native import NativeSource
from vrae.intelligence.common import encode
from vrae.intelligence.s3 import prepare_context


def test_partial_literal_product_context_can_reach_original_qwen_gateway():
    original = context()
    pack = fixture(overrides={'/products/p40': b'<html><body><main><h1>Grinding wheel W100</h1><p>Source descriptive text without a reliable parameter pair.</p></main></body></html>'})
    data = diagnose(pack, expected_pack_ref=pack.ref, expected_industry_ref=load(tenant_id=pack.document['tenant_id'])['industry_ref'], diagnostic_version='l2-industrial-1.0.2')
    task = replace(original.completion.task, native_pack_ref=pack.ref, diagnosis_ref=data['diagnosis_ref'],
        source_bundle_sha256=hashlib.sha256(encode(pack.document)).hexdigest())
    source = NativeSource(pack, data, held=task)
    completion = replace(original.completion, task=task, report_content_hash=source.read().version['content_hash'])
    prepared = prepare_context(pack, source, {}, buyer_pins=None, completion=completion, now=NOW)
    assert any(e['fact']['observation_result'] == 'UNKNOWN' for e in prepared.catalog['entries'].values())
