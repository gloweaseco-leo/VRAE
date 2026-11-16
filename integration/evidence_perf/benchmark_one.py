"""Fresh process, fixed P40/V25 bytes, original producer and full Guard paths.

The context is a synthetic consistency fixture, NOT an actual PG lease/commit.
No clock/lease/Worker production code is patched. The real PR112 task remains C3.
"""

import argparse
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.http_transport import FetchResponse
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess
from vrae.collection.manifest import CaptureBundle
import vrae.evidence.pack as implementation
from vrae.evidence import EvidencePack, build_pack
from vrae.industry.l2_v1 import diagnose, load, verify
from vrae.application.ra4b_p2.producer import LeaseContext, capture_digest, encode
from vrae.application.ra4b_p2.m1.producer import produce, replay

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
RUN = '22222222-2222-4222-8222-222222222222'


def fixture():
    source = json.loads((ROOT / 'docs/03-engineering/l2-industrial-v1/example/source.json').read_bytes())
    entry = source['pack']['sources'][0]
    objects = {k: base64.b64decode(v, validate=True) for k, v in source['objects_base64'].items()}
    routes = {}
    for page in entry['document']['pages']:
        snapshot = page['snapshot']
        routes[snapshot['url']] = objects[entry['object_refs'][snapshot['private_object_ref']]]
    routes['https://example.org/robots.txt'] = b'User-agent: *\nDisallow:\n'
    cases = json.loads((ROOT / 'tests/fixtures/contracts/valid.json').read_bytes())
    audit, policy = [next(c['data'] for c in cases if c['schema'] == n) for n in ('AuditRequest', 'SourcePolicy')]
    audit.update(tenant_id='tenant-test', source_policy_ref='policy-perf', source_policy_version=1)
    policy.update(tenant_id='tenant-test', policy_id='policy-perf', policy_version=1)
    access = SourceAccess(audit, lambda: policy, terms_reference='P40_V25_OFFLINE_PERFORMANCE_FIXTURE', now=lambda: NOW)

    class DNS:
        async def resolve(self, host):
            assert host == 'example.org'
            return ('93.184.216.20',)

    class Transport:
        async def exchange(self, url, method, ip, budget, max_bytes):
            assert method == 'GET' and url in routes
            body = routes[url]
            assert len(body) <= max_bytes
            budget.consume(len(body))
            return FetchResponse(url, 200, {'content-type': 'text/plain' if url.endswith('robots.txt') else 'text/html'}, body, ip)

    capture = asyncio.run(Collector(SafeFetcher(DNS(), Transport())).capture(
        RUN, access, limits=Limits(max_pages=8, interval_seconds=0.01), retain_raw_html=True))
    assert len(capture.manifest['pages']) == 8
    context = LeaseContext('tenant-test', '11111111-1111-4111-8111-111111111111', RUN,
        '33333333-3333-4333-8333-333333333333', 'ra4b_test_a_worker',
        '44444444-4444-4444-8444-444444444444', 1, (NOW + timedelta(seconds=30)).isoformat(), 1,
        'perf-p40-v25', '1' * 64, capture_digest(capture), 'policy-perf', 1,
        hashlib.sha256(encode(policy)).hexdigest(), NOW.isoformat())
    return capture, access, context


def memory():
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

        value = Counters()
        value.cb = ctypes.sizeof(value)
        process = ctypes.windll.kernel32.GetCurrentProcess
        process.restype = wintypes.HANDLE
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        query.restype = wintypes.BOOL
        if not query(process(), ctypes.byref(value), value.cb):
            raise OSError('MEMORY_MEASUREMENT_FAILED')
        return {'peak_rss_bytes': value.PeakWorkingSetSize, 'rss_bytes': value.WorkingSetSize}
    import resource
    return {'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--variant', required=True)
    args = parser.parse_args()
    counts = {'verify': 0, 'project': 0, 'verify_wall_seconds': 0.0}
    original_verify, original_project = EvidencePack.verify, implementation._project

    def observed_verify(self, **kw):
        counts['verify'] += 1
        start = time.perf_counter()
        try:
            return original_verify(self, **kw)
        finally:
            counts['verify_wall_seconds'] += time.perf_counter() - start

    def observed_project(*a, **kw):
        counts['project'] += 1
        return original_project(*a, **kw)

    EvidencePack.verify = observed_verify
    implementation._project = observed_project
    phases = []

    def phase(name, call):
        wall, cpu, before = time.perf_counter(), time.process_time(), dict(counts)
        value = call()
        phases.append({'name': name, 'wall_seconds': time.perf_counter() - wall,
                       'cpu_seconds': time.process_time() - cpu,
                       'verify_calls': counts['verify'] - before['verify'],
                       'full_project_calls': counts['project'] - before['project'],
                       'verify_wall_seconds': counts['verify_wall_seconds'] - before['verify_wall_seconds']})
        return value

    capture, access, context = fixture()
    output = phase('original_m1_produce', lambda: produce(capture, access, context, now=NOW))
    phase('mandatory_precommit_replay', lambda: replay(output))
    pack = phase('new_industry_boundary_load', lambda: build_pack([CaptureBundle(capture.manifest, dict(capture.objects))]))
    industry_ref = load(tenant_id='tenant-test')['industry_ref']
    result = phase('full_native_industry_diagnose', lambda: diagnose(pack, expected_pack_ref=pack.ref, expected_industry_ref=industry_ref))
    phase('full_industry_export_verify', lambda: verify(result, pack, expected_result_ref=result['diagnosis_ref'], expected_pack_ref=pack.ref, expected_industry_ref=industry_ref))
    receipt = {'kind': 'OFFLINE_ORIGINAL_PRODUCER_AND_GUARD_NOT_ACTUAL_PG_LEASE_OR_COMMIT', 'variant': args.variant,
               'python': sys.version, 'pid': os.getpid(), 'clock': 'perf_counter wall and process_time CPU; no cProfile',
               'phases': phases, 'counts': counts, 'memory': memory(), 'lease_context_seconds': 30,
               'actual_pg_worker_trial': 'NOT_PERFORMED_C3_UNMERGED_PR112_LAUNCHER_NOT_IMPORTED',
               'capture_sha256': capture_digest(capture), 'input_product_body_sha256': {
                   p['snapshot']['url']: p['snapshot']['sha256'] for p in capture.manifest['pages']},
               'output_sha256': {key: hashlib.sha256(getattr(output, key)).hexdigest() for key in ('source', 'report', 'html', 'binding')},
               'diagnosis_ref': result['diagnosis_ref'], 'diagnosis_bytes_sha256': hashlib.sha256(encode(result)).hexdigest(),
               'assessment_results': [a['observation']['result'] for a in result['assessments']]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps({'variant': args.variant, 'phases': phases, 'memory': receipt['memory']}), flush=True)


if __name__ == '__main__':
    main()
