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
    print(
        json.dumps({"worker_phase": "LEASE_HELD", "job_id": str(job), "lease_seq": seq}), flush=True
    )
    loaded = port.call("load", *args)
    task = loaded["task"]
    plan = loaded["plan"]
    request = dict(loaded["submission"]["command"]["request"])
    request.update(request_id=task["request_id"], audit_id=task["request_id"])

    checks = {'calls': 0, 'seconds': 0.0}

    def current():
        started_check = time.monotonic()
        try:
            return port.call('load', *args)
        finally:
            checks['calls'] += 1
            checks['seconds'] += time.monotonic() - started_check

    def current_policy():
        return current()["plan"]["policy"]

    # The original 30s lease also covers rule/Guard replay and atomic commit.
    # Automatic captures must stop early enough to preserve acquired evidence.
    reserve = 12 if plan.get('automatic_result') else 3
    remaining = (until - datetime.now(UTC)).total_seconds() - reserve
    if remaining < 1:
        raise ValueError("ORIGINAL_LEASE_BUDGET_EXHAUSTED")
    bounded = {
        **workload,
        "deadline": (until - timedelta(seconds=reserve)).isoformat(),
        "task_seconds": remaining,
    }
    print(json.dumps({'worker_phase': 'LEASE_BUDGET', 'capture_seconds': remaining,
                      'finish_reserve_seconds': reserve}), flush=True)
    started = time.monotonic()
    try:
        captured = capture(request, current_policy, plan, task['run_id'], bounded, current=current)
    finally:
        print(json.dumps({'worker_phase': 'CAPTURE_AUTHORITY_CHECKS', **checks}), flush=True)
    print(
        json.dumps(
            {
                "worker_phase": "CAPTURE_RETURNED",
                "job_id": str(job),
                "seconds": time.monotonic() - started,
            }
        ),
        flush=True,
    )
    output = produce_capture(
        captured, task, plan["policy"]["authorization_reference"], loaded["loaded_at"],
        diagnostic_version="l2-industrial-1.0.7" if plan.get('automatic_result') else "l2-industrial-1.0.1"
    )
    if plan.get("execution_profile") == "ADMIN_TARGET_V2":
        output["source_authority"] = {
            "authorization": loaded["source_authorization"],
            "plan_sha256": loaded["plan_sha256"],
            "retention_until": loaded["source_authorization"]["document"]["retention_until"],
        }
    print(
        json.dumps(
            {
                "worker_phase": "DRAFT_PRODUCED",
                "job_id": str(job),
                "seconds": time.monotonic() - started,
            }
        ),
        flush=True,
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
    interval = cfg.get("poll_interval_seconds")
    if interval is not None and (type(interval) not in (int, float) or not 0.1 <= interval <= 30):
        raise ValueError("BOUNDED_POLL_INTERVAL_REQUIRED")
    while True:
        for binding in cfg["bindings"]:
            port = None
            try:
                port = store.WorkerPort(binding)
                while True:
                    receipt = run(binding, cfg["workload"], port)
                    if not receipt["claimed"]:
                        break
                    print(json.dumps(receipt), flush=True)
            except Exception:
                if interval is None:
                    raise
                print('{"worker_state":"DEPENDENCY_UNAVAILABLE","retryable":true}', flush=True)
            finally:
                if port is not None:
                    port.close()
        if interval is None:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
