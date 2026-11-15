"""Finite allowlist publication of native M2 outcomes, never raw private logs."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def main():
    label = sys.argv[1]
    assert re.fullmatch('[a-z0-9-]{3,40}', label)
    private = ROOT / 'integration/b5b/.runtime' / ('m2-native-' + label)
    public = ROOT / 'docs/03-engineering/b5b/evidence' / ('m2-' + label)
    public.mkdir(parents=True, exist_ok=False)
    metadata = {'status': 'INCOMPLETE_NOT_PASS', 'label': label, 'native': [], 'files': {}}
    (public/'publication.json').write_text(json.dumps(metadata, indent=2))
    values = []
    for path in private.rglob('private-credential-scan-values.json'):
        values.extend(json.loads(path.read_bytes()))
    # Original fixture scan-values already include all actual role credentials.
    # Full root-owned restart state remains private to the PG supervisor.
    reviewer_file = private / 'private-m2-reviewers.json'
    if reviewer_file.exists():
        values += list(json.loads(reviewer_file.read_bytes()).values())

    def publish(name, raw):
        decoded = raw.decode('utf-8', errors='ignore')
        assert not any(v and v in decoded for v in values), 'M2_SECRET_SCAN'
        assert not re.search(r'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', decoded), 'M2_JWT_SCAN'
        assert '-----BEGIN PRIVATE KEY' not in decoded and '"Authorization"' not in decoded
        (public / name).write_bytes(raw)
        metadata['files'][name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    try:
        for name, folder, expected in [('native', private, 17), ('restarted', private/'recovered', 2)]:
            raw = (folder/'native-junit.xml').read_bytes()
            receipt = json.loads((folder/'receipt.json').read_bytes())
            assert hashlib.sha256(raw).hexdigest() == receipt['native_junit_sha256']
            cases = list(ET.fromstring(raw).iter('testcase'))
            ids = [c.get('classname') + '::' + c.get('name') for c in cases]
            assert len(ids) == len(set(ids)) == expected
            assert all(c.find(t) is None for c in cases for t in ('failure', 'error', 'skipped', 'system-out', 'system-err'))
            assert receipt['returncode'] == 0 and not receipt['red_or_skipped']
            assert b'<html' not in raw.lower() and b'objects_base64' not in raw
            publish(name+'.xml', raw)
            publish(name+'-receipt.json', (folder/'receipt.json').read_bytes())
            metadata['native'].append({'gate': name, 'cases': expected, 'ids': ids})
        browser = json.loads((private/'browser/browser.json').read_bytes())
        records = browser['records']
        names = []
        for width in (1280, 375, 320):
            for case in ('404', '200'):
                phase = str(width) + '/' + case
                names += [prefix + '-' + phase for prefix in (
                    'real-signed-new-result', 'httponly-new-result-session',
                    'exact-new-job-and-file-hash', 'actual-evidence-and-guard',
                    'actual-supported-issue-on-404' if case == '404' else 'no-invented-issue-on-200',
                    'bounded-generated-report', 'real-persistent-review-receipt',
                    'not-human-or-external-approval', 'watermarked-version-bound-a4', 'bounded-a4-screen')]
        names += ['one-real-A4-PDF-404', 'one-real-A4-PDF-200', 'no-browser-exceptions']
        assert Counter(r['name'] for r in records) == Counter(names)
        assert all(r['pass'] for r in records) and len(browser['shots']) == 12
        cleanup = json.loads((private/'cleanup.json').read_bytes())
        assert len(cleanup) == 4 and all(r['absent'] for r in cleanup)
        transport = json.loads((private/'browser/transport-cleanup.json').read_bytes())
        chrome = json.loads((private/'browser/browser-process-cleanup.json').read_bytes())
        assert all(transport[k] for k in ('node_exited', 'bridge_exited', 'http_thread_exited'))
        assert chrome['exit_observed'] and not browser['exceptions']
        for name in ('browser.json', 'http-observations.json', 'transport-cleanup.json', 'browser-process-cleanup.json'):
            publish(name, (private/'browser'/name).read_bytes())
        for item in browser['shots']:
            name = item['file']
            assert re.fullmatch(r'(report|a4)-(1280|375|320)-(404|200)\.png', name)
            raw = (private/'browser'/name).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == item['sha256']
            publish(name, raw)
        for case in ('404', '200'):
            name = 'a4-' + case + '.pdf'
            raw = (private/'browser'/name).read_bytes()
            assertion = next(r for r in records if r['name'] == 'one-real-A4-PDF-' + case)
            assert assertion['metadata']['pages'] == 1 and assertion['metadata']['sha256'] == hashlib.sha256(raw).hexdigest()
            publish(name, raw)
        publish('source-manifest.json', (private/'source-manifest.json').read_bytes())
        publish('cleanup.json', (private/'cleanup.json').read_bytes())
        metadata.update(status='GENERATED_REVIEW_A4_PASS_TASK_SUBMISSION_BLOCKED',
            real_pg_restart=True, browser_assertions=len(records), screenshots=12,
            actual_a4_pdf_pages={'404': 1, '200': 1}, full_m2_exit=False,
            signing_key_outside_ssr=True, worker_uid=10002, ssr_uid=10003)
    finally:
        (public/'publication.json').write_text(json.dumps(metadata, indent=2))
    assert metadata['status'] == 'GENERATED_REVIEW_A4_PASS_TASK_SUBMISSION_BLOCKED'
    print(json.dumps({'status': metadata['status'], 'public': str(public)}))


if __name__ == '__main__':
    main()
