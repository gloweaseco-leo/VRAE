"""Bounded RED views of actual native/browser files; no stdout reconstruction."""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zlib

from integration.ra4b.evidence import sanitized_junit


def native_failure_views(path):
    raw = path.read_bytes()
    curated, _ = sanitized_junit(raw)
    cases = list(ET.fromstring(raw).iter('testcase'))
    bad = sum(any(c.find(k) is not None for k in ('failure', 'error', 'skipped')) for c in cases)
    retention = {
        'raw_native_sha256': hashlib.sha256(raw).hexdigest(),
        'raw_native_crc32': format(zlib.crc32(raw) & 0xFFFFFFFF, '08x'),
        'public_curated_sha256': hashlib.sha256(curated).hexdigest(),
        'cases': len(cases), 'passed': len(cases) - bad,
        'raw_xml_private': True, 'stdout_constructed_xml': False,
    }
    return {'native-junit.xml': curated, 'native-retention.json': json.dumps(retention, sort_keys=True).encode()}


def browser_failure_view(root):
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
    return json.dumps({'status': 'ACTUAL_BROWSER_RED_NOT_PASS', 'suites': suites,
                       'owned_pg_cleanup': cleanups, 'raw_logs_private': True}, sort_keys=True).encode()
