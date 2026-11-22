"""vrae.report-content-units.v1. Strength is fixed by review state, not by display order."""
from copy import deepcopy
import hashlib
import json

CONTRACT = 'vrae.report-content-units.v1'
STRENGTHS = ('CONFIRMED_BY_REVIEW', 'EVIDENCED_PENDING_REVIEW', 'HYPOTHESIS', 'UNKNOWN')
GROUPS = ('D1', 'D2', 'D3', 'D4', 'D5', 'D6')


def _encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def build(rows):
    units = []
    for row in rows:
        if row.get('group') not in GROUPS or row.get('strength') not in STRENGTHS:
            raise ValueError('CONTENT_UNIT')
        body = {'unit_id': row['unit_id'], 'group': row['group'], 'strength': row['strength'],
                'text': {'zh': row['text']['zh'], 'en': row['text']['en']},
                'evidence_ids': list(row.get('evidence_ids') or []),
                'limit': row.get('limit') or '本次样本',
                'review_status': 'CONFIRMED_BY_REVIEW' if row['strength'] == 'CONFIRMED_BY_REVIEW' else 'REVIEW_REQUIRED'}
        body['unit_sha256'] = hashlib.sha256(_encode({k: v for k, v in body.items() if k != 'unit_sha256'})).hexdigest()
        units.append(body)
    return {'contract': CONTRACT, 'units': units, 'reorder_allowed': True,
            'strength_mutable': False, 'semantic_mutable': False}


def project(units, order):
    """Reference consumer rule: reorder only. Strength, group and text stay byte-identical."""
    by_id = {unit['unit_id']: unit for unit in units['units']}
    if set(order) != set(by_id) or len(order) != len(by_id):
        raise ValueError('CONTENT_UNIT_SET')
    projected = []
    for unit_id in order:
        source = by_id[unit_id]
        copy = deepcopy(source)
        if copy['strength'] != source['strength'] or copy['group'] != source['group'] or copy['text'] != source['text']:
            raise ValueError('CONTENT_UNIT_SEMANTICS')
        if copy['strength'] != 'CONFIRMED_BY_REVIEW':
            copy['presented_as_confirmed'] = False
        else:
            copy['presented_as_confirmed'] = True
        projected.append(copy)
    return {'contract': CONTRACT, 'units': projected}
