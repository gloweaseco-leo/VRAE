"""CONTROL_SUBPROCESS_ONLY_NO_PG: deterministic stop-before-initialization ordering."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from integration.beta_review.codex3 import local_app


def test_stop_before_child_initialization_does_not_create_run_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(local_app, "PRIVATE", tmp_path)
    label = "controlled-cancel-race-001"
    launch = tmp_path / "local-launches" / label
    launch.mkdir(parents=True)
    folder = tmp_path / label
    # This child models only Run's exclusive directory creation. It cannot start PG.
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys;from pathlib import Path;sys.stdin.buffer.read(1);Path(sys.argv[1]).mkdir(exist_ok=False)",
            str(folder),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    (launch / "local-launch.json").write_text(
        json.dumps(
            {
                "run": label,
                "mode": "EXISTING_COMPONENT_PREVIEW_NOT_WHOLE_APP_PASS",
                "source_sha": "759476092bc88cebc2045e13997fd52a1c79385b",
                "supervisor_pid": child.pid,
            }
        )
    )
    try:
        assert local_app.main(["stop", "--run", label]) == 0
    finally:
        _output, error = child.communicate(b"x", timeout=10)
    assert child.returncode == 0, error.decode(errors="replace")
    assert folder.is_dir()
    assert (launch / "stop.json").exists()


def _reserve(tmp_path, monkeypatch, label):
    monkeypatch.setattr(local_app, "PRIVATE", tmp_path)
    launch = tmp_path / "local-launches" / label
    launch.mkdir(parents=True)
    (launch / "local-launch.json").write_text(
        json.dumps(
            {
                "run": label,
                "mode": "EXISTING_COMPONENT_PREVIEW_NOT_WHOLE_APP_PASS",
                "source_sha": "759476092bc88cebc2045e13997fd52a1c79385b",
                "supervisor_pid": None,
            }
        )
    )
    return launch


def test_cancel_before_supervisor_never_invokes_business_runner(tmp_path, monkeypatch):
    from integration.beta_review.codex3 import runner

    label = "controlled-pre-start-cancel"
    launch = _reserve(tmp_path, monkeypatch, label)
    called = []
    monkeypatch.setattr(runner, "main", lambda: called.append(True))
    local_app.request_stop(label)
    assert local_app.supervise(label, "3.11") == 0
    assert not called and not (tmp_path / label).exists()
    result = local_app.status(label)
    assert result["state"] == "CLOSED" and "url" not in result
    assert json.loads((launch / "cancelled-before-start.json").read_text()) == {
        "cancelled_before_run": True,
        "resources_started": False,
    }


def test_supervisor_exception_is_failed_not_starting_or_closed(tmp_path, monkeypatch):
    import pytest

    from integration.beta_review.codex3 import runner

    label = "controlled-start-exception"
    _reserve(tmp_path, monkeypatch, label)

    def fail():
        raise RuntimeError("CONTROL_ONLY_INJECTED_START_EXCEPTION_NO_PG")

    monkeypatch.setattr(runner, "main", fail)
    with pytest.raises(RuntimeError, match="CONTROL_ONLY"):
        local_app.supervise(label, "3.11")
    result = local_app.status(label)
    assert result["state"] == "FAILED_START_CLEANUP_UNCONFIRMED"
    assert result["component_result"] == "STARTUP_FAILED" and "url" not in result


def test_cancel_after_first_phase_runs_cleanup_without_starting_pg(tmp_path, monkeypatch):
    from integration.beta_review.codex3 import runner

    label = "controlled-between-phases"
    launch = _reserve(tmp_path, monkeypatch, label)
    monkeypatch.setattr(runner, "PRIVATE", tmp_path)
    calls = []

    class ControlOnlyRun:
        def __init__(self, name, minor, *, b5):
            self.result = {}
            (tmp_path / name).mkdir()
            self.r = None

        def case(self, name, operation):
            calls.append(name)
            return operation()

        def pipeline(self):
            local_app.control_write(launch / "stop.json", {"stop": True})

        def start_pg(self):
            raise AssertionError("PG_MUST_NOT_START")

        def start_native(self):
            raise AssertionError("WORKER_MUST_NOT_START")

        def start_ssr(self):
            raise AssertionError("SSR_MUST_NOT_START")

        def cleanup(self):
            calls.append("CONTROL_ONLY_CLEANUP")

        def publish(self):
            assert self.result["status"] == "CANCELLED_DURING_STARTUP"
            calls.append("CONTROL_ONLY_PUBLISH")

    monkeypatch.setattr(runner, "Run", ControlOnlyRun)
    monkeypatch.setattr(sys, "argv", ["beta_internal.py", "start", "--run", label, "--phase", "s2"])
    runner.main()
    assert calls == [
        "live_offline_source_policy_six_rules_guard_report",
        "owned_cleanup",
        "CONTROL_ONLY_CLEANUP",
        "CONTROL_ONLY_PUBLISH",
    ]


def test_process_spawn_exception_is_visible_without_fake_cleanup(tmp_path, monkeypatch):
    import pytest

    label = "controlled-spawn-failure"
    monkeypatch.setattr(local_app, "PRIVATE", tmp_path)
    monkeypatch.setattr(
        local_app,
        "doctor",
        lambda: {
            "candidate_sha": "759476092bc88cebc2045e13997fd52a1c79385b",
            "business_flow": "BLOCKED_MISSING_ACCEPTED_PORTS",
        },
    )

    def fail(*args, **kwargs):
        raise OSError("CONTROL_ONLY_INJECTED_PROCESS_FAILURE")

    monkeypatch.setattr(local_app.subprocess, "Popen", fail)
    with pytest.raises(OSError, match="CONTROL_ONLY"):
        local_app.start(label, "3.11", True)
    result = local_app.status(label)
    assert result["state"] == "FAILED_START_CLEANUP_UNCONFIRMED"
    assert not (tmp_path / label).exists()
