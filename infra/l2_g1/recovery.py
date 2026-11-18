"""Actual owned PG16/service restart and current same-task HTTP recovery."""

import hashlib
import json
import subprocess
import time

SOCKET = "/evidence/.private-root/owner.sock"


def execute(docker, names, private, public):
    from contracts.l2_launch.contract import validate

    ownership = json.loads((public / "ownership.json").read_text(encoding="utf8"))
    for name in (names["pg"], names["runtime"]):
        actual = json.loads(docker("inspect", "--format", "{{json .Config.Labels}}", name))
        assert all(actual.get(k) == v for k, v in ownership["label"].items())
    checks = []
    events = []

    def write():
        (public / "recovery.json").write_text(
            json.dumps(
                {
                    "scope": "REAL_PG_SERVICE_SESSION_RECOVERY_NOT_G1_FINAL_PASS",
                    "checks": checks,
                    "events": events,
                },
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf8",
        )

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        write()
        print(json.dumps({"recovery_check": name, "status": "PASS"}), flush=True)

    def call(op, ref=None):
        args = (
            "exec",
            "-u",
            "0",
            names["runtime"],
            "python",
            "-m",
            "integration.l2_launch.g1.owner_cli",
            op,
        )
        raw = docker(*args, *([ref] if ref else []))
        document = json.loads(raw)
        (private / ("recovery-" + str(len(events)) + "-" + op + ".json")).write_bytes(raw)
        if "error" in document:
            raise AssertionError("CONTROLLED_OWNER_OPERATION_" + op + "_" + document["error"])
        result = document["result"]
        event = {"operation": op, "response_sha256": hashlib.sha256(raw).hexdigest()}
        if "http_status" in result:
            event["http_status"] = result["http_status"]
        if op in ("new", "retry"):
            event["accepted"] = result["body"]
        if op == "status":
            event["status"] = result["body"]
        if op == "preview":
            event["report_pins"] = result.get("pins")
            event["formal_human_review"] = result.get("formal_human_review")
        if op == "custody":
            event["original_custody"] = result
        events.append(event)
        write()
        return result

    end = time.monotonic() + 600
    while True:
        ready = subprocess.run(
            ["docker", "exec", names["runtime"], "test", "-S", SOCKET],
            capture_output=True,
            timeout=5,
        )
        if ready.returncode == 0:
            break
        if time.monotonic() > end:
            raise AssertionError("RECOVERY_CONTROL_NOT_READY")
        time.sleep(0.3)
    fresh = call("new", "manufacturer")
    check("RECOVERY_NEW_NATIVE_TASK_HTTP202", fresh["http_status"] == 202)
    ref = fresh["body"]["audit_ref"]
    accepted = fresh["body"]
    try:
        check("RECOVERY_ORIGINAL_WORKER_COMMIT", call("work")["worker_exit"] == 0)
        before_custody = call("custody", ref)
        check("RECOVERY_SINGLE_ORIGINAL_RESULT", before_custody["original_result_rows"] == 1)
        before = call("preview", ref)
        check(
            "RECOVERY_ORIGINAL_REPORT_PREVIEW",
            before["http_status"] == 200 and before["formal_human_review"] is False,
        )
        replay = call("replay", ref)
        check(
            "RETURN_REPLAY_WITH_FRESH_CHALLENGE_HTTP403",
            replay["http_status"] == 403 and replay["fresh_challenge"] is True,
        )
        call("deny", ref)
        check("CURRENT_RETURN_REVOCATION_HTTP403", call("status", ref)["http_status"] == 403)
        call("allow", ref)
        check("OWNER_CONTROLLED_RETURN_RESTORED", call("status", ref)["http_status"] == 200)
        call("expire", ref)
        check("EXPIRED_COOKIE_AUTHORITY_HTTP403", call("status", ref)["http_status"] == 403)
        call("allow", ref)
        check("OWNER_CONTROLLED_EXPIRY_RESTORED", call("status", ref)["http_status"] == 200)
        call("service-down")
        unavailable = call("status", ref)
        validate("VFSafeError", unavailable["body"])
        check("ACTUAL_FACADE_DOWN_SAFE_HTTP503", unavailable["http_status"] == 503)
        call("service-up")
        check("FACADE_RESTART_PRESERVES_CURRENT_SESSION", call("status", ref)["http_status"] == 200)
        query = "SELECT pg_postmaster_start_time(),system_identifier FROM pg_control_system()"

        def pg_identity():
            return (
                docker(
                    "exec",
                    "-u",
                    "postgres",
                    names["pg"],
                    "psql",
                    "-d",
                    "vrae_ra4a_p1",
                    "-At",
                    "-c",
                    query,
                )
                .decode()
                .strip()
                .split("|")
            )

        pg_before = pg_identity()
        docker(
            "exec",
            "-u",
            "postgres",
            names["pg"],
            "pg_ctl",
            "-D",
            "/var/lib/postgresql/data",
            "stop",
            "-m",
            "fast",
            "-w",
            "-t",
            "20",
        )
        pg_unavailable = call("status", ref)
        validate("VFSafeError", pg_unavailable["body"])
        check("ACTUAL_PG_STOP_SAFE_HTTP503", pg_unavailable["http_status"] == 503)
        docker(
            "exec",
            "-u",
            "postgres",
            names["pg"],
            "pg_ctl",
            "-D",
            "/var/lib/postgresql/data",
            "start",
            "-l",
            "/var/lib/postgresql/data/g1-restart.log",
            "-w",
            "-t",
            "30",
        )
        pg_after = pg_identity()
        check(
            "NEW_REAL_PG_PROCESS_SAME_CLUSTER",
            pg_before[0] != pg_after[0] and pg_before[1] == pg_after[1],
        )
        events.append(
            {
                "original_pg_start": pg_before[0],
                "new_pg_start": pg_after[0],
                "same_original_cluster_identifier": pg_after[1],
            }
        )
        write()
        retry = call("retry", ref)
        check(
            "PG_RESTART_SAME_KEY_SAME202_SAME_NATIVE_RUN",
            retry["http_status"] == 202 and retry["body"] == accepted,
        )
        after_status = call("status", ref)
        check(
            "PG_RESTART_SESSION_TASK_CURRENT_UNPUBLISHED",
            after_status["http_status"] == 200
            and after_status["body"]["task"]["run_id"] == accepted["run_id"]
            and after_status["body"]["publication"]["state"] == "UNPUBLISHED",
        )
        after = call("preview", ref)
        check(
            "PG_AND_SERVICE_RESTART_REPORT_PINS_IDENTICAL",
            after["http_status"] == 200 and before["pins"] == after["pins"],
        )
        after_custody = call("custody", ref)
        check("SAME_ORIGINAL_COMMIT_NO_DUPLICATE_RESULT", before_custody == after_custody)
    finally:
        call("stop")
