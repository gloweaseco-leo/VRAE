"""Bounded RED views of actual native/browser files; no stdout reconstruction."""

import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zlib

from integration.ra4b.evidence import sanitized_junit


def native_failure_views(path, *, retain_passed_original=False):
    raw = path.read_bytes()
    curated, _ = sanitized_junit(raw)
    cases = list(ET.fromstring(raw).iter('testcase'))
    bad = sum(any(c.find(k) is not None for k in ('failure', 'error', 'skipped')) for c in cases)
    original_pass = retain_passed_original and bool(cases) and bad == 0
    if original_pass:
        tree = ET.fromstring(raw)
        # Never expose traceback/captured streams as an "original PASS" file.
        original_pass = not any(list(tree.iter(k)) for k in ('system-out', 'system-err', 'properties'))
        original_pass = original_pass and not re.search(rb'Bearer\s+|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.', raw)
    if original_pass:
        curated = raw
    retention = {
        'raw_native_sha256': hashlib.sha256(raw).hexdigest(),
        'raw_native_crc32': format(zlib.crc32(raw) & 0xFFFFFFFF, '08x'),
        ('public_original_passed_sha256' if original_pass else 'public_curated_sha256'): hashlib.sha256(curated).hexdigest(),
        'cases': len(cases), 'passed': len(cases) - bad,
        'raw_xml_private': not original_pass, 'stdout_constructed_xml': False,
    }
    return {'native-junit.xml': curated, 'native-retention.json': json.dumps(retention, sort_keys=True).encode()}


def browser_failure_view(root, *, stage='ACTUAL_BROWSER_RED_NOT_PASS'):
    assert stage in {'ACTUAL_BROWSER_RED_NOT_PASS', 'POST_BROWSER_GATES_NOT_CLEARED'}
    suites = []
    for name in ('accepted', 'b5b'):
        folder = root / (name + '-browser')
        row = {'suite': name, 'status': 'NOT_STARTED'}
        failure = folder / 'browser-failure.json'
        passed = folder / 'browser.json'
        if failure.exists() or passed.exists():
            actual = failure if failure.exists() else passed
            report = json.loads(actual.read_bytes())
            records = report.get('records', [])
            row.update(status='RED' if failure.exists() else 'REPORT_RECORDED_NOT_CLEANUP_CLEARANCE',
                       raw_report_sha256=hashlib.sha256(actual.read_bytes()).hexdigest(),
                       completed_assertions=len(records), passed_assertions=sum(r.get('pass') is True for r in records))
            for field in ('code', 'phase', 'step'):
                value = report.get(field)
                if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_./-]{1,160}', value):
                    row[field] = value
            row['failed_assertions'] = [r['name'] for r in records if r.get('pass') is False
                and isinstance(r.get('name'), str) and re.fullmatch(r'[A-Za-z0-9_./-]{1,160}', r['name'])]
            row['failed_layout_metrics'] = [
                {k: r.get('metadata', {})[k] for k in ('width', 'scroll', 'scripts', 'jwt')
                 if type(r.get('metadata', {}).get(k)) in (int, bool)}
                for r in records if r.get('pass') is False
            ]
        cleanup = folder / 'browser-process-cleanup.json'
        if cleanup.exists():
            original = json.loads(cleanup.read_bytes())
            row['cleanup'] = {k: original[k] for k in ('exit_observed', 'graceful', 'forced') if type(original.get(k)) is bool}
        suites.append(row)
    cleanups = []
    for path in root.rglob('cleanup.json'):
        original = json.loads(path.read_bytes())
        if 'resources' in original:
            cleanups.append({'port_closed': original.get('port_closed') is True,
                'resources_absent': all(r.get('absent') is True for r in original['resources']),
                'resource_count': len(original['resources'])})
    return json.dumps({'status': stage, 'suites': suites,
                       'owned_pg_cleanup': cleanups, 'raw_logs_private': True}, sort_keys=True).encode()


REVISION_CASE = 'test_revision_race_after_original_read_before_submit'
REVISION_BEFORE = 'd8c87d4d07455a11d7fa8c430e6d41fb3938f0952418319eb3647aa1be75c3a6'
REVISION_AFTER = '3fa303b13c4f65b180aea95ce9a2bf82ad0f49b3e45597c5c62fee6a2542dcc5'


def verify_protected_observations(original, consumer):
    """Preserve the frozen original negative's exact v2-append expectation.

    Independently held accepted B5-P0 evidence has this one transition. It is
    not a generic exception for changed roots: source bytes, both full roots,
    suite, exact case, count and zero business rows must all match.
    """
    root = Path(__file__).resolve().parents[2]
    holds = {
        'integration/ra4c_b5p0/cases.py': '40016f1a6bbc997cd8e6350928c0a119bb1dd1928b2ebb34fd994fd56f780781',
        'integration/b3_p0/support.py': '1f78dc7d33c69a337848b4c9e172a91ffef15a8172ec5d90f1c246fcefe1dca6',
    }
    assert all(hashlib.sha256((root/n).read_bytes()).hexdigest() == h for n, h in holds.items())
    assert len(original) == len({r['case_id'] for r in original}) == 53
    assert len(consumer) == 32
    expected = [r for r in original if r['case_id'] == REVISION_CASE]
    assert len(expected) == 1
    row = expected[0]
    assert row['protected_roots_before'] == REVISION_BEFORE
    assert row['protected_roots_after'] == REVISION_AFTER
    assert set(row['counts']) == {'states', 'intents', 'claims', 'sections', 'audit', 'outbox'}
    assert all(type(v) is int and v == 0 for v in row['counts'].values())
    assert all(r['protected_roots_before'] == r['protected_roots_after']
               for r in original if r['case_id'] != REVISION_CASE)
    assert all(r['protected_roots_before'] == r['protected_roots_after'] for r in consumer)
    return {'accepted_original_revision_case': REVISION_CASE,
            'exact_before': REVISION_BEFORE, 'exact_after': REVISION_AFTER,
            'original_source_sha256': holds, 'original_other_unchanged': 52,
            'consumer_and_browser_unchanged': 32, 'business_writes_in_revision_case': 0}
