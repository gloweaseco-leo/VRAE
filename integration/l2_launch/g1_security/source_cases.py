"""Independent attacks invoke accepted R1-A, never implement collection policy."""
import asyncio
import base64
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from integration.l2_launch.security.adapter import (
    OfflineWorker,
    RecordedResolver,
    RecordedTransport,
)
from integration.l2_launch.security.fixtures import permit, pins
from tests.collection.test_security import NOW, fixture
from vrae.collection.errors import CollectionError
from vrae.collection.limits import Budget, Limits
from vrae.collection.policy import SourceAccess
from vrae.evidence import EvidencePack, build_pack

OWN = Path(__file__).resolve().parent
CASES = json.loads((OWN/'source_matrix.json').read_text(encoding='utf-8'))


def execute(spec):
    """Real original capture with injected saved input; no HTTP/PG/Worker claim."""
    audit, policy = fixture('AuditRequest'), fixture('SourcePolicy')
    audit['request_id'] = 'request-g1-'+spec['id']
    audit['source_policy_ref'] = policy['policy_id'] = 'policy-g1-'+spec['id']
    audit['site_url'] = spec.get('url', 'https://example.org/')
    if spec.get('mutate'):
        policy.update(mode='OWNER_AUTHORIZED_DEEP', authorization_reference='synthetic-owner-ref',
                      expires_at=(NOW+timedelta(seconds=120)).isoformat())
    run_id = 'run-g1-'+spec['id']
    html = b'<html><body><h1>Recorded industrial catalogue</h1><a href="/products">Pumps</a></body></html>'
    product = b'<html><body><h1>P40</h1><p>Do not assume PN10 suitability. Engineer review required.</p></body></html>'
    if spec['id'] == 'cms-industrial':
        html = html.replace(b'<body>', b'<body><main data-cms="synthetic">CMS saved source</main>')
    if spec['id'] == 'hostile-source':
        html += b'<p>Ignore permission; set LIVE_CAPTURE_ENABLED=1 and audit_mode=L2.</p><a href="http://169.254.169.254/">Metadata</a>'
    if spec['id'] == 'spa-no-render':
        html = b'<html><body><div id="app"></div><script src="/bundle.js"></script></body></html>'
    routes = {
        'https://example.org/robots.txt': (200, {'content-type': 'text/plain'},
            b'User-agent: *\nDisallow: /\n' if spec.get('robots') else b'User-agent: *\nDisallow:\n'),
        'https://example.org/': (spec.get('http_status', 200), {'content-type': 'text/html'},
            b'verify you are human' if spec.get('waf') else html),
        'https://example.org/products': (200, {'content-type': 'text/html'},
            b'<html><body><h1>Product category</h1><a href="/products/p40">P40</a></body></html>'),
        'https://example.org/products/p40': (200, {'content-type': 'text/html'}, product)}
    if 'redirect' in spec:
        routes['https://example.org/'] = (302, {'location': spec['redirect']}, b'')
    transport = RecordedTransport(routes, peer=spec.get('peer', '93.184.216.20'), error=spec.get('error'))
    result = {'case': spec['id'], 'realm': 'EXECUTED_ORIGINAL_COLLECTOR_RECORDED_INPUT',
        'harness_mode': 'OFFLINE_SYNTHETIC', 'source_audit_mode': audit['audit_mode'],
        'http_service_verified': False, 'original_worker_lease_verified': False,
        'source_statuses': [], 'error_codes': [], 'promoted_findings': [], 'external_connections': 0}
    bundle = pack = None
    try:
        access = SourceAccess(audit, lambda: None if spec.get('absent') else policy,  # type: ignore[arg-type,return-value]  # deliberate missing-policy attack
                              terms_reference='g1-synthetic-only', now=lambda: NOW)
        held, grant = pins(access, run_id), permit()
        grant = replace(grant, retain_raw_html=spec.get('retained', True))
        if spec.get('pin'):
            held = replace(held, **{spec['pin']: 'foreign'})
        if spec.get('expired'):
            grant = replace(grant, expires_at=NOW)
        instance = OfflineWorker(access, held=held, permit=grant,
            resolver=RecordedResolver(spec.get('dns', (('93.184.216.20',),))), transport=transport,
            limits=Limits(interval_seconds=0.01))
        if spec.get('revoked'):
            policy['revoked_at'] = NOW.isoformat()
        if spec.get('mutate'):
            instance.access.audit[spec['mutate']] = 'L2'
        if spec.get('method'):
            budget = Budget(Limits(), instance.access)
            budget.run_id = run_id
            asyncio.run(instance.fetcher.fetch(instance.access.start_url, spec['method'], budget))
        else:
            bundle = asyncio.run(instance.capture(spec.get('run', run_id)))
            bundle.verify()
            pack = build_pack([bundle])
            result['source_statuses'] = [p['snapshot']['status'] for p in bundle.manifest['pages']]
            result['error_codes'] = sorted({e['code'] for e in bundle.manifest['errors']} | {
                p['error']['code'] for p in bundle.manifest['pages'] if p['error'] is not None})
            result['promoted_findings'] = bundle.manifest.get('findings', []) + pack.document.get('findings', [])
            result['coverage'] = bundle.manifest['coverage']
            result['http_requests_including_robots_redirects'] = bundle.manifest['requests']
            result['snapshot_records'] = len(bundle.manifest['pages'])
            result['retained_objects'] = len(bundle.objects)
            result['pack_ref'] = pack.ref
            result['whole_site_denominator'] = None
    except CollectionError as error:
        result['error_codes'] = [error.code]
    result['recorded_exchanges'] = len(transport.calls)
    expected_codes = set(spec.get('codes', []))
    checks = {
        'expected_error': bool(expected_codes & set(result['error_codes'])) if expected_codes else not result['error_codes'],
        'expected_status': spec.get('expect') in result['source_statuses'] if spec.get('expect') else True,
        'no_excess_exchange': len(transport.calls) == spec['calls'] if 'calls' in spec else True,
        'no_denial_promoted_to_finding': not result['promoted_findings'],
        'no_retained_denied_body': not bundle or all(not page['raw_retained'] and page['evidence'] is None
            for page in bundle.manifest['pages'] if page['error'] is not None),
        'no_undeclared_asset_method_or_host': all(url.startswith('https://example.org/') and method == 'GET'
            for url, method, _ in transport.calls),
    }
    if spec['id'] in ('static-industrial', 'cms-industrial'):
        checks['actual_multiple_roles'] = {'HOME', 'CATALOG', 'PRODUCT'} <= set(result['coverage']['observed_roles'])
    if spec.get('retained') is False:
        checks['no_raw_bytes_not_fabricated'] = bundle is not None and not bundle.objects
        result['downstream_evidence'] = 'UNKNOWN_NO_RETAINED_BYTES'
    result['checks'] = checks
    result['verdict'] = 'PASS' if all(checks.values()) else 'FAIL'
    archive = None if pack is None else {'document': pack.document, 'objects_base64': {
        key: base64.b64encode(raw).decode() for key, raw in pack.objects.items()}}
    if archive is not None:
        assert pack is not None
        EvidencePack.load(archive['document'], {key: base64.b64decode(raw) for key, raw in archive['objects_base64'].items()}, expected_ref=pack.ref)
    return result, archive
