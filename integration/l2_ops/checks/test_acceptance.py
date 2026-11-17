"""Reject foreign resource metadata before any dump or cleanup. Not E2E."""
import json
from types import SimpleNamespace

import pytest

from integration.l2_ops import acceptance


@pytest.mark.parametrize("wrong", ["run", "label", "mount", "id"])
def test_owned_capture_rejects_foreign_resources_before_database_io(tmp_path, monkeypatch, wrong):
    record = {"pg": "owned-pg", "volume": "owned-code", "label": "vrae.beta.codex3", "value": "ownrun"}
    item = {"Id": "a"*64, "Config": {"Labels": {"vrae.b5_p0": "owned-pg"}}, "Mounts": [{"Name": "owned-pg-data"}]}
    if wrong == "run":
        record["value"] = "other-run"
    elif wrong == "label":
        item["Config"]["Labels"]["vrae.b5_p0"] = "other-pg"
    elif wrong == "mount":
        item["Mounts"][0]["Name"] = "other-data"
    (tmp_path/"ownership.json").write_text(json.dumps(record))
    calls = []
    def inspect(args):
        assert args == ["docker", "inspect", "owned-pg"]
        calls.append(args)
        return json.dumps([item]).encode()
    monkeypatch.setattr(acceptance, "command", inspect)
    with pytest.raises(AssertionError):
        acceptance.owned(tmp_path, "ownrun", "b"*64 if wrong == "id" else "a"*64)
    assert len(calls) == (0 if wrong == "run" else 1)


def test_native_acceptance_rejects_mismatched_driver_before_launch(monkeypatch):
    monkeypatch.setattr(acceptance, "sys", SimpleNamespace(version_info=(3, 11)))
    monkeypatch.setattr(acceptance.local_app, "start", lambda *a, **k: pytest.fail("must not create resources"))
    with pytest.raises(AssertionError, match="NATIVE_DRIVER_MINOR_MISMATCH"):
        acceptance.accept("ownrun", "3.13")
