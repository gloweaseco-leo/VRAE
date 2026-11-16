"""Real disposable PG16/API/independent Worker. This is NOT full L2/browser E2E."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))



def main():
    from integration.beta_review.codex3.m3_application import GeneratedRun
    from integration.beta_review.codex3.runner import cmd, wait, write
    from integration.l2_ops.catalog import SOURCE_REF, install
    from tests.identity.issuer import AUDIENCE, ISSUER, Issuer
    from vrae.application.ra4b_p2.m1.reader import JobAssignment
    from vrae.l2_ops.ingest import load_source
    from vrae.l2_ops.native_input import load_native

    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--minor", required=True, choices=("3.11", "3.13"))
    args = parser.parse_args()
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
            run.client_name, "python", "-B", "-m", "integration.l2_ops.worker_probe", action],
            input=json.dumps(private).encode(), cwd=ROOT, capture_output=True, timeout=60)
        if p.returncode:
            # Private traceback may contain connection data; never publish it.
            (run.folder / ("probe-" + action + ".stdout.private")).write_bytes(p.stdout)
            (run.folder / ("probe-" + action + ".stderr.private")).write_bytes(p.stderr)
            raise RuntimeError("L2_WORKER_PROBE_FAILED_SEE_PRIVATE_" + action.upper())
        value = json.loads(p.stdout)
        assert value["uid"] == 10003
        return value["result"]

    started = time.monotonic_ns()
    try:
        image = "vrae-ra4b-p1:" + args.minor.replace(".", "")
        owner = run.case("actual_restricted_linux_owner_write", lambda: cmd([
            "docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "CHOWN",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=32m",
            "--mount", "type=bind,src=" + str(ROOT) + ",dst=/work,readonly",
            image, "python", "-B", "-m", "integration.l2_ops.check_profile_owner"]))
        proof["private_profile_owner_check"] = json.loads(owner)
        run.case("pg16_original_migrations", run.start_pg)
        bundle = load_source(ROOT / "integration/l2_ops/fixtures/native-offline_synthetic.json")
        native = load_native(bundle, "industrial-native",
            expected_pack_ref="ep-735db2c276030e018f21ba7124fb61db6d46f3e922eca1b99df254512064582e",
            expected_capture_run_id="l2-industrial-capture-v1")
        proof["input"] = run.case("independent_synthetic_input_not_seeded_result", lambda: install(run.r.lab, native))
        run.r.lab.state["l2_source_refs"] = [SOURCE_REF]
        run.r.lab.state["l2_source_binding"] = {"sha256": proof["input"]["reference_sha256"],
                                              "policy_id": "pol-001", "policy_version": 1}
        run.r.lab.save()
        run.case("original_api_independent_worker", run.start_native)
        created = run.case("real_app202", lambda: probe("create", {"key": "l2-industrial-native-0001"}))
        task = created["task"]
        assert created["http_status"] == 202 and task["source_ref"] == SOURCE_REF
        before = probe("status", {"task": task})
        assert before["job_state"] == "PENDING"
        write(run.native_out / "l2-industrial.wake.json", {"process_one": True})
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
        proof["observed_states"] = [before["job_state"], *observed]
        proof["automated_wall_ns"] = time.monotonic_ns() - started
        proof["cost_status"] = "UNKNOWN"
        cmd(["git", "diff", "--exit-code", "HEAD", "--", *source_paths])
        assert cmd(["git", "rev-parse", "HEAD"]).decode().strip() == proof["candidate_sha"]
        proof["status"] = "PASS_WORKER_INTAKE_ONLY"
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
            proof["source_manifest_sha256"] = hashlib.sha256((run.public / "source-manifest.json").read_bytes()).hexdigest()
            write(output / "worker-intake.json", proof)
    print(json.dumps(proof), flush=True)


if __name__ == "__main__":
    main()
