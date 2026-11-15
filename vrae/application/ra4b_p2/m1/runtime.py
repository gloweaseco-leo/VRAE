"""Real low-role Collector/producer/atomic commit; synthetic transport only."""

import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import time

from vrae.application.ra4b import store
from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.http_transport import FetchResponse
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess
from ..producer import LeaseContext, CandidateDenied, capture_digest
from .producer import produce, replay


class RecordedDNS:
    async def resolve(self, host):
        # SafeFetcher still validates the IP. The transport opens NO socket.
        return ("93.184.216.20",)


class RecordedTransport:
    def __init__(self, source):
        self.routes = {}
        self.calls = []
        entry = source["pack"]["sources"][0]
        if len(source["pack"]["sources"]) != 1 or entry["kind"] != "CaptureManifest":
            raise CandidateDenied("M1_SINGLE_SYNTHETIC_CAPTURE_ONLY")
        for p in entry["document"]["pages"]:
            snap = p["snapshot"]
            body = b""
            if snap["private_object_ref"]:
                key = entry["object_refs"][snap["private_object_ref"]]
                body = base64.b64decode(source["objects_base64"][key], validate=True)
                if hashlib.sha256(body).hexdigest() != snap["sha256"]:
                    raise CandidateDenied("M1_RAW_SOURCE_SHA")
            if snap["url"] != snap["final_url"]:
                raise CandidateDenied("M1_REDIRECT_PROFILE_UNSUPPORTED")
            if p["http_status"] not in (200, 404, 410):
                raise CandidateDenied("M1_CAPTURE_STATUS_UNSUPPORTED")
            self.routes[snap["url"]] = (p["http_status"], {"content-type": "text/html"}, body)
        robots = entry["document"]["robots"]
        robots_body = b"User-agent: *\nDisallow:\n"
        if robots["status"] != 200 or hashlib.sha256(robots_body).hexdigest() != robots["sha256"]:
            raise CandidateDenied("M1_RECORDED_ROBOTS_REQUIRED")
        self.routes[robots["url"]] = (200, {"content-type": "text/plain"}, robots_body)

    async def exchange(self, url, method, ip, budget, max_bytes):
        if method != "GET" or url not in self.routes:
            raise CollectionError("SOURCE_NOT_ALLOWED")
        status, headers, body = self.routes[url]
        if len(body) > max_bytes:
            raise CollectionError("LIMIT_EXCEEDED")
        budget.consume(len(body))
        self.calls.append((url, method))
        return FetchResponse(url, status, headers, body, ip)


def load(c, tenant, lease):
    with c.transaction():
        cur = c.execute(
            "SELECT * FROM ra4b_p2.m1_load_source(%s,%s,%s,%s)",
            (tenant, lease[0], lease[2], lease[3]),
        )
        row = cur.fetchone()
        if row is None:
            raise CandidateDenied("M1_INPUT_UNAVAILABLE")
        return dict(zip([v.name for v in cur.description], row))


def build(row, lease):
    raw = json.loads(bytes(row["raw_source"]))
    transport = RecordedTransport(raw)
    policy = row["policy_document"]
    audit = dict(row["audit_document"])
    audit["audit_id"] = str(row["request_id"])
    access = SourceAccess(
        audit, lambda: policy, terms_reference="M1_AUTHORIZED_SYNTHETIC_RECORDED_TRANSPORT"
    )
    capture = asyncio.run(
        Collector(SafeFetcher(RecordedDNS(), transport)).capture(
            str(row["run_id"]),
            access,
            limits=Limits(max_pages=8, interval_seconds=0.01),
            retain_raw_html=True,
        )
    )
    if not transport.calls:
        raise CandidateDenied("M1_COLLECTOR_DID_NOT_RUN")
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
        capture_digest(capture),
        audit["source_policy_ref"],
        audit["source_policy_version"],
        hashlib.sha256(
            json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        row["loaded_at"].isoformat(),
    )
    return produce(capture, access, context, now=datetime.now(timezone.utc))


def commit(c, tenant, lease, output):
    from psycopg.pq import TransactionStatus

    if not c.autocommit or c.info.transaction_status != TransactionStatus.IDLE:
        raise CandidateDenied("M1_OUTER_COMMIT_REQUIRED")
    started = time.monotonic()
    replay(output)
    print(
        json.dumps({"stage": "M1_COMMIT_REPLAY_VERIFIED", "seconds": time.monotonic() - started}),
        flush=True,
    )
    sql_started = time.monotonic()
    with c.transaction():
        result = c.execute(
            "SELECT ra4b_p2.m1_commit(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                tenant,
                lease[0],
                lease[2],
                lease[3],
                output.source,
                output.report,
                output.html,
                output.binding,
            ),
        ).fetchone()[0]
    print(
        json.dumps({"stage": "M1_SQL_COMMITTED", "seconds": time.monotonic() - sql_started}),
        flush=True,
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = store.load_config(args.config, "WORKER")
    with store.connect(cfg) as c:
        lease = store.claim(c, cfg, 30)
        if lease is None:
            print(json.dumps({"status": "NO_LEGAL_PENDING_JOB"}), flush=True)
            return
        started = time.monotonic()
        output = build(load(c, cfg["tenant"], lease), lease)
        print(
            json.dumps({"stage": "M1_COLLECTOR_GENERATED", "seconds": time.monotonic() - started}),
            flush=True,
        )
        receipt = commit(c, cfg["tenant"], lease, output)
    # Hash/locator only, no raw report, source, binding or private lease token.
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
