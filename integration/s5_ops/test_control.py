"""Original private control response read, never a repeated signed operation."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.beta_review.codex3 import m3_browser_run as driver


@pytest.mark.parametrize("platform,retries", [("nt", 1), ("posix", 0)])
def test_response_lock_uses_original_deadline_and_does_not_reissue(tmp_path, monkeypatch, platform, retries):
    (tmp_path / "m3-control").mkdir()
    monkeypatch.setattr(driver, "folder_for", lambda label: tmp_path)
    monkeypatch.setattr(driver, "launch_for", lambda label: tmp_path)
    monkeypatch.setattr(driver, "os", SimpleNamespace(name=platform))
    writes = []
    sleeps = []

    def write(request, value):
        writes.append(value)
        request.write_text(json.dumps(value), encoding="utf-8")
        response = request.with_name(request.name.replace(".request.json", ".response.json"))
        response.write_text(json.dumps({"ok": True}), encoding="utf-8")

    original = Path.read_bytes
    reads = []

    def read(path):
        if path.name.endswith(".response.json"):
            reads.append(path)
            if len(reads) == 1:
                raise PermissionError("transient private file lock")
        return original(path)

    monkeypatch.setattr(driver, "control_write", write)
    monkeypatch.setattr(Path, "read_bytes", read)
    monkeypatch.setattr(driver.time, "sleep", lambda delay: sleeps.append(delay))
    if retries:
        assert driver.control("synthetic", "sign", nonce="test-only") == {"ok": True}
        assert len(reads) == 2 and sleeps == [0.05]
    else:
        with pytest.raises(PermissionError):
            driver.control("synthetic", "sign", nonce="test-only")
        assert len(reads) == 1 and sleeps == []
    assert writes == [{"operation": "sign", "nonce": "test-only"}]
