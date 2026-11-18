"""Synthetic protocol data with deliberately fictitious fees and no real credentials."""
from datetime import timedelta
import json

from integration.s3_offline.fixture import NOW, context, references
from vrae.intelligence.qwen import Config, Permission, Price, QwenProvider, Quota
from vrae.intelligence.qwen.provider import MODEL, PROMPT
from vrae.intelligence.qwen.testing import FakeTransport


def candidate(c):
    literal, _ = references(c)
    return {'prompt_version': PROMPT, 'context_ref': c.context_ref, 'claims': [{
        'task': 'UNDERSTAND', 'refs': [literal], 'counter_refs': [],
        'explanation': 'A buyer may need to compare the saved technical observation with the current '
                       'revision before narrowing the product shortlist.',
        'uncertainties': ['The bounded capture does not establish current engineering suitability.'],
        'questions': ['Which current revision and operating conditions should the buyer compare?'],
        'rebuild': ['Place revision, operating conditions and a traceable source reference together '
                    'in the technical information section; ask an engineer to review the content.']}]}


def response(c):
    return {'id': 'fake-request-never-a-vendor-response', 'object': 'chat.completion',
        'model': MODEL, 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps(candidate(c))}}],
        'usage': {'prompt_tokens': 137, 'completion_tokens': 83, 'total_tokens': 220}}


def provider(path, c=None, *, fake=None, **overrides):
    c = c or context()
    values = dict(config=Config('synthetic-workspace'), quota=Quota(path, create=True),
        permission=Permission('TEST_ONLY_NOT_OWNER_LIVE_PERMISSION', NOW + timedelta(minutes=9), 3, 1000000),
        price=Price('TEST_ONLY_FICTITIOUS_PRICE', 'https://help.aliyun.com/zh/model-studio/models',
                    1000000, 2000000, NOW + timedelta(minutes=9)),
        key='synthetic-key-no-real-secret-0000', _transport=fake or FakeTransport(response(c)))
    values.update(overrides)
    return QwenProvider(**values)
