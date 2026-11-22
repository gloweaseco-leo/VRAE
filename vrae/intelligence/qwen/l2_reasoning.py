"""qwen-l2-buyer-reasoning-1.0.0. Fake providers only in this branch.

Input is redacted structured facts, checklist judgments, rule observations and
citation ids. Output claims stay REVIEW_REQUIRED. Missing evidence is dropped.
Failure, timeout and unknown cost become AI_UNAVAILABLE.
"""
import re

from jsonschema import Draft202012Validator

from .provider import L2_PROMPT, QwenError

PROMPT = L2_PROMPT
LIMIT = 8
KINDS = ('CROSS_PAGE_CONFLICT', 'MATERIAL_RELATION', 'BUYER_QUESTION', 'IMPROVEMENT_BASIS')
FORBIDDEN = re.compile(r'(价格|报价|工期|排名|流失|E2|E3|证书为真|工程适配已确认|price|ranking|churn)', re.I)
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'required': ['prompt_version', 'context_ref', 'claims'],
          'properties': {
              'prompt_version': {'const': PROMPT},
              'context_ref': {'type': 'string', 'minLength': 8, 'maxLength': 80},
              'claims': {'type': 'array', 'minItems': 0, 'maxItems': LIMIT, 'items': {
                  'type': 'object', 'additionalProperties': False,
                  'required': ['kind', 'fact', 'hypothesis', 'counterevidence', 'pending_confirmation', 'refs'],
                  'properties': {
                      'kind': {'enum': list(KINDS)},
                      'fact': {'type': 'string', 'maxLength': 400},
                      'hypothesis': {'type': 'string', 'maxLength': 400},
                      'counterevidence': {'type': 'string', 'maxLength': 400},
                      'pending_confirmation': {'type': 'string', 'maxLength': 400},
                      'refs': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                               'items': {'type': 'string', 'pattern': '^[a-z]+-[0-9a-f]{8,64}$'}}}}}}}


def system_text():
    return ('Return only structured buyer-reasoning candidates. Separate fact, hypothesis, '
            'counterevidence and pending confirmation. Drop claims without a supplied citation id. '
            'CROSS_PAGE_CONFLICT needs two snapshot ids. No price, rank, churn, certificate authenticity '
            'or engineering-fit conclusion. Zero claims is valid. Human review is required.')


def validate(payload, allowed):
    """Drop unbound claims. Truncate to K. Refuse forbidden conclusions."""
    try:
        Draft202012Validator(SCHEMA).validate(payload)
    except Exception as exc:
        raise QwenError('CANDIDATE_SCHEMA') from exc
    snapshots = allowed.get('snapshots') or {}
    refs = set(allowed.get('refs') or ())
    kept, dropped = [], 0
    for claim in payload['claims']:
        if any(FORBIDDEN.search(claim[key] or '') for key in ('fact', 'hypothesis', 'counterevidence', 'pending_confirmation')):
            raise QwenError('FORBIDDEN_CONCLUSION')
        if not set(claim['refs']) <= refs:
            dropped += 1
            continue
        if claim['kind'] == 'CROSS_PAGE_CONFLICT':
            found = {snapshots.get(ref) for ref in claim['refs']}
            found.discard(None)
            if len(found) < 2:
                dropped += 1
                continue
        kept.append({**claim, 'status': 'REVIEW_REQUIRED', 'native_fact_admission': 'NONE'})
    truncated = len(kept) > LIMIT
    return {'prompt_version': PROMPT, 'claims': kept[:LIMIT], 'dropped': dropped,
            'truncated': truncated, 'limit': LIMIT, 'real_model_calls': 0}


def degrade(reason):
    return {'status': 'AI_UNAVAILABLE', 'reason': reason, 'claims': [], 'diagnosis_complete': False,
            'prompt_version': PROMPT, 'real_model_calls': 0, 'verification_realm': 'PROTOCOL_FAKE_NOT_REAL_API'}


def attach(draft, validated, *, artifact_sha256, model_version):
    """Layer reviewed candidates onto an existing draft. Not a second report."""
    if validated.get('status') == 'AI_UNAVAILABLE':
        draft['ai'] = validated
        return draft
    draft['ai'] = {'status': 'AI_CANDIDATES_FOR_HUMAN_REVIEW', 'prompt_version': PROMPT,
                   'model_version': model_version, 'artifact_sha256': artifact_sha256,
                   'claims': validated['claims'], 'review_status': 'REVIEW_REQUIRED',
                   'real_qwen_on_customer_artifact': False, 'diagnosis_complete': False}
    return draft


async def complete_with_fake(provider, body, *, operation, scope, context_ref, now, timeout_ms):
    """Walk the existing provider complete() path. Caller supplies a protocol fake."""
    try:
        text, receipt = await provider.complete(body, operation=operation, scope=scope,
                                                context_ref=context_ref, now=now, timeout_ms=timeout_ms)
    except QwenError as exc:
        return degrade(str(exc)), None
    if receipt.get('cost_status') not in ('ESTIMATED', 'PROVIDER_REPORTED'):
        return degrade('COST_UNKNOWN'), receipt
    return text, receipt
