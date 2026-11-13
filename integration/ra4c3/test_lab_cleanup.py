"""Unit failure-path checks, explicitly not PostgreSQL integration evidence."""
import json
import subprocess

import pytest

from integration.ra4c3 import lab


def test_partial_start_without_state_cleans_receipt_only(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, 'OWN', tmp_path)
    output, state = tmp_path / 'startup', tmp_path / 'state.json'
    owned = {'container': 'vrae-ra4c3-012345abcdef',
             'network': 'vrae-ra4c3-012345abcdef-local',
             'volume': 'vrae-ra4c3-012345abcdef-data'}
    calls = []

    def fail(_state, folder):
        folder.mkdir()
        (folder / 'ownership.json').write_text(json.dumps(owned))
        raise RuntimeError('PORT_MISSING')

    monkeypatch.setattr(lab, '_start', fail)
    monkeypatch.setattr(lab, 'cleanup_owned', lambda s, o: calls.append((s, o)))
    with pytest.raises(RuntimeError, match='PORT_MISSING'):
        lab.start(state, output)
    assert calls == [(owned, output / 'failure-cleanup')]
    assert not state.exists()


def test_cleanup_refuses_foreign_label_without_remove(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, 'OWN', tmp_path)
    calls = []

    def inspect(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, b'{"vrae.ra4c3":"OTHER"}', b'')

    monkeypatch.setattr(lab.subprocess, 'run', inspect)
    with pytest.raises(AssertionError):
        lab.cleanup_owned({'container': 'vrae-ra4c3-012345abcdef',
                           'network': 'vrae-ra4c3-012345abcdef-local',
                           'volume': 'vrae-ra4c3-012345abcdef-data'}, tmp_path / 'cleanup')
    assert len(calls) == 1
    assert 'rm' not in calls[0]


def test_migration_failure_removes_owned_state(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, 'OWN', tmp_path)
    state = tmp_path / 'state.json'
    state.write_text('{}')
    calls = []

    def fail(_state):
        raise RuntimeError('MIGRATION_FAILED')

    def stop(s, output):
        calls.append((s, output))
        s.unlink()

    monkeypatch.setattr(lab, 'migrate', fail)
    monkeypatch.setattr(lab, 'stop', stop)
    with pytest.raises(RuntimeError, match='MIGRATION_FAILED'):
        lab.bootstrap_action('migrate', state, tmp_path / 'cleanup')
    assert calls == [(state, tmp_path / 'cleanup')]
    assert not state.exists()


def test_cleanup_accepts_lowercase_absence_and_checks_each_resource(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, 'OWN', tmp_path)
    calls = []

    def absent(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, b'', b'Error: no such object: ' + args[-1].encode())

    monkeypatch.setattr(lab.subprocess, 'run', absent)
    lab.cleanup_owned({'container': 'vrae-ra4c3-012345abcdef',
                       'network': 'vrae-ra4c3-012345abcdef-local',
                       'volume': 'vrae-ra4c3-012345abcdef-data'}, tmp_path / 'cleanup')
    assert len(calls) == 6
    assert all('rm' not in call for call in calls)
    receipt = json.loads((tmp_path / 'cleanup/teardown.json').read_text())
    assert len(receipt['resources']) == 3
    assert all(row['absent_after'] for row in receipt['resources'])
