"""Replay independent source fixtures on accepted APIs, without RA3B imports."""
import base64
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.findings import FindingPackage  # noqa: E402


def audit():
    data = json.loads((ROOT/'tests/interpretation/fixtures/ra3b_codex1_inputs.json').read_text(encoding='utf-8'))
    rows = []
    for case, d in data.items():
        pack = EvidencePack.load(d['document'], {k: base64.b64decode(v, validate=True)
            for k, v in d['objects'].items()}, expected_ref=d['pins']['expected_pack_ref'])
        package = FindingPackage.load(d['package'], pack, **{k: v for k, v in d['pins'].items()
            if k not in ('expected_scope', 'expected_guard_version')})
        rules = {r['rule_id']: r for r in package.document['rule_execution']['executions']}
        trust = rules['TRUST-01']['observations'][0]
        if case in ('positive', 'source_injection', 'source_fake_certificate'):
            assert trust['observation']['result'] == 'PASS'
            assert any(c['fact_kind'] == 'DECLARED_NAME' for c in trust['citations'])
        else:
            assert trust['observation']['result'] in ('UNKNOWN', 'ACCESS_BLOCKED')
        if case in ('contact_404', 'contact_410'):
            row = rules['CTA-02']['observations'][0]
            assert row['observation']['result'] == 'FAIL_WITH_EVIDENCE'
            assert row['target_response']['http_status'] == int(case.rsplit('_', 1)[1])
        if case == 'positive':
            assert all(rules[k]['observations'][0]['observation']['result'] == 'PASS'
                       for k in ('SEO-01', 'INFO-01', 'CTA-02'))
        assert all(url.startswith('https://example.org/') for url in d['calls'])
        assert package.document['private'] and not package.document['shareable']
        assert package.document['approval_status'] == 'NOT_APPROVED'
        assert pack.document['run_id'] == 'run-codex1-ra3b-' + case.replace('_', '-')
        rows.append({'case': case, 'pins': d['pins'], 'trust': trust['observation']['result']})
    assert len(rows) == 14
    print(json.dumps({'source_fixture_cases': len(rows), 'all_replayed': True, 'cases': rows}, indent=2))


if __name__ == '__main__':
    audit()
