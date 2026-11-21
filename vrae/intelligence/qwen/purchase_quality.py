"""Bounded task/label admission; no generic semantic or engineering approval."""
from collections import defaultdict

from vrae.industry.l2_v1.pack import load
from vrae.industry.l2_v1.procurement import configuration, normalized
from vrae.industry.l2_v1.purchase_tasks import TASKS, ACTIONS, QUESTIONS, VERIFICATIONS, informative
from .provider import fail
from .source_values import value


def check_purchase(claim, entries, language):
    task = claim.get('purchase_task')
    if task not in TASKS or claim.get('opportunity_kind') != 'CLARIFICATION' or claim['task'] != 'UNDERSTAND':
        fail('PURCHASE_TASK_REQUIRED')
    i = 0 if language == 'zh' else 1
    if (claim['rebuild'] != [ACTIONS[task][i]] or claim['questions'] != [QUESTIONS[task][i]]
            or claim['verification'] != VERIFICATIONS[task][i]):
        fail('UNSUPPORTED_PURCHASE_ACTION')
    _, aliases = configuration(load()['profile'], '1.1.0')
    pairs: dict[tuple, dict] = defaultdict(dict)
    for ref in claim['refs'] + claim['counter_refs']:
        entry = entries[ref]
        if entry['type'] != 'GUARD_LITERAL' or entry['fact']['rule_id'] != 'INFO-01':
            continue
        c = entry['fact']['source']['citation']
        text = value(entry['fact'])
        if text and c.get('fact_role') in ('SPEC_LABEL','SPEC_VALUE'):
            pairs[(c.get('product_scope_ref'),c.get('field_index'))][c['fact_role']] = text
    keys = {aliases.get(normalized(p['SPEC_LABEL'])) for p in pairs.values()
            if set(p)=={'SPEC_LABEL','SPEC_VALUE'} and informative(p['SPEC_VALUE'])} & TASKS[task][1]
    if len(keys) < (2 if task == 'OPTION_SELECTION' else 1):
        fail('PURCHASE_TASK_LABEL_VALUE_REQUIRED')
    supported_values = [p['SPEC_VALUE'] for p in pairs.values() if set(p)=={'SPEC_LABEL','SPEC_VALUE'}
        and aliases.get(normalized(p['SPEC_LABEL'])) in TASKS[task][1] and informative(p['SPEC_VALUE'])]
    if not any(normalized(v) in normalized(claim['explanation']) for v in supported_values):
        fail('PURCHASE_EXPLANATION_SOURCE_VALUE_REQUIRED')
