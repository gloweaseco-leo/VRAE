"""The integration exception accepts only the exact Owner-reviewed S4 bytes."""
from integration.l2_ops import s2_quality_verify as gate


def test_reviewed_overlay_matches_the_actual_approved_git_blobs():
    assert gate.reviewed_s4_overlay(sorted(gate.REVIEWED_S4_FILES), gate.REVIEWED_S4_BASE)


def test_no_permission_to_change_original_authority_guard_or_gold():
    for name in ('vrae/evidence/pack.py', 'vrae/l2/identity.py', 'vrae/l2_ops/briefs.py',
                 'tests/benchmark/human_gold.py', 'industry-packs/l2-industrial-v1/profile.json'):
        assert not gate.reviewed_s4_overlay(['vrae/l2/executive.py', name], gate.REVIEWED_S4_BASE)
    assert not gate.reviewed_s4_overlay(['vrae/l2/executive.py'], '0'*40)


def test_even_an_allowed_UI_path_cannot_change_its_approved_bytes(monkeypatch):
    original = gate.git

    def changed(*args):
        return '0'*40 if args == ('rev-parse', 'HEAD:vrae/l2/executive.py') else original(*args)

    monkeypatch.setattr(gate, 'git', changed)
    assert not gate.reviewed_s4_overlay(['vrae/l2/executive.py'], gate.REVIEWED_S4_BASE)
