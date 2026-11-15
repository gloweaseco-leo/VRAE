"""Linux-only supervisor; actual accepted API and UID-isolated low-role Worker."""
import json
import os
from pathlib import Path
import signal
import sys
import time
from integration.ra4a import support as old
from integration.ra4b import runtime_check as native
from integration.ra4b.support import config
from vrae.application.ra4b import store

def main():
    assert os.geteuid() == 0 and not Path("/var/run/docker.sock").exists()
    state = json.load(sys.stdin)
    state["port"] = 5432
    private = Path("/tmp/beta-supervisor")
    private.mkdir(mode=0o700)
    old.STATE = private/"state.json"
    old.STATE.write_text(json.dumps(state))
    old.STATE.chmod(0o600)
    native.OUT = Path("/evidence")
    records = []
    try:
        app_path, app_cfg = native.provision("APP",10001)
        worker_path, worker_cfg = native.provision("WORKER",10002)
        api, _ = native.spawn("APP",app_path)
        native.wait_for(lambda: (native.LOGS[0].exists() and b"READY" in native.LOGS[0].read_bytes()))
        with old.connect() as admin:
            for case in ("404","200"):
                code, receipt = native.request(app_cfg,payload={"source_ref":"accepted-"+case},
                    key="beta-integration-"+case)
                assert code == 202
                # A new independent observer sees the actual committed identifiers.
                with old.connect() as observer:
                    persisted = observer.execute(
                        "SELECT request_id FROM ra4a.requests WHERE request_id=%s",
                        (receipt["request_id"],)).fetchone()
                    assert str(persisted[0]) == receipt["request_id"]
                worker, worker_log = native.spawn("WORKER",worker_path,"--once")
                worker.wait(timeout=15)
                raw = worker_log.read_bytes()
                assert worker.returncode == 0 and b"TEST_ONLY_DONE" in raw and b"DENIED" not in raw
                code, status = native.request(app_cfg,"GET","/v1/audit-requests/"+receipt["request_id"])
                assert code == 200 and status["status"] == "TEST_ONLY_CONSUMED"
                epoch = admin.execute("SELECT epoch FROM ra4b_test.request_origins WHERE request_id=%s",
                    (receipt["request_id"],)).fetchone()[0]
                job = admin.execute("SELECT state,lease_seq,attempts FROM ra4a.jobs WHERE job_id=%s",
                    (receipt["job_id"],)).fetchone()
                assert job[0] == "TEST_ONLY_DONE"
                audit=admin.execute("SELECT count(*) FROM ra4a.audit WHERE run_id=%s AND action='TEST_ONLY_CONSUMED'",
                    (receipt["run_id"],)).fetchone()[0]
                outbox=admin.execute("SELECT count(*) FROM ra4a.outbox WHERE run_id=%s AND kind='TEST_ONLY_CONSUMED'",
                    (receipt["run_id"],)).fetchone()[0]
                assert audit == outbox == 1
                records.append({"consumed_audit":audit,"consumed_outbox":outbox,"case":case,"receipt":receipt,"status":status,"origin_epoch":epoch,
                    "job_state":job[0],"lease_seq":job[1],"attempts":job[2],"worker_uid":10002,
                    "app_uid":10001,"commit_observed_before_worker":True,
                    "generated_report_by_worker":False})
            assert native.request(app_cfg,overrides={"Authorization":"Bearer invalid"} )[0] == 401
            cfg_b = config("APP","b")
            with store.connect(cfg_b) as c:
                try:
                    cross = store.status(c,cfg_b,records[0]["receipt"]["request_id"])
                except Exception as exc:
                    assert getattr(exc,"sqlstate",None) == "42501"
                    cross = None
                assert cross is None
            with store.connect(worker_cfg) as c:
                try:
                    c.execute("SELECT * FROM ra4a.jobs").fetchall()
                except Exception as exc:
                    assert getattr(exc,"sqlstate",None) == "42501"
                else:
                    raise AssertionError("LOW_ROLE_RAW_TABLE_ACCESS")
        (native.OUT/"native-result.json").write_text(json.dumps(
            {"records":records,"native_python":sys.version.split()[0],"unauthorized_http":401,"cross_tenant_denied":True,
             "worker_raw_select_denied":True,"runtime_admin_credential":False},indent=2))
        (native.OUT/"ready.json").write_text('{"actual_api_worker_ready":true}')
        # Keep original API live for the owner-start session; no remote control endpoint.
        deadline = time.monotonic()+1800
        while not (native.OUT/"stop.json").exists() and time.monotonic()<deadline:
            restart=native.OUT/"api-restart.request.json"
            restarted=native.OUT/"api-restart.receipt.json"
            if restart.exists() and not restarted.exists():
                assert json.loads(restart.read_text())=={"action":"RESTART_OWN_ORIGINAL_API_ONCE"}
                native.signal_child(api,signal.SIGTERM)
                api.wait(timeout=5)
                api,new_log=native.spawn("APP",app_path)
                native.wait_for(lambda: new_log.exists() and b"READY" in new_log.read_bytes())
                pending=restarted.with_suffix(".tmp")
                pending.write_text(json.dumps({"original_api_restarted":True,"app_uid":10001,"new_admissions":0}))
                pending.replace(restarted)
            if api.poll() is not None:
                raise RuntimeError("API_EARLY_EXIT")
            time.sleep(0.2)
    finally:
        for child in reversed(native.CHILDREN):
            native.signal_child(child,signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except Exception:
                native.signal_child(child,signal.SIGKILL)
                child.wait(timeout=5)
        old.STATE.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
