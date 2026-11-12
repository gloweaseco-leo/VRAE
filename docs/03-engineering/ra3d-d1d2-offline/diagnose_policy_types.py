"""Minimal self-review probe; records actual behavior of the initial candidate."""
from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tests.reviewing.synthetic import inputs
from vrae.reviewing import ReviewError, build_target
from vrae.reviewing.canonical import canonical, parse

i = inputs()
rows = []
for case in ('policy_bool_version', 'held_bool_issue_count'):
    trust = i.trust
    if case == 'policy_bool_version':
        p = parse(trust.policy)
        p['scope']['policy_version'] = True
        trust = replace(trust, policy=canonical(p))
    else:
        h = parse(trust.held)
        h['expected_issue_count'] = True
        trust = replace(trust, held=canonical(h))
    try:
        t = build_target(i.document, i.html, i.source, trust=trust)
        result = {'case': case, 'actual': 'ACCEPTED', 'target_digest': t.target_digest}
    except ReviewError as exc:
        result = {'case': case, 'actual': 'REFUSED', 'code': exc.code}
    rows.append(result)
print(json.dumps({'python': sys.version, 'results': rows}, indent=2))
