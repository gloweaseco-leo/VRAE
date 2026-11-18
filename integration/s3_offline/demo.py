"""Produce paired synthetic NO_MODEL/fixture fragments, never a native report."""
import argparse
import asyncio
import json
from pathlib import Path
import time

from vrae.intelligence.s3 import Session
from .fixture import NOW, book, claim, context, provider, references


def pair(c, name, claims, *, behavior='ok'):
    before = c.source.read().document
    plain = Session(c, clock=lambda: NOW)
    model = Session(c, ledger=book(c), clock=lambda: NOW)
    async def perform():
        no_model = await plain.run('baseline-' + name)
        assisted = await model.run('fixture-' + name, mode='FIXTURE',
            provider=provider(c, claims, behavior=behavior), timeout_ms=20)
        return no_model, assisted
    no_model, assisted = asyncio.run(perform())
    assert before == c.source.read().document
    assert no_model['deterministic_report_hash'] == assisted['deterministic_report_hash']
    assert assisted['usage']['amount'] is None and assisted['real_model_calls'] == 0
    assert not assisted['external_actions'] and not assisted['shareable']
    return {'scenario': name, 'context_ref': c.context_ref,
        'component_scope': 'OFFLINE_SYNTHETIC_NOT_ACTUAL_APP202_OR_WORKER',
        'task': {'tenant_id': c.completion.task.tenant_id, 'request_id': c.completion.task.request_id,
            'run_id': c.completion.task.run_id, 'job_id': c.completion.task.job_id,
            'pack_ref': c.pack.ref, 'report_content_hash': c.completion.report_content_hash},
        'worker_lease_expires_at': c.completion.lease_expires_at.isoformat(),
        'model_task_started_at_synthetic_clock': NOW.isoformat(),
        'no_model': no_model, 'fixture': assisted, 'original_report_unchanged': True,
        'before_markdown': plain.markdown('baseline-' + name),
        'after_markdown': model.markdown('fixture-' + name)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    good = context()
    literal, cards = references(good)
    technical = pair(good, 'technical-cross-page', [claim('OBJECTIVE_SOURCE_FACT', [literal]),
        claim('BUYER_HYPOTHESIS', cards), claim('MISSING_INFORMATION', [cards[0]]),
        claim('IMPROVEMENT_OPPORTUNITY', [cards[1]], task='TRUST')])
    cases = [technical]
    for label, kwargs in [('unknown', {'unknown': True}), ('not-applicable', {'not_applicable': True})]:
        c = context(**kwargs)
        ref = next(k for k, e in c.catalog['entries'].items() if e['type'] == 'S2_REVIEW_CARD'
                   and e['card']['result'] != 'PASS')
        task = c.catalog['entries'][ref]['card']['buyer_task']
        cases.append(pair(c, label, [claim('MISSING_INFORMATION', [ref], task=task)]))
    for label, bad in [('forged-citation', {'refs': ['cf-' + '0' * 64]}),
                       ('fabricated-certificate', {'text': 'This certificate is authentic.'}),
                       ('fabricated-loss', {'text': 'The supplier lost $99999.'}),
                       ('malicious-model', {'tool_calls': ['exfiltrate', 'approve report']})]:
        bad_claim = claim('OBJECTIVE_SOURCE_FACT', [literal])
        bad_claim.update(bad)
        item = pair(good, label, [bad_claim])
        assert item['fixture']['status'] == 'REFUSED'
        cases.append(item)
    hostile = context(injection=True)
    cases.append(pair(hostile, 'malicious-website',
                      [claim('OBJECTIVE_SOURCE_FACT', [references(hostile)[0]])]))
    for behavior in ('timeout', 'cancel', 'error'):
        item = pair(good, 'fallback-' + behavior,
                    [claim('OBJECTIVE_SOURCE_FACT', [literal])], behavior=behavior)
        assert item['fixture']['status'] == 'REFUSED'
        cases.append(item)
    args.output.mkdir(parents=True, exist_ok=True)
    for item in cases:
        for field in ('before_markdown', 'after_markdown'):
            args.output.joinpath(item['scenario'] + '-' + field + '.md').write_text(item.pop(field), encoding='utf-8')
    result = {'status': 'S3_OFFLINE_AI_ENGINEERING_PASS_PROVIDER_PENDING', 'version': 's3-offline-1.0.0',
        'scope': 'REPRODUCIBLE_SYNTHETIC_COMPONENT_ONLY_NOT_S3_REAL_PROVIDER_OR_SYSTEM_ACCEPTANCE',
        'wall_seconds': time.monotonic() - started, 'cases': cases, 'real_model_calls': 0,
        'real_provider_cost': {'status': 'UNKNOWN', 'amount': None},
        'quality': {'status': 'NOT_EVALUABLE', 'independent_gold': 0, 'improvement': None}}
    args.output.joinpath('evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'cases': len(cases), 'real_model_calls': 0,
                      'quality': 'NOT_EVALUABLE', 'wall_seconds': result['wall_seconds']}))


if __name__ == '__main__':
    main()
