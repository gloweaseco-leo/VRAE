"""Versioned original-queue Worker: original30s claim, real Collector, NativeSource."""

import argparse
from datetime import datetime, UTC, timedelta
import json
import time
from contracts.l2_launch.contract import canonical
from integration.authorized_targets import store
from integration.authorized_targets.capture import capture
from integration.authorized_targets.producer import produce_capture


def run(binding, workload, port):
    lease = port.claim()
    if lease is None:
        return {"claimed": False}
    try:
        return execute(binding, workload, port, lease)
    except Exception as error:
        if workload.get("kind") != "AUTHORIZED_EGRESS_V2":
            raise
        job, run, token, seq, until = lease
        try:
            port.call("capture_failure", binding["tenant_id"], job, token, seq, "CAPTURE_FAILED")
        except Exception:
            pass  # A lost/expired lease cannot write an audit either.
        return {
            "claimed": True,
            "job_id": str(job),
            "run_id": str(run),
            "capture_failed": True,
            "failure_type": type(error).__name__,
            "safe_code": "CAPTURE_FAILED",
            "publication": "UNPUBLISHED",
        }


def execute(binding, workload, port, lease):
    job, run, token, seq, until = lease
    args = (binding["tenant_id"], job, token, seq)
    loaded = port.call("load", *args)
    task = loaded["task"]
    plan = loaded["plan"]
    request = dict(loaded["submission"]["command"]["request"])
    request.update(request_id=task["request_id"], audit_id=task["request_id"])

    def current_policy():
        return port.call("load", *args)["plan"]["policy"]

    remaining = (until - datetime.now(UTC)).total_seconds() - 3
    if remaining < 1:
        raise ValueError("ORIGINAL_LEASE_BUDGET_EXHAUSTED")
    bounded = {
        **workload,
        "deadline": (until - timedelta(seconds=3)).isoformat(),
        "task_seconds": remaining,
    }
    started = time.monotonic()
    captured = capture(
        request,
        current_policy,
        plan,
        task["run_id"],
        bounded,
        current=lambda: port.call("load", *args),
    )
    output = produce_capture(
        captured, task, plan["policy"]["authorization_reference"], loaded["loaded_at"]
    )
    if plan.get("execution_profile") == "ADMIN_TARGET_V2":
        output["source_authority"] = {
            "authorization": loaded["source_authorization"],
            "plan_sha256": loaded["plan_sha256"],
            "retention_until": loaded["source_authorization"]["document"]["retention_until"],
        }
    digest = port.call("commit", *args, canonical(output))
    return {
        "claimed": True,
        "task": task,
        "artifact_sha256": digest,
        "pack_ref": output["pack_ref"],
        "capture_errors": captured.manifest["errors"],
        "page_states": [p["snapshot"]["status"] for p in captured.manifest["pages"]],
        "source_fact_count": len(output["diagnosis"]["source_facts"]),
        "findings": len(output["native_document"]["findings"]),
        "blueprint_packages": len(output["native_document"]["blueprint"]),
        "seconds": time.monotonic() - started,
        "transport": "ORIGINAL_PINNED_REAL_DNS_TCP_TLS",
        "publication": "UNPUBLISHED",
        "ai_state": "NO_MODEL",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = store.config(args.config, "WORKER")
    for binding in cfg["bindings"]:
        port = store.WorkerPort(binding)
        try:
            while True:
                receipt = run(binding, cfg["workload"], port)
                if not receipt["claimed"]:
                    break
                print(json.dumps(receipt), flush=True)
        finally:
            port.close()


if __name__ == "__main__":
    main()
