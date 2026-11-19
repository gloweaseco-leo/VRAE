"""Failure paths must not overwrite a deployment or leave its backup source off."""

import json
import pytest
from infra.linux_service import control


def setup_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "config", lambda _: (tmp_path, {"image": "sha256:" + "1" * 64}))
    monkeypatch.setattr(control, "inspect", lambda *_: None)
    (tmp_path / "data.tar.gz").write_bytes(b"corrupted")
    (tmp_path / "ledger.tar.gz").write_bytes(b"ledger")
    (tmp_path / "backup.json").write_text(
        json.dumps({"files": {"data.tar.gz": "0" * 64, "ledger.tar.gz": "0" * 64}})
    )
    calls = []
    monkeypatch.setattr(control, "docker", lambda *a, **k: calls.append(a))
    return calls


def test_corrupt_backup_cannot_create_or_replace_a_volume(tmp_path, monkeypatch):
    calls = setup_restore(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="BACKUP_HASH_MISMATCH"):
        control.restore("vrae-recovery", tmp_path, tmp_path)
    assert calls == []


def test_restore_never_overwrites_an_existing_deployment(tmp_path, monkeypatch):
    calls = setup_restore(tmp_path, monkeypatch)
    monkeypatch.setattr(
        control, "inspect", lambda kind, name: {"existing": True} if kind == "volume" else None
    )
    with pytest.raises(PermissionError, match="RESTORE_REQUIRES_NEW_DEPLOYMENT"):
        control.restore("vrae-recovery", tmp_path, tmp_path)
    assert calls == []


def test_backup_failure_still_restarts_original_service(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "config", lambda _: (tmp_path, {"image": "sha256:" + "1" * 64}))
    phases = []
    monkeypatch.setattr(control, "stop", lambda _: phases.append("stopped"))
    monkeypatch.setattr(control, "up", lambda *_: phases.append("restarted"))
    monkeypatch.setattr(control, "owned", lambda *_: {"owned": True})

    def unavailable(*_, **__):
        raise RuntimeError("DISK_IO_FAILURE")

    monkeypatch.setattr(control, "docker", unavailable)
    with pytest.raises(RuntimeError, match="DISK_IO_FAILURE"):
        control.backup("vrae-primary", tmp_path, tmp_path / "backup")
    assert phases == ["stopped", "restarted"]
    assert not (tmp_path / "backup" / "backup.json").exists()


def test_foreign_resource_label_is_never_adopted(monkeypatch):
    monkeypatch.setattr(
        control, "inspect", lambda *_: {"Config": {"Labels": {control.LABEL: "someone-else"}}}
    )
    with pytest.raises(PermissionError, match="RESOURCE_OWNERSHIP_MISMATCH"):
        control.owned("container", "vrae-primary-runtime", "vrae-primary")


def test_model_activation_reuses_existing_pg_and_linux_private_operator_volume(monkeypatch):
    events = []
    monkeypatch.setattr(control, 'owned', lambda *a: {'existing': True})
    monkeypatch.setattr(control, 'inspect', lambda *a: {'Config': {'Labels': {'vrae.source_sha': '2' * 40}}})
    monkeypatch.setattr(control, 'docker', lambda *a, **k: json.dumps({
        'image': 'sha256:' + '1' * 64, 'source_sha': '1' * 40}).encode())
    monkeypatch.setattr(control, 'start_runtime', lambda owner, names, root, d:
                        events.append((owner, names['pg'], root, d['isolated_model_runtime'])))
    monkeypatch.setattr(control, 'start_ai', lambda *a: None)
    monkeypatch.setattr(control, 'config', lambda *a: pytest.fail('NO_HOST_SECRET_DIRECTORY_ALLOWED'))
    result = control.activate_model('vrae-current', 'sha256:' + '2' * 64)
    assert events == [('vrae-current', 'vrae-current-pg', None, True)]
    assert result['same_pg'] == 'vrae-current-pg' and result['same_ledger'] == 'vrae-current-ledger'
    assert result['model_go_attested'] is False


def test_model_activation_refuses_missing_existing_authority_before_mutation(monkeypatch):
    monkeypatch.setattr(control, 'owned', lambda *a: False)
    monkeypatch.setattr(control, 'docker', lambda *a, **k: pytest.fail('NO_MUTATION_ALLOWED'))
    with pytest.raises(PermissionError, match='EXISTING_DEPLOYMENT_REQUIRED'):
        control.activate_model('vrae-current', 'sha256:' + '2' * 64)


def test_shared_model_quota_mounts_same_canonical_ledger(monkeypatch):
    calls = []
    monkeypatch.setattr(control, 'owned', lambda *a: {'existing': True})
    monkeypatch.setattr(control, 'docker', lambda *a, **k: calls.append(a))
    control.start_ai('vrae-windows', control.names('vrae-windows'), {
        'image': 'sha256:' + '1' * 64, 'model_quota_owner': 'vrae-local',
        'model_quota_shared': True})
    created = next(c for c in calls if c[0] == 'create')
    assert 'type=volume,src=vrae-local-ledger,dst=/model-ledger,volume-subpath=qwen' in created
    assert not any(c[:2] == ('volume', 'create') for c in calls)


@pytest.mark.parametrize('exists,shared,code', [
    (False, True, 'EXISTING_QUOTA_VOLUME_REQUIRED'),
    (True, False, 'EXPLICIT_SHARED_QUOTA_REQUIRED')])
def test_shared_model_quota_fails_before_container_creation(monkeypatch, exists, shared, code):
    monkeypatch.setattr(control, 'owned', lambda kind, *a: kind == 'network' or exists)
    monkeypatch.setattr(control, 'docker', lambda *a, **k: pytest.fail('NO_MUTATION_ALLOWED'))
    with pytest.raises(PermissionError, match=code):
        control.start_ai('vrae-windows', control.names('vrae-windows'), {
            'image': 'sha256:' + '1' * 64, 'model_quota_owner': 'vrae-local',
            'model_quota_shared': shared})
