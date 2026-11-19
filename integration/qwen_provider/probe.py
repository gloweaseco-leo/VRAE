"""Fixed pure-synthetic first-probe body, no credentials, transport or live CLI.

Owner requires the first future authorized call to prove model/usage before any
second diagnostic call. This builder cannot authorize, dispatch or retry a call.
"""
from vrae.intelligence.qwen.provider import MODEL


def minimal_probe_body():
    return {'model': MODEL, 'messages': [
        {'role': 'system', 'content': 'Return only JSON containing ok=true. This is a pure synthetic protocol check.'},
        {'role': 'user', 'content': 'Confirm this synthetic check. No source or customer data.'}],
        'enable_thinking': False, 'stream': False, 'max_completion_tokens': 64,
        'response_format': {'type': 'json_schema', 'json_schema': {
            'name': 'qwen4_minimal_protocol_probe', 'strict': True,
            'schema': {'type': 'object', 'properties': {'ok': {'type': 'boolean', 'const': True}},
                       'required': ['ok'], 'additionalProperties': False}}}}
