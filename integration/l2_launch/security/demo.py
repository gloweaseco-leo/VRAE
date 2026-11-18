"""Saved synthetic site families and machine-readable refusal packets."""
import asyncio
import base64
import json
import re
import sys
from pathlib import Path

from vrae.collection.errors import CollectionError
from vrae.evidence import EvidencePack, build_pack

from .adapter import STATUS, capture_live
from .fixtures import worker


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'local-demo'
    if not re.fullmatch('[a-z0-9-]{3,40}', label):
        raise ValueError('OWNED_LABEL_REQUIRED')
    out = Path(__file__).resolve().parent / '.runtime' / label
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for scenario in ('static', 'cms', 'spa', 'multi-sku', 'multilingual', 'query-percent',
                     'dynamic-assets', 'redirect', '403', '429', 'robots', 'waf'):
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
            'semantic_sufficiency': 'UNKNOWN',
            'unsupported_link_scope': ['QUERY_URLS', 'PERCENT_PATHS'] if scenario == 'query-percent' else []})
    denied = []
    for name, operation in [('LIVE_CAPTURE_DISABLED', capture_live),
                            ('WRONG_RUN', lambda: asyncio.run(worker().capture('foreign-run')))]:
        try:
            operation()
            raise AssertionError('REFUSAL_EXPECTED')
        except (PermissionError, CollectionError) as exc:
            denied.append({'case': name, 'denied': True, 'code': str(exc), 'retry': False, 'finding': None})
    result = {'status': STATUS, 'live_enabled': False, 'real_target_connections': 0,
              'infra_cost': 'UNKNOWN', 'quality': 'NOT_EVALUABLE', 'independent_gold': 0,
              'c2_contract': 'UNFROZEN_NOT_ASSUMED', 'cases': rows, 'denial_packets': denied}
    (out/'summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'status': STATUS, 'scenarios': len(rows), 'denials': len(denied)}))


if __name__ == '__main__':
    main()
