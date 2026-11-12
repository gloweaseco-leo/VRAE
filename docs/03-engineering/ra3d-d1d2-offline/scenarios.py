"""Executable D2 evidence: synthetic paths, deterministic targets, actual refusals."""
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tests.reviewing.synthetic import NOW, actor, command, inputs, ledger, submit
from vrae.reviewing import ReviewError, ReviewCommandProposal, build_target, prepare_production_review
from vrae.reviewing.canonical import canonical, parse, sha


def main():
    destination = Path(sys.argv[1])
    paths = []
    for case, action in [('404', 'APPROVE_CANDIDATE'), ('404', 'REQUEST_CHANGES'),
                         ('404', 'REJECT'), ('200', None)]:
        i = inputs(case)
        before = sha(i.document), sha(i.html), sha(i.source)
        receipt = submit(ledger(i), i.target, command(i.target, action)).receipt.document
        assert before == (sha(i.document), sha(i.html), sha(i.source))
        paths.append({'case': case, 'target': i.target.document, 'target_digest': i.target.target_digest,
                      'receipt': receipt, 'original_byte_hashes': before})
    i = inputs()
    c = command(i.target).document
    c['dispositions'].pop()
    actions = {
        'html': lambda: build_target(i.document, i.html + b'x', i.source, trust=i.trust),
        'source': lambda: build_target(i.document, i.html, i.source + b' ', trust=i.trust),
        'object': lambda: build_target(i.document, i.html, i.source,
                                      trust=replace(i.trust, artifact_ref='https://invalid.invalid')),
        'clock': lambda: submit(ledger(i), i.target, now=None),
        'cross_tenant': lambda: submit(ledger(i), i.target, who=actor(i.target, tenant_id='tenant-other')),
        'missing_claim': lambda: submit(ledger(i), i.target, ReviewCommandProposal(canonical(c))),
        'real_auth': lambda: prepare_production_review({'role': 'OWNER', 'verified': True}),
        'duplicate_json': lambda: parse(b'{"x":1,"x":2}'),
    }
    refusals = {}
    for name, action in actions.items():
        try:
            action()
        except ReviewError as exc:
            refusals[name] = exc.code
        else:
            raise AssertionError('Expected refusal: ' + name)
    record = {'python': sys.version, 'synthetic_time': NOW.isoformat(), 'paths': paths,
              'refusals': refusals, 'human_decisions': 0, 'native_approvals': 0, 'grants': 0,
              'models': 0, 'customer_accesses': 0, 'durability': 'NOT_IMPLEMENTED',
              'production_auth': 'BLOCKED_ALWAYS_DENY', 'human_gold': '0/26'}
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'targets': {p['case']: p['target_digest'] for p in paths},
                      'refusals': refusals, 'output': str(destination)}, sort_keys=True))


if __name__ == '__main__':
    main()
