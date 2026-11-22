"""Buyer-stage checklist. Industry names and item ids come only from the JSON pack."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / 'industry-packs' / 'l2-industrial-v1'
KEYS = ('version', 'profile', 'approval', 'label_aliases', 'items')
ROLES = {'DISCOVERABLE', 'PUBLISH', 'CLARIFY_CHANNEL'}
DECISIONS = {'REVIEW_REQUIRED', 'SOURCE_AVAILABLE', 'CLARIFY_ROUTE_RECORDED',
             'CLARIFY_ROUTE_UNKNOWN', 'GAP_WITH_EVIDENCE', 'UNKNOWN', 'NOT_APPLICABLE'}


def _canonical(doc):
    body = {k: doc[k] for k in ('version', 'profile', 'label_aliases', 'items')}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(doc):
    return hashlib.sha256(_canonical(doc).encode('utf-8')).hexdigest()


def load(name='buyer-stages-1.0.0.json'):
    doc = json.loads((ROOT / name).read_text(encoding='utf-8'))
    if set(doc) != set(KEYS):
        raise ValueError('BUYER_STAGE_SHAPE')
    if not isinstance(doc['label_aliases'], dict) or not doc['items']:
        raise ValueError('BUYER_STAGE_SHAPE')
    for item in doc['items']:
        if item['site_role'] not in ROLES or not item['field_groups']:
            raise ValueError('BUYER_STAGE_ITEM')
        if item['site_role'] != 'PUBLISH' and item.get('gap_condition'):
            raise ValueError('BUYER_STAGE_GAP_ROLE')
    return doc


def approved(doc):
    """A checklist file cannot approve itself. Formal approval stays on the existing review ledger."""
    del doc
    return False


def _norm(text):
    return ''.join(ch for ch in text.casefold() if ch.isalnum())


def match_groups(doc, fields):
    """Map extracted labels to checklist groups. Labels come from the pack, not from code."""
    aliases = {_norm(label): group for group, labels in doc['label_aliases'].items() for label in labels}
    found: dict[str, list[dict]] = {str(group): [] for group in doc['label_aliases']}
    for field in fields:
        group = aliases.get(_norm(field['label']))
        if group:
            found[group].append(field)
    return found


def judge(doc, *, groups, parsed, ambiguous, technical_link, contact_recorded, grant=False):
    """JSON approval is ignored. grant is only for the decision table, never set from the checklist file."""
    signed = grant is True
    rows = []
    for item in doc['items']:
        present = all(groups.get(group) for group in item['field_groups'])
        if not signed:
            decision = 'REVIEW_REQUIRED'
        elif ambiguous or not parsed:
            decision = 'UNKNOWN'
        elif item['site_role'] == 'CLARIFY_CHANNEL':
            decision = 'CLARIFY_ROUTE_RECORDED' if contact_recorded else 'CLARIFY_ROUTE_UNKNOWN'
        elif item['site_role'] == 'PUBLISH' and present:
            decision = 'SOURCE_AVAILABLE'
        elif item['site_role'] == 'PUBLISH' and technical_link:
            decision = 'UNKNOWN'
        elif item['site_role'] == 'PUBLISH':
            decision = 'GAP_WITH_EVIDENCE'
        else:
            decision = 'SOURCE_AVAILABLE' if present else 'UNKNOWN'
        if item['site_role'] == 'CLARIFY_CHANNEL' and decision == 'GAP_WITH_EVIDENCE':
            raise ValueError('CLARIFY_CHANNEL_GAP')
        if decision not in DECISIONS:
            raise ValueError('BUYER_STAGE_DECISION')
        rows.append({'item_id': item['item_id'], 'stage': item['stage'], 'site_role': item['site_role'],
                     'decision': decision, 'is_defect': decision == 'GAP_WITH_EVIDENCE',
                     'question': item['buyer_question']})
    return rows
