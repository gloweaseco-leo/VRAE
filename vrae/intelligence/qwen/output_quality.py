"""Narrow output refusals, not semantic approval or a new diagnostic rule."""
import re

from .provider import fail

VERSION = 'qwen-buyer-output-1.0.0'
SCOPED_VERSION = 'qwen-buyer-output-1.1.0'
CONTEXT_VERSION = 'qwen-buyer-output-1.2.0'
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


COMMERCIAL = re.compile(
    r'现货|库存|标准(?:粒度|规格|品)|交期|起订|产能承诺|营销话术|'
    r'\b(?:in[ -]?stock|inventory|stock(?:ed)?|standard (?:grits?|specifications?)|'
    r'lead[ -]?times?|MOQ|minimum order|capacity promise|marketing (?:claim|hype))\b', re.I)


def check_commercial(claim, entries):
    """Neutral questions stay questions; listed choices do not prove stock or capacity."""
    # Only safe source values actually cited by the claim can support its prose.
    from .source_values import value
    source = []
    for ref in claim['refs'] + claim['counter_refs']:
        entry = entries[ref]
        if entry['type'] == 'GUARD_LITERAL':
            text = value(entry['fact'])
            if text:
                source.append(text)
    supported = {m[0].casefold() for text in source for m in COMMERCIAL.finditer(text)}
    prose = [claim['explanation'], *claim['rebuild'], *claim['uncertainties'], claim['verification']]
    if any(m[0].casefold() not in supported for text in prose for m in COMMERCIAL.finditer(text)):
        fail('UNSUPPORTED_COMMERCIAL_INFERENCE')
