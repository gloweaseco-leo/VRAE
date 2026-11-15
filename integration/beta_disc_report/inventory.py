"""Exact additive DISC partition; accepted B5 verifier checks its intact layer."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'docs/03-engineering/beta-disc-report/exact-test-ids.json'
MANIFEST_SHA256 = 'b249159ea69f2f96497aa94d9e816e3360b515ebb0c8f05ba55777c24d02a502'


def verify_inventory(cases):
    raw = MANIFEST.read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(raw).hexdigest() == MANIFEST_SHA256
    manifest = json.loads(raw)
    original, b5, disc = (manifest[k] for k in
                          ('baseline_ids', 'accepted_main_additions', 'added_ids'))
    assert len(original) == len(set(original)) == 2473
    assert len(b5) == len(set(b5)) == 2
    assert len(disc) == len(set(disc)) == 46
    expected = set(original) | set(b5) | set(disc)
    assert len(expected) == manifest['expected_total'] == 2521
    ids = [c.get('classname', '') + '::' + c.get('name', '') for c in cases]
    assert len(ids) == len(set(ids)) == 2521
    assert set(ids) == expected, 'DISC_ACCEPTED_FULL_ID_SET_CHANGED'
    selected = [(c, ident) for c, ident in zip(cases, ids) if ident in set(disc)]
    assert len(selected) == 46
    assert all(c.find(tag) is None for c, _ in selected
               for tag in ('skipped', 'failure', 'error'))
    for relative, expected_hash in manifest['added_test_sources'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == expected_hash
    accepted = [c for c, ident in zip(cases, ids) if ident not in set(disc)]
    assert len(accepted) == 2475
    return accepted, {'kind': 'EXACT_2473_ORIGINAL_PLUS_2_ACCEPTED_B5_PLUS_46_DISC',
        'manifest_sha256': MANIFEST_SHA256, 'actual_full_cases': len(cases),
        'accepted_b5_layer_cases': len(accepted), 'disc_cases': len(selected),
        'disc_skipped': 0, 'ids_unique': True, 'unknown_ids': 0,
        'test_discovery_filtered': False, 'original_b5_verifier_still_required': True}
