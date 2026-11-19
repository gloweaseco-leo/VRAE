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
    plan = dict(plan)
    plan["limits"] = dict(plan["limits"])
    plan["limits"]["task_seconds"] = min(plan["limits"]["task_seconds"], remaining)
    bounded = {**workload, "deadline": (until - timedelta(seconds=3)).isoformat()}
    started = time.monotonic()
    captured = capture(request, current_policy, plan, task["run_id"], bounded)
    output = produce_capture(
        captured, task, plan["policy"]["authorization_reference"], loaded["loaded_at"]
    )
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
