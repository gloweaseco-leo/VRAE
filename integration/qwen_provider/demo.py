"""Reproducible no-network same-source business candidate and failure fallback."""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from integration.qwen_provider.fixture import provider
from integration.s3_offline.fixture import NOW, context
from vrae.intelligence.s3 import Session


def blocked(*args, **kwargs):
    raise AssertionError('UNEXPECTED_NETWORK')


async def generate(root, c):
    no_model = await Session(c, clock=lambda: NOW).run('operation-no-model')
    p = provider(root / 'quota.sqlite', c)
    session = Session(c, clock=lambda: NOW)
    out = await session.run('operation-protocol', mode='REAL_QWEN', provider=p)
    assert out['status'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW' and out['real_model_calls'] == 0
    (root / 'candidate.json').write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    (root / 'candidate.md').write_text(session.markdown('operation-protocol'), encoding='utf-8')
    denied = provider(root / 'missing-key.sqlite', c, key=None)
    fallback = await Session(c, clock=lambda: NOW).run('operation-key', mode='REAL_QWEN', provider=denied)
    assert fallback['code'] == 'KEY_REQUIRED' and not fallback['claims']
    for name, data in (('no-model', no_model), ('fallback', fallback)):
        (root / (name + '.json')).write_text(json.dumps(data, indent=2), encoding='utf-8')
    receipt = {'status': 'REAL_PROVIDER_INTEGRATION_READY_LIVE_CALL_PENDING',
        'verification_realm': 'PROTOCOL_FAKE_NOT_REAL_API', 'real_model_calls': 0,
        'actual_model_version_confirmed': False, 'same_report_hash': out['deterministic_report_hash'],
        'source_pack_ref': c.pack.ref, 'guard_semantic_approval': False,
        'live_permission': 'NOT_GRANTED', 'independent_gold': 0,
        'candidate_status': out['status'], 'fallback_code': fallback['code'],
        'default_mode': no_model['mode']}
    (root / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    root = Path(parser.parse_args().output)
    root.mkdir(parents=True, exist_ok=False)
    with patch('socket.create_connection', blocked), patch('socket.getaddrinfo', blocked), \
            patch('asyncio.BaseEventLoop.sock_connect', blocked), \
            patch('asyncio.create_subprocess_exec', blocked):
        c = context()
        asyncio.run(generate(root, c))


if __name__ == '__main__':
    main()
