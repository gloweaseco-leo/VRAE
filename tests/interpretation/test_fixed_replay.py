"""Hosted CI must consume frozen expectations, not merely recreate examples."""
import json
import os

from scripts.verify_ra3b import ARCHIVE, replay


def test_archived_fixed_replay():
    result = replay(json.loads(ARCHIVE.read_text(encoding='utf-8')),
                    minimal_isolated_layout=os.environ.get('VRAE_ISOLATED_LAB') == '1')
    assert result['status'] == 'OFFLINE_PRIVATE_REPLAY_PASS'
    assert len({c['expected_pack_ref'] for c in result['cases']}) == 3
