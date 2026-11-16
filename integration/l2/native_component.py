"""Accepted native C1 fixture pipeline for component evidence, NOT Worker E2E."""
from functools import lru_cache

from integration.industry_l2.fixture import evidence_pack
from vrae.industry.l2_v1 import load, diagnose
from vrae.l2.native import NativeTask, NativeSource


@lru_cache(maxsize=1)
def source():
    pack,_,transport=evidence_pack()
    if not all(method=='GET' for method,_ in transport.requests):
        raise ValueError('NATIVE_COMPONENT_NO_SEND')
    industry=load(tenant_id=pack.document['tenant_id'])
    data=diagnose(pack,expected_pack_ref=pack.ref,expected_industry_ref=industry['industry_ref'])
    held=NativeTask(pack.document['tenant_id'],'component-request-not-app202',pack.document['run_id'],
        'component-job-not-worker','component-event','component-source',pack.ref,industry['industry_ref'],
        data['diagnosis_ref'],'1'*64,'OFFLINE_SYNTHETIC','2026-11-16T12:00:00+00:00')
    return NativeSource(pack,data,held=held)
