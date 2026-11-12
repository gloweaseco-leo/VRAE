"""Hosted CI must consume frozen expectations, not merely recreate examples."""
import json

from scripts.verify_ra3b import ARCHIVE, replay


def test_archived_fixed_replay():
    result = replay(json.loads(ARCHIVE.read_text(encoding='utf-8')))
    assert result['status'] == 'OFFLINE_PRIVATE_REPLAY_PASS'
    assert len({c['expected_pack_ref'] for c in result['cases']}) == 3
