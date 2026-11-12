"""Replay independently pinned accepted-main fixtures, not reporting PASS."""
import ast
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
TEST = ROOT/'tests/reporting/test_ra3c_independent_acceptance.py'


def main():
    spec = importlib.util.spec_from_file_location('codex1_independent_input_audit',TEST)
    qa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qa)
    assert len(qa.CASES) == 64 and len(qa.INPUT['scenarios']) == 14
    tree = ast.parse(TEST.read_text(encoding='utf-8'))
    assert not any(isinstance(n,ast.Attribute) and n.attr in ('skip','skipif','xfail') for n in ast.walk(tree))
    contexts = []
    for scenario,config in qa.INPUT['scenarios'].items():
        for profile in config['pins']:
            ctx = qa.prepare_context(scenario,profile)
            assert ctx['pins'] == config['pins'][profile]
            assert ctx['pack'].document['tenant_id'] == 'tenant-ra3c-qa'
            assert all(url.startswith('https://example.org/') for url in ctx['calls'])
            claims = ctx['guard'].document['claims']
            if profile != 'truthful':
                fabricated = set(qa.INPUT['profiles'][profile])
                assert not any(qa.pointer(ctx['interpretation'],c['pointer']) in fabricated and c['status'] == 'SOURCE_FACT_BINDING_VERIFIED' for c in claims)
            contexts.append(dict(scenario=scenario,profile=profile,pins=ctx['pins'],
                claim_statuses=dict(Counter(c['status'] for c in claims)),
                native_failures=len(ctx['verified_findings']),synthetic_requests=len(ctx['calls'])))
    assert len(contexts) == 18
    # These are parser/extraction/gate self-checks, not a reporting stub.
    class Mapping:
        origins = {'scope':{'kind':'object','members':{'tenant_id':{'kind':'json','pointer':'/tenant'}}}}
    assert qa.field(Mapping,{'document':{'tenant':'local'}},'scope') == {'tenant_id':'local'}
    assert qa.HtmlAudit(b'<p id="q">a &amp; b</p>').nodes[0]['text'] == ['a & b']
    import socket
    try:
        with qa.no_external_effects():
            try:
                socket.getaddrinfo('never-resolve.invalid',443)
            except AssertionError:
                pass
    except AssertionError as error:
        assert str(error) == 'QA_FORBIDDEN_NETWORK_OR_PROCESS_ATTEMPT'
    else:
        raise AssertionError('QA gate swallowed an attempted external effect')
    print(json.dumps(dict(kind='ACCEPTED_SOURCE_INPUT_REPLAY_NOT_REPORTING_PASS',
        scenarios=14,contexts=contexts,planned_cases=64,real_network_calls=0,
        source_sha256=hashlib.sha256(TEST.read_bytes()).hexdigest()),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
