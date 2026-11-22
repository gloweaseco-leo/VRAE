"""Role coverage for diagnostic 1.0.8. The denominator is declared before the visit."""
PREDECLARED = ('HOME', 'CATEGORY', 'PRODUCT', 'CONTACT', 'ABOUT')
REASONS = ('UNSELECTED', 'LIMIT_REACHED', 'ACCESS_BLOCKED', 'UNSUPPORTED_FORMAT',
           'EVIDENCE_INSUFFICIENT', 'NOT_APPLICABLE')


def extend(pack, scope):
    manifests = [source['document'] for source in pack.document['sources'] if source['kind'] == 'CaptureManifest']
    inventory_roles = {item.get('role') for manifest in manifests for item in manifest.get('inventory') or []}
    visited = [page.get('request_role') for page in scope.get('visited_pages') or []]
    observed = sorted({role for role in visited if role})
    failed = scope.get('failed_attempt_records') or []
    selected = [{'role': role, 'reason': 'VISITED'} for role in PREDECLARED if role in observed]
    uncovered = []
    fetched = len(scope.get('visited_pages') or [])
    for role in PREDECLARED:
        if role in observed:
            continue
        match = next((page for page in failed if page.get('request_role') == role), None)
        if match and match.get('reason') == 'ACCESS_BLOCKED':
            code = 'ACCESS_BLOCKED'
        elif match and match.get('reason') in ('CONTENT_TYPE_INVALID', 'UNSUPPORTED_FORMAT'):
            code = 'UNSUPPORTED_FORMAT'
        elif match and match.get('reason') in ('EVIDENCE_INSUFFICIENT', 'CONTENT_ENCODING_INVALID'):
            code = 'EVIDENCE_INSUFFICIENT'
        elif role not in inventory_roles and role not in {page.get('request_role') for page in failed}:
            code = 'NOT_APPLICABLE'
        elif fetched >= 6:
            code = 'LIMIT_REACHED'
        else:
            code = 'UNSELECTED'
        if code not in REASONS:
            code = 'UNSELECTED'
        uncovered.append({'role': role, 'reason_code': code, 'is_defect': False})
    enabled = 0
    passed_or_failed = 0
    return {'selected_roles': selected, 'observed_roles': observed, 'uncovered_roles': uncovered,
            'rule_coverage': {'numerator': sum(role in observed for role in PREDECLARED),
                              'denominator': len(PREDECLARED),
                              'denominator_basis': 'PREDECLARED_ROLES',
                              'enabled_rules': enabled, 'judged_rules': passed_or_failed,
                              'unvisited_is_defect': False}}
