"""Independent low-role G1 entry: original claim/load/produce/commit, R1A capture.

No alternative queue, report engine, lease renewal or live transport exists here.
"""

import argparse
import base64
from datetime import datetime, UTC
import hashlib
import json
import time

from vrae.application.ra4b import store
from vrae.application.ra4b_p2.producer import LeaseContext, capture_digest, CandidateDenied
from vrae.application.ra4b_p2.m1.runtime import load, commit
from vrae.application.ra4b_p2.m1.producer import produce
from integration.l2_launch.g1.sources import capture


def recorded_input(row, kind):
    """Decode the original PG-authorized source; no network miss or old bundle."""
    raw = json.loads(bytes(row["raw_source"]))
    sources = raw["pack"]["sources"]
    if len(sources) != 1 or sources[0]["kind"] != "CaptureManifest":
        raise CandidateDenied("G1_SOURCE_TEMPLATE_REQUIRED")
    entry = sources[0]
    expected_origin = "https://g1-" + kind + ".example"
    recorded = {}
    for page in entry["document"]["pages"]:
        snap = page["snapshot"]
        if not snap["url"].startswith(expected_origin + "/") or snap["final_url"] not in (
            None,
            snap["url"],
        ):
            raise CandidateDenied("G1_SOURCE_SCOPE")
        if page["http_status"] is None:
            continue
        body = b""
        if snap["private_object_ref"]:
            key = entry["object_refs"][snap["private_object_ref"]]
            body = base64.b64decode(raw["objects_base64"][key], validate=True)
            if hashlib.sha256(body).hexdigest() != snap["sha256"]:
                raise CandidateDenied("G1_SOURCE_BYTES")
        if page["http_status"] not in (200, 403, 404, 410, 429):
            raise CandidateDenied("G1_SOURCE_STATUS")
        recorded[snap["url"]] = (page["http_status"], {"content-type": "text/html"}, body)
    robots = entry["document"]["robots"]
    robot_options = [b"User-agent: *\nDisallow:\n", b"User-agent: *\nDisallow: /\n"]
    body = next(
        (body for body in robot_options if hashlib.sha256(body).hexdigest() == robots["sha256"]),
        None,
    )
    if body is None and kind != "unknown":
        raise CandidateDenied("G1_RECORDED_ROBOTS_REQUIRED")
    recorded[expected_origin + "/robots.txt"] = (200, {"content-type": "text/plain"}, body or b"")
    return recorded


def build(row, lease):
    kind = row["source_ref"].removeprefix("g1-recorded-")
    policy = row["policy_document"]
    audit = dict(row["audit_document"])
    audit.update(request_id=str(row["request_id"]), audit_id=str(row["request_id"]))
    remaining = (row["lease_until"] - datetime.now(UTC)).total_seconds() - 3
    if remaining < 0.1:
        raise CandidateDenied("G1_LEASE_BUDGET_EXHAUSTED")
    captured, access, trace = capture(
        kind,
        policy,
        audit,
        str(row["run_id"]),
        recorded=recorded_input(row, kind),
        task_seconds=min(10, remaining),
    )
    context = LeaseContext(
        row["tenant_id"],
        str(row["request_id"]),
        str(row["run_id"]),
        str(row["job_id"]),
        row["worker_role"],
        str(lease[2]),
        lease[3],
        row["lease_until"].isoformat(),
        row["origin_epoch"],
        row["source_ref"],
        row["reference_sha256"],
        capture_digest(captured),
        audit["source_policy_ref"],
        audit["source_policy_version"],
        hashlib.sha256(
            json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        row["loaded_at"].isoformat(),
    )
    output = produce(captured, access, context, now=datetime.now(UTC))
    print(
        json.dumps(
            {
                "stage": "G1_R1A_CAPTURE_TO_ORIGINAL_M1_PRODUCER",
                "run_id": context.run_id,
                "job_id": context.job_id,
                "capture_digest": context.input_sha256,
                **trace,
            }
        ),
        flush=True,
    )
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = store.load_config(args.config, "WORKER")
    with store.connect(cfg) as c:
        lease = store.claim(c, cfg, 30)
        if lease is None:
            print('{"status":"NO_LEGAL_PENDING_JOB"}', flush=True)
            return
        started = time.monotonic()
        output = build(load(c, cfg["tenant"], lease), lease)
        receipt = commit(c, cfg["tenant"], lease, output)
    print(
        json.dumps(
            {"stage": "G1_ORIGINAL_M1_COMMITTED", "seconds": time.monotonic() - started, **receipt}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
