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
