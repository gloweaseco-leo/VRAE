"""Real disposable PG16/API/independent Worker. This is NOT full L2/browser E2E."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
import queue
import threading
from pathlib import Path
import secrets
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))



def main():
    from integration.beta_review.codex3.m3_application import GeneratedRun
    from integration.beta_review.codex3.runner import cmd, wait, write
    from integration.l2_ops.catalog import install
    from integration.l2_ops.source_profiles import PROFILES, selected
    from tests.identity.issuer import AUDIENCE, ISSUER, Issuer
    from vrae.application.ra4b_p2.m1.reader import JobAssignment

    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--minor", required=True, choices=("3.11", "3.13"))
    parser.add_argument("--source-profile", choices=tuple(PROFILES), default="industrial-v1")
    parser.add_argument("--native-l2", action="store_true")
    args = parser.parse_args()
    source_ref, bundle, native = selected(args.source_profile)
    if sys.version_info[:2] != tuple(map(int, args.minor.split("."))):
        parser.error("Actual native interpreter version mismatch")
    source_paths = ["vrae/l2_ops", "integration/l2_ops", "integration/beta_review/codex3/m3_native.py", "scripts/beta_internal.py", ".github/workflows/l2-ops.yml"]
    cmd(["git", "diff", "--exit-code", "HEAD", "--", *source_paths])
    run = GeneratedRun(args.label, args.minor)
    output = ROOT / "docs/03-engineering/l2-operations" / args.label
    output.mkdir(parents=True, exist_ok=False)
    proof = {"candidate_sha": run.result["source_sha"], "host_python": sys.version,
             "scope": "REAL_PG16_APP202_WORKER_EVIDENCE_NOT_COMPLETE_L2_E2E"}

    def probe(action, private):
        p = subprocess.run(["docker", "exec", "-i", "--user", "10003:10003", "--env", "VRAE_RA4B_TEST_ONLY=1",
            run.client_name, "python", "-B", "-m", "integration.l2_ops.worker_probe", action, "--source-profile", args.source_profile],
            input=json.dumps(private).encode(), cwd=ROOT, capture_output=True, timeout=60)
        if p.returncode:
            # Private traceback may contain connection data; never publish it.
            (run.folder / ("probe-" + action + ".stdout.private")).write_bytes(p.stdout)
            (run.folder / ("probe-" + action + ".stderr.private")).write_bytes(p.stderr)
            raise RuntimeError("L2_WORKER_PROBE_FAILED_SEE_PRIVATE_" + action.upper())
        value = json.loads(p.stdout)
        assert value["uid"] == 10003
        return value["result"]

    def current_native(private, issuer):
        # Original server-generated challenge is signed ONLY in this trusted
        # host fixture. UID10003 never receives an issuer private key.
        command = ["docker", "exec", "-i", "--user", "10003:10003", "--env", "VRAE_RA4B_TEST_ONLY=1",
            run.client_name, "python", "-B", "-m", "integration.l2_ops.worker_probe", "diagnose-current",
            "--source-profile", args.source_profile]
        p = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.stdin.write(json.dumps(private).encode() + b"\n")
        p.stdin.flush()
        lines = queue.Queue()
        thread = threading.Thread(target=lambda: lines.put(p.stdout.readline()), daemon=True)
        thread.start()
        try:
            challenge = json.loads(lines.get(timeout=25))
            assert challenge["uid"] == 10003 and set(challenge) == {"uid", "signing_nonce"}
            now = int(time.time())
            signed = {"bearer": issuer.token({"iat": now, "nbf": now, "exp": now + 120,
                                             "nonce": challenge["signing_nonce"]})}
            stdout, stderr = p.communicate(json.dumps(signed).encode() + b"\n", timeout=60)
            (run.folder / "current-native.stderr.private").write_bytes(stderr)
            assert p.returncode == 0, "L2_CURRENT_NATIVE_PROBE_FAILED_SEE_PRIVATE_STDERR"
            output = json.loads(stdout)
            assert output["uid"] == 10003
            return output["result"]
        finally:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=10)

    def junit():
        rows = run.cases
        suite = ET.Element("testsuite", name="l2-real-worker-intake", tests=str(len(rows)),
                           failures=str(sum(row["result"] != "PASS" for row in rows)), errors="0", skipped="0")
        ET.SubElement(ET.SubElement(suite, "properties"), "property",
                      name="candidate_sha", value=proof["candidate_sha"])
        for row in rows:
            case = ET.SubElement(suite, "testcase", classname="l2.actual_worker_intake",
                                 name=row["name"], time=str(row["seconds"]))
            if row["result"] != "PASS":
                ET.SubElement(case, "failure", message=row.get("error_type", "FAILED"))
        ET.ElementTree(suite).write(output / "worker-intake.xml", encoding="utf-8", xml_declaration=True)

    started = time.monotonic_ns()
    try:
        image = "vrae-ra4b-p1:" + args.minor.replace(".", "")
        owner = run.case("actual_restricted_linux_owner_write", lambda: cmd([
            "docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "CHOWN",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=32m",
            "--tmpfs", "/evidence:rw,nosuid,nodev,mode=755,size=32m",
            "--mount", "type=bind,src=" + str(ROOT) + ",dst=/work,readonly",
            image, "python", "-B", "-m", "integration.l2_ops.check_profile_owner"]))
        proof["private_profile_owner_check"] = json.loads(owner)
        run.case("pg16_original_migrations", run.start_pg)
        with run.r.lab.connect(dbname="vrae_ra4a_p1") as c:
            proof["pg_version_num"] = c.execute("SHOW server_version_num").fetchone()[0]
            assert 160000 <= int(proof["pg_version_num"]) < 170000
        proof["input"] = run.case("independent_synthetic_input_not_seeded_result", lambda: install(run.r.lab, native, source_ref=source_ref))
        run.r.lab.state["l2_source_refs"] = [source_ref]
        run.r.lab.state["l2_source_binding"] = {"sha256": proof["input"]["reference_sha256"],
                                              "policy_id": "pol-001", "policy_version": 1}
        if os.name == "posix":
            run.r.lab.state["l2_evidence_owner"] = {"uid": os.getuid(), "gid": os.getgid()}
        run.r.lab.save()
        run.case("original_api_independent_worker", run.start_native)
        proof["native_python"] = run.result["native_python"]
        proof["worker_image_id"] = run.result["runtime_image_id"]
        created = run.case("real_app202", lambda: probe("create", {"key": "l2-industrial-native-0001"}))
        task = created["task"]
        proof["actual_app202_task"] = task
        write(run.folder / "actual-app202-task.private.json", task)
        assert created["http_status"] == 202 and task["source_ref"] == source_ref
        before = probe("status", {"task": task})
        assert before["job_state"] == "PENDING"
        wake = run.native_out / "l2-industrial.wake.json"
        write(wake, {"process_one": True})
        wake.chmod(0o644)  # Nonsecret control; parent mount denies other UIDs.
        observed = []

        def done():
            assert run.client.poll() is None, "L2_NATIVE_PROCESS_EXIT"
            status = probe("status", {"task": task})
            observed.append(status["job_state"])
            return status["job_state"] == "TEST_ONLY_DONE"

        run.case("actual_worker_commit", lambda: wait(done, 90))
        cfg = json.loads((run.folder / "m3-reviewer.private.json").read_bytes())
        cfg["port"] = 5432
        issuer, now = Issuer(), int(time.time())
        nonce = secrets.token_urlsafe(24)
        private = {"task": task, "reviewer": cfg,
            "anchor": {"issuer": ISSUER, "audience": AUDIENCE, "jwks": json.loads(issuer.jwks()), "expires": now + 180},
            "assignment": asdict(JobAssignment(ISSUER, "synthetic-reviewer-1", cfg["role"], "tenant-test", task["job_id"], now + 180)),
            "bearer": issuer.token({"iat": now, "nbf": now, "exp": now + 120, "nonce": nonce}), "nonce": nonce}
        proof["evidence"] = run.case("actual_signed_low_role_read", lambda: probe("read", private))
        assert proof["evidence"]["snapshot_count"] == 8 and not proof["evidence"]["l2_complete"]
        if args.native_l2:
            private["policy_expires_at"] = proof["input"]["policy_expires_at"]
            proof["native_diagnosis"] = run.case("actual_same_worker_native_l2_under_original_authority",
                lambda: current_native(private, issuer))
            deep = proof["native_diagnosis"]
            assert deep["task"] == task and deep["worker_pack_ref"] == proof["evidence"]["worker_pack_ref"]
            if args.source_profile == "industrial-p40-v3":
                assert deep["assessment_count"] == 19 and deep["models"] == ["P40", "V25"]
        proof["observed_states"] = [before["job_state"], *observed]
        proof["automated_wall_ns"] = time.monotonic_ns() - started
        proof["cost_status"] = "UNKNOWN"
        cmd(["git", "diff", "--exit-code", "HEAD", "--", *source_paths])
        assert cmd(["git", "rev-parse", "HEAD"]).decode().strip() == proof["candidate_sha"]
        proof["status"] = "PASS_NATIVE_DIAGNOSIS_REPORT_PENDING" if args.native_l2 else "PASS_WORKER_INTAKE_ONLY"
    except BaseException:
        proof["status"] = "RED_PRESERVED"
        raise
    finally:
        try:
            run.case("owned_cleanup", run.cleanup)
        finally:
            proof["cases"] = run.cases
            proof["cleanup"] = run.result.get("cleanup")
            proof["cleanup_errors"] = run.result.get("cleanup_errors")
            if proof["cleanup_errors"] or any(row["result"] != "PASS" for row in run.cases):
                proof["status"] = "RED_PRESERVED"
            proof["source_manifest_sha256"] = hashlib.sha256((run.public / "source-manifest.json").read_bytes()).hexdigest()
            (output / "source-manifest.json").write_bytes((run.public / "source-manifest.json").read_bytes())
            if hasattr(run, "native_out") and (run.native_out / "m1-worker.log").is_file():
                proof["private_worker_log_sha256"] = hashlib.sha256((run.native_out / "m1-worker.log").read_bytes()).hexdigest()
            if hasattr(run, "native_out"):
                owner_file = run.native_out / "evidence-owner.json"
                if owner_file.is_file():
                    proof["actual_evidence_mount"] = json.loads(owner_file.read_bytes())
                supervisor_log = run.native_out / "native-supervisor.log"
                if supervisor_log.is_file():
                    proof["private_supervisor_log_sha256"] = hashlib.sha256(supervisor_log.read_bytes()).hexdigest()
            junit()
            proof["junit_sha256"] = hashlib.sha256((output / "worker-intake.xml").read_bytes()).hexdigest()
            write(output / "worker-intake.json", proof)
    print(json.dumps(proof), flush=True)


if __name__ == "__main__":
    main()
