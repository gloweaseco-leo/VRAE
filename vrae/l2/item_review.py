"""Per-item review records on the existing C2 decision shape.

Reviewer identity comes from the caller. This module does not embed a person.
Synthetic identities cannot set formal_human_review. A revised hash retires the
previous approval. The wrong recipient is refused.
"""
DIFFS = ('WORDING', 'STRENGTH', 'EVIDENCE', 'REJECTION_REASON')
ACTIONS = ('CONFIRM', 'MODIFY', 'REJECT')


def _synthetic(identity):
    ref = str((identity or {}).get('verification_ref') or '')
    mode = (identity or {}).get('directory_mode')
    return mode == 'CONTROLLED' or ref.startswith('TEST_') or ref.startswith('SYNTHETIC_') or not ref


def decide(items, identity):
    if any(item.get('action') not in ACTIONS or item.get('diff_class') not in DIFFS for item in items):
        raise ValueError('REVIEW_ITEM')
    formal = False if _synthetic(identity) else bool(identity.get('verification_ref'))
    return {'items': [{**item, 'review_status': 'RECORDED'} for item in items],
            'formal_human_review': formal, 'reviewer_id': identity.get('actor_id'),
            'synthetic': _synthetic(identity)}


def approve_hash(receipt, content_hash):
    if receipt.get('content_hash') != content_hash:
        raise ValueError('STALE_APPROVAL')
    return {'approved_hash': content_hash, 'formal_human_review': False if receipt.get('synthetic') else receipt.get('formal_human_review')}


def revision_invalidates(approved_hash, current_hash):
    return approved_hash != current_hash


def recipient_allowed(grant, recipient_id):
    return grant.get('subject_ref') == recipient_id and grant.get('status') == 'ACTIVE'


def revoke(grant):
    return {**grant, 'status': 'REVOKED', 'formal_human_review': False}


def weekly_summary(records):
    decided = [record for record in records if record.get('action') in ACTIONS]
    if not decided:
        return {'status': 'NOT_EVALUABLE', 'adoption_rate': None, 'modification_rate': None, 'denominator': 0}
    confirmed = sum(record['action'] == 'CONFIRM' for record in decided)
    modified = sum(record['action'] == 'MODIFY' for record in decided)
    return {'status': 'COMPUTED', 'denominator': len(decided),
            'adoption_rate': confirmed / len(decided), 'modification_rate': modified / len(decided),
            'formal_human_review': False}


def gold_candidates(records):
    return [{'origin': 'SIMULATED_NOT_HUMAN_GOLD', 'action': record.get('action'),
             'diff_class': record.get('diff_class'), 'formal_human_review': False,
             'elapsed_ms': record.get('elapsed_ms')} for record in records]
