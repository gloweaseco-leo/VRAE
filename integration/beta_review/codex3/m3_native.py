"""Own Linux supervisor: original API plus actual independent M1 Worker."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from integration.ra4a import support as old
from integration.ra4b import runtime_check as native


def main():
    assert os.geteuid() == 0 and not Path("/var/run/docker.sock").exists()
    state = json.load(sys.stdin)
    state["port"] = 5432
    # Trusted TEST_ONLY provisioning only; no client-selected URL or DB grant.
    extra_sources = state.get("l2_source_refs", [])
    assert extra_sources in ([], ["l2-industrial-native-v1"])
    private = Path("/tmp/beta-supervisor")
    private.mkdir(mode=0o700)
    old.STATE = private / "state.json"
    old.STATE.write_text(json.dumps(state))
    old.STATE.chmod(0o600)
    native.OUT = Path("/evidence")
    try:
        if extra_sources and "l2_evidence_owner" in state:
            from integration.l2_ops.provisioning import prepare_evidence_directory
            evidence_owner = prepare_evidence_directory(native.OUT, state["l2_evidence_owner"])
            (native.OUT / "evidence-owner.json").write_text(json.dumps(evidence_owner))
        app_path, app_config = native.provision("APP", 10001)
        if extra_sources:
            from integration.l2_ops.provisioning import extend_app_sources
            extend_app_sources(app_config, state["l2_source_binding"])
            # Native provision already made this file UID10001/0600. Write as
            # that same owner before API spawn; root has no DAC override here.
            subprocess.run(
                [sys.executable, "-B", "-m", "integration.l2_ops.provisioning", str(app_path)],
                input=json.dumps(app_config).encode(), check=True, timeout=10,
                capture_output=True, user=10001, group=10001, extra_groups=[],
                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": "/work",
                     "PYTHONDONTWRITEBYTECODE": "1", "VRAE_RA4B_TEST_ONLY": "1"},
            )
        consumer_dir = Path("/tmp/m3-consumer")
        consumer_dir.mkdir(mode=0o700)
        consumer_profile = consumer_dir / "config.json"
        consumer_profile.write_text(
            json.dumps(
                {
                    "bearer": app_config["bearer"],
                    "tenant_id": app_config["tenant"],
                    "source_refs": ["accepted-404", "accepted-200"] + extra_sources,
                }
            )
        )
        consumer_profile.chmod(0o600)
        os.chown(consumer_profile, 10003, 10003)
        os.chown(consumer_dir, 10003, 10003)
        worker_path, _ = native.provision("WORKER", 10002)
        api, _ = native.spawn("APP", app_path)
        native.wait_for(lambda: native.LOGS[0].exists() and b"READY" in native.LOGS[0].read_bytes())
        stream = (native.OUT / "m1-worker.log").open("ab")
        worker = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "integration.beta_review.codex3.m3_worker",
                "--config",
                str(worker_path),
            ],
            cwd="/work",
            stdin=subprocess.PIPE,
            stdout=stream,
            stderr=stream,
            user=10002,
            group=10002,
            extra_groups=[],
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "PYTHONPATH": "/work",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "VRAE_RA4B_TEST_ONLY": "1",
            },
        )
        stream.close()
        worker.b4_uid = 10002
        native.CHILDREN.append(worker)
        native.wait_for(lambda: b"M1_WORKER_READY" in (native.OUT / "m1-worker.log").read_bytes())
        (native.OUT / "native-result.json").write_text(
            json.dumps(
                {
                    "native_python": sys.version.split()[0],
                    "mode": "M1_REAL_GENERATION",
                    "app_uid": 10001,
                    "consumer_uid": 10003,
                    "consumer_entry": "vrae.application.ra4b_p2.m1.consumer.TaskClient",
                    "consumer_profile_fields": ["bearer", "tenant_id", "source_refs"],
                    "canonical_worker_entry": "vrae.application.ra4b_p2.m1.runtime",
                    "worker_uid": 10002,
                    "worker_entry": "integration.beta_review.codex3.m3_worker",
                    "accepted_processing": "vrae.application.ra4b_p2.m1.runtime",
                    "generated_rows_seeded": 0,
                    "records": [],
                }
            )
        )
        (native.OUT / "ready.json").write_text('{"actual_api_worker_ready":true}')
        handled = set()
        end = time.monotonic() + 1800
        while not (native.OUT / "stop.json").exists() and time.monotonic() < end:
            assert api.poll() is None and worker.poll() is None, "M3_RUNTIME_CHILD_EXIT"
            for wake in sorted(native.OUT.glob("*.wake.json")):
                if wake.name in handled:
                    continue
                assert json.loads(wake.read_bytes()) == {"process_one": True}
                worker.stdin.write(b'{"process_one":true}\n')
                worker.stdin.flush()
                handled.add(wake.name)
            time.sleep(0.2)
    finally:
        for child in reversed(native.CHILDREN):
            native.signal_child(child, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                native.signal_child(child, signal.SIGKILL)
                child.wait(timeout=5)
        old.STATE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
