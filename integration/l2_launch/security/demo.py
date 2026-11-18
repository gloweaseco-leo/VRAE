"""Saved synthetic site families and machine-readable refusal packets."""
import asyncio
import base64
import json
import re
import sys
from pathlib import Path

from tests.collection.test_security import NOW, fixture
from vrae.collection.errors import CollectionError
from vrae.collection.policy import SourceAccess
from vrae.evidence import EvidencePack, build_pack

from .adapter import STATUS, RecordedResolver, RecordedTransport, capture_live
from .fixtures import routes, worker


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'local-demo'
    if not re.fullmatch('[a-z0-9-]{3,40}', label):
        raise ValueError('OWNED_LABEL_REQUIRED')
    out = Path(__file__).resolve().parent / '.runtime' / label
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for scenario in ('static', 'cms', 'spa', 'multi-sku', 'multilingual', 'query-percent',
                     'dynamic-assets', 'redirect', '403', '429', 'robots', 'waf', 'hostile-source'):
        candidate = worker(scenario)
        bundle = asyncio.run(candidate.capture(candidate.access.held.run_id))
        pack = build_pack([bundle])
        data = {'document': pack.document, 'objects_base64': {
            ref: base64.b64encode(raw).decode() for ref, raw in pack.objects.items()}}
        EvidencePack.load(data['document'], {k: base64.b64decode(v) for k, v in data['objects_base64'].items()}, expected_ref=pack.ref)
        (out/(scenario+'-pack.json')).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        rows.append({'scenario': scenario, 'source_mode': 'OFFLINE_RECORDED_L1_NOT_REAL_L2',
            'pack_ref': pack.ref, 'page_statuses': [p['snapshot']['status'] for p in bundle.manifest['pages']],
            'selected_page_attempts': len(bundle.manifest['pages']), 'whole_site_denominator': None,
            'target_connections': 0, 'findings_created': 0, 'rendered_js_assets': 'UNKNOWN',
            'semantic_sufficiency': 'UNKNOWN', 'source_instructions_executed': False,
            'unsupported_link_scope': ['QUERY_URLS', 'PERCENT_PATHS'] if scenario == 'query-percent' else []})
    denied = []
    for name, operation in [('LIVE_CAPTURE_DISABLED', capture_live),
                            ('WRONG_RUN', lambda: asyncio.run(worker().capture('foreign-run'))),
                            ('POLICY_REQUIRED', lambda: SourceAccess(fixture('AuditRequest'), lambda: None,  # type: ignore[arg-type, return-value]  # refusal sample
                                terms_reference='terms-test', now=lambda: NOW)),
                            ('VF_SELF_ASSERTION', lambda: capture_live(owner_checkbox=True))]:
        try:
            operation()
            raise AssertionError('REFUSAL_EXPECTED')
        except (PermissionError, CollectionError) as exc:
            denied.append({'case': name, 'denied': True, 'code': str(exc), 'retry': False, 'finding': None})
    for name, candidate in [
        ('DNS_REBINDING', worker(resolver=RecordedResolver((('93.184.216.20',), ('169.254.169.254',))))),
        ('MIXED_A_AAAA', worker(resolver=RecordedResolver((('93.184.216.20', '::1'),)))),
        ('FORGED_PEER', worker(transport=RecordedTransport(routes(), peer='127.0.0.1'))),
        ('EXTERNAL_REDIRECT', worker(transport=RecordedTransport({'https://example.org/robots.txt':
            (302, {'location': 'https://other.test/'}, b'')})))]:
        bundle = asyncio.run(candidate.capture(candidate.access.held.run_id))
        assert bundle.manifest['errors'] and not bundle.objects
        denied.append({'case': name, 'denied': True, 'errors': bundle.manifest['errors'],
            'page_statuses': [p['snapshot']['status'] for p in bundle.manifest['pages']],
            'target_connections': 0, 'retry': False, 'finding': None})
    result = {'status': STATUS, 'live_enabled': False, 'real_target_connections': 0,
              'infra_cost': 'UNKNOWN', 'quality': 'NOT_EVALUABLE', 'independent_gold': 0,
              'c2_contract': 'UNFROZEN_NOT_ASSUMED', 'cases': rows, 'denial_packets': denied}
    (out/'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'status': STATUS, 'scenarios': len(rows), 'denials': len(denied)}))


if __name__ == '__main__':
    main()
