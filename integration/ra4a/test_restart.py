"""Real process restart on an owned PG data volume, not simulated recovery."""

import json
import os
from pathlib import Path
import subprocess
import time

from .support import connect, STATE
from .test_pg import client


def test_committed_queue_lease_and_idempotency_survive_real_container_restart(db):
    s = json.loads(STATE.read_text())
    assert s["data_volume"] == s["container"] + "-data"
    with client() as a:
        admitted = a.admit("tenant-test", "restart-proof-001")
    with client("ra4a_test_a_worker") as worker:
        old = worker.claim("tenant-test", seconds=1)
    subprocess.run(["docker", "restart", s["container"]], capture_output=True, check=True)
    for _ in range(80):
        p = subprocess.run(
            ["docker", "exec", s["container"], "pg_isready", "-U", "postgres", "-d", s["dbname"]],
            capture_output=True,
        )
        if p.returncode == 0:
            break
        time.sleep(0.25)
    else:
        raise AssertionError("REAL_PG_RESTART_BLOCKED")
    port = subprocess.check_output(["docker", "port", s["container"], "5432/tcp"]).decode().strip()
    s["port"] = int(port.rsplit(":", 1)[1])
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")
    with client() as a:
        assert a.admit("tenant-test", "restart-proof-001") == admitted
    time.sleep(1.1)
    with client("ra4a_test_a_worker") as w:
        new = w.claim("tenant-test", seconds=5)
        assert new[0] == old[0] and new[3] == old[3] + 1 and new[2] != old[2]
        assert w.finish("tenant-test", new[0], new[2], new[3])
    with connect() as c:
        assert c.execute("SELECT count(*) FROM ra4a.requests").fetchone() == (1,)
        settings = {
            name: c.execute("SHOW " + name).fetchone()[0]
            for name in ("fsync", "synchronous_commit", "full_page_writes")
        }
        assert all(v == "on" for v in settings.values())
    output = Path(os.environ["RA4A_EVIDENCE_DIR"])
    (output / "real-restart.json").write_text(
        json.dumps(
            {
                "container": s["container"],
                "own_data_volume": s["data_volume"],
                "settings": settings,
                "committed_ids_preserved": True,
                "expired_lease_reclaimed_with_new_token": True,
                "no_duplicate_admission": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
