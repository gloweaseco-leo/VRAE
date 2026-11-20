"""Narrow output refusals, not semantic approval or a new diagnostic rule."""
import re

from .provider import fail

VERSION = 'qwen-buyer-output-1.0.0'
SCOPED_VERSION = 'qwen-buyer-output-1.1.0'
INTERNAL_LIMIT = re.compile(
    r'WITHHELD_BY_DEFAULT|rule_result|pinned\s+(?:description\s+)?anchor|'
    r'source\s+text\s+(?:(?:is|was)\s+)?withheld|锚点编号|源文本.{0,8}(?:隐藏|屏蔽)', re.I)
UNSUPPORTED_ABSENCE = re.compile(
    r'\b(?:no|missing|lacks?)\s+(?:usable\s+|any\s+|product\s+)?(?:specifications?|specs|parameters)\b|'
    r'(?:网站|页面|产品).{0,8}(?:缺少|没有|缺失).{0,6}(?:参数|规格)', re.I)


def check(claim):
    if any(INTERNAL_LIMIT.search(text) for text in [claim['explanation'], *claim['rebuild']]):
        fail('MODEL_INTERNAL_LIMIT_NOT_BUYER_FINDING')
    # INFO-01 has no implemented absence/FAIL proof. A model must not supply it.
    if claim['task'] == 'UNDERSTAND' and UNSUPPORTED_ABSENCE.search(claim['explanation']):
        fail('UNSUPPORTED_SPECIFICATION_ABSENCE')
    if claim['verification'].strip() in {x.strip() for x in claim['rebuild']}:
        fail('DISTINCT_VERIFICATION_REQUIRED')


def check_product_scopes(claim, entries):
    """Reject cross-region product comparisons; this is not semantic approval."""
    scopes = set()
    for ref in claim['refs'] + claim['counter_refs']:
        entry = entries[ref]
        if entry['type'] != 'GUARD_LITERAL' or entry['fact']['rule_id'] != 'INFO-01':
            continue
        citation = entry['fact']['source']['citation']
        scope = citation.get('product_scope_ref')
        if type(scope) is not str or not re.fullmatch('ps-[0-9a-f]{64}', scope):
            fail('UNSCOPED_PRODUCT_REFERENCE')
        scopes.add(scope)
    if len(scopes) > 1:
        fail('PRODUCT_SCOPE_MISMATCH')
