"""Real discovery/S3/Guard/PG with explicit protocol fake. Zero native API calls."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from contracts.l2_launch.contract import canonical
from infra.linux_service import ai_loop, qwen_runtime
from infra.qwen_provider.transport import NativeTransport
from vrae.intelligence.qwen import Quota
from vrae.intelligence.qwen.provider import PROMPT
from vrae.intelligence.qwen.testing import FakeTransport


def main():
    d, _ = qwen_runtime.load()
    assert d['source_class'] == 'CONTROLLED_NON_CUSTOMER' and d['approval_ref'].startswith('TEST_ONLY_')
    quota = Path('/tmp/EXPLICIT-FAKE-ONLY.sqlite')
    Quota(quota, create=True)
    qwen_runtime.LEDGER = quota
    original = qwen_runtime.provider_for
    assignments = {}
    cases = ('permission', 'key', 'ok', 'schema', 'timeout', 'budget')
    def factory(binding, job, held, now=None):
        identity = binding['tenant_id'] + '/' + str(job)
        if identity not in assignments:
            assignments[identity] = cases[len(assignments) % len(cases)]
        case = assignments[identity]
        provider = original(binding, job, held, now)
        fake = FakeTransport({})
        provider = replace(provider, _transport=fake)
        if case == 'permission':
            provider = replace(provider, permission=None)
        elif case == 'key':
            provider = replace(provider, key=None)
        elif case == 'timeout':
            fake.timeout = True
        elif case == 'budget':
            provider = replace(provider, permission=replace(provider.permission, cap_micros=1))
        fake._runtime_case = case
        return provider
    qwen_runtime.provider_for = factory
    build = ai_loop.adapter
    def adapter(*args, **kwargs):
        result = build(*args, **kwargs)
        if result is not None:
            result._timeout = 10
        return result
    ai_loop.adapter = adapter
    post = FakeTransport.post
    async def reply(self, config, key, body, timeout_ms):
        data = json.loads(body['messages'][1]['content'])
        refs = data['references']
        anchor = next(r for r in refs if r['type'] == 'GUARD_LITERAL')
        conflict = [r for r in refs if r['type'] == 'CONFIGURATION_CONFLICT' and r['task'] == anchor['task']]
        bound = list(dict.fromkeys([anchor['ref']] + [r['ref'] for r in conflict]))
        counter = sorted({v for r in conflict for v in r['counter_refs']} - set(bound))
        candidate = {'prompt_version': PROMPT, 'context_ref': data['context_ref'], 'claims': [{
            'task': anchor['task'], 'refs': bound, 'counter_refs': counter,
            'explanation': 'A buyer may need the saved product information grouped by variant before comparing options.',
            'uncertainties': ['UNKNOWN observations and withheld text do not establish completeness or suitability.'],
            'questions': ['Which variant and revision should the buyer compare?'],
            'rebuild': ['Group the recorded variant details beside their traceable source references.']}]}
        self.response = {'object': 'chat.completion', 'model': 'qwen4-max',
            'id': 'FAKE-runtime-' + hashlib.sha256(data['context_ref'].encode()).hexdigest(),
            'usage': {'prompt_tokens': 137, 'completion_tokens': 83, 'total_tokens': 220},
            'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
                'content': '{}' if self._runtime_case == 'schema' else json.dumps(candidate)}}]}
        return await post(self, config, key, body, timeout_ms)
    FakeTransport.post = reply
    async def forbidden(*_):
        raise AssertionError('NATIVE_NETWORK_FORBIDDEN_IN_PROTOCOL_FAKE')
    NativeTransport.post = forbidden
    process = ai_loop.process_job
    def checked(binding, job, *args, **kwargs):
        result = process(binding, job, *args, **kwargs)
        print(canonical({'test_realm': 'PROTOCOL_FAKE_NOT_REAL_API',
            'case': assignments.get(binding['tenant_id'] + '/' + job),
            'state': result['state'], 'reason': result.get('reason'),
            'pg_receipt_status': result['pg_receipt_status'], 'native_model_calls': 0}).decode(), flush=True)
        return result
    ai_loop.process_job = checked
    ai_loop.main()


if __name__ == '__main__':
    main()
