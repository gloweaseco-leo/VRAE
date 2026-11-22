"""P1 scoring entry. Synthetic annotations do not become a score."""


def import_synthetic_annotations(rows):
    return {'status': 'NOT_EVALUABLE', 'imported': len(rows or []), 'score': None,
            'reason': 'SYNTHETIC_ANNOTATION_NOT_GOLD'}
