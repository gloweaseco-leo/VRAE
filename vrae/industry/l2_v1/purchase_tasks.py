"""Bounded procurement questions over source-local fields, never engineering fit."""
TASKS = {
    'APPLICATION_SCREEN': (('应用初筛', 'Application screening'), {'usage'}),
    'SPECIFICATION_COMPARISON': (('规格比对', 'Specification comparison'),
        {'dimensions', 'model', 'bore', 'flow', 'head', 'power', 'voltage', 'frequency', 'pressure', 'temperature'}),
    'OPTION_SELECTION': (('选项关系澄清', 'Clarify option relationships'),
        {'bond', 'grit', 'abrasive', 'medium', 'material', 'connection'}),
}
PLACEHOLDERS = {'n/a', 'na', 'unknown', 'not specified', 'tbd', '-', '—', 'on request'}


def informative(value):
    return ' '.join(value.split()).casefold() not in PLACEHOLDERS
# These are bounded clarification actions, not promises to publish inferred
# parameter meanings or Cartesian products of independently listed options.
ACTIONS = {
    'APPLICATION_SCREEN': (
        '如需按所列用途初筛，先向供方确认适用条件，并核对现有应用资料；未确认前不发布适配结论。',
        'For screening by the stated use, ask the supplier to confirm conditions and check existing application documents before publishing fit claims.'),
    'SPECIFICATION_COMPARISON': (
        '先核对现有图纸和规格说明；仍无法解释的编码请供方澄清，保留原文及已标注单位，不自行拆解为工程参数。',
        'Check existing drawings and specifications first; ask the supplier about unresolved codes, preserving source text and stated units without inventing engineering parameters.'),
    'OPTION_SELECTION': (
        '先核对现有选型资料；如仍无法建立所列选项的对应关系，请供方确认，不由并列选项生成可用组合。',
        'Check existing selection documents first; ask the supplier about unresolved option relationships rather than generating valid combinations from separate lists.'),
}
QUESTIONS = {
    'APPLICATION_SCREEN': ('所列用途对应哪些已确认条件，现有哪份资料可以核对？',
        'Which confirmed conditions apply to the stated use, and which existing document supports them?'),
    'SPECIFICATION_COMPARISON': ('哪些现有图纸或说明可解释原规格编码及其对应关系？',
        'Which existing drawing or specification explains the original code and its relationships?'),
    'OPTION_SELECTION': ('哪些选项关系已获供方确认，依据是哪份选型资料？',
        'Which option relationships has the supplier confirmed, and which selection document supports them?'),
}
VERIFICATIONS = {
    key: ('对照同一产品区域的原字段及供方确认资料逐项复核；当前仅验证来源一致性，不验证工程适配。',
          'Compare the same product-region fields with supplier-confirmed documents; source consistency does not verify engineering fit.')
    for key in TASKS
}


def bilingual(pair):
    return dict(zip(('zh', 'en'), pair))


def evaluate(card):
    result = []
    for task, (title, keys) in TASKS.items():
        indexes = [i for i, f in enumerate(card['fields']) if f['key'] in keys and informative(f['value'])]
        result.append({'task': task, 'title': bilingual(title), 'field_indexes': indexes,
            'citation_indexes': sorted({c for i in indexes for c in card['fields'][i]['citation_indexes']}),
            'state': 'SOURCE_INFORMATION_AVAILABLE' if indexes else 'UNKNOWN',
            'decision_readiness': 'SUPPLIER_CONFIRMATION_REQUIRED' if indexes else 'UNKNOWN',
            'buyer_requirements_known': False, 'engineering_fit': 'UNKNOWN',
            'relationships_verified': False, 'is_defect': False,
            'next_step': bilingual(ACTIONS[task]), 'question': bilingual(QUESTIONS[task]),
            'verification': bilingual(VERIFICATIONS[task])})
    return result
