"""Actual bounded read-only transport. No recording or implicit live fallback."""

import asyncio
import json
from datetime import datetime

from integration.l2_launch.security.adapter import (
    TaskPins,
    OfflinePermit,
    isolated_fetcher,
    fingerprint,
)
from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess


def components(audit, policy_provider, plan, run_id, workload, current=None):
    if plan.get("execution_profile") == "ADMIN_TARGET_V2":
        from integration.authorized_targets.egress import components as authorized

        return authorized(audit, policy_provider, plan, run_id, workload, current)
    policy = policy_provider()
    source = SourceAccess(audit, policy_provider, terms_reference=plan["terms_reference"])
    held = TaskPins(
        audit["tenant_id"],
        audit["request_id"],
        run_id,
        policy["policy_id"],
        policy["policy_version"],
        fingerprint(policy),
    )
    permit = OfflinePermit(
        plan["origin"],
        tuple(plan["exact_paths"]),
        datetime.fromisoformat(policy["created_at"]),
        min(
            datetime.fromisoformat(policy["expires_at"]),
            datetime.fromisoformat(workload["deadline"]),
        ),
        plan["retain_raw_html"],
    )
    if workload["kind"] == "CONTROLLED_NON_CUSTOMER":
        if plan["authorization_kind"] != "CONTROLLED_NON_CUSTOMER":
            raise CollectionError("SOURCE_NOT_ALLOWED")
        # This exact accepted factory uses REAL DNS/TCP/TLS in the owned,
        # firewall-denied namespace. It is not RecordedTransport.
        return isolated_fetcher(
            source,
            held=held,
            permit=permit,
            nameservers=["93.184.216.53"],
            cafile="/tmp/lab/cert.pem",
        )
    # Customer deployment and per-target legal issuance are deliberately not
    # implemented by self-asserted config flags. A separate reviewed attestation
    # adapter is required before this branch can make any connection.
    raise PermissionError("LIVE_CAPTURE_DISABLED")


def capture(audit, policy_provider, plan, run_id, workload, current=None):
    access, fetcher = components(audit, policy_provider, plan, run_id, workload, current)
    configured = dict(plan["limits"])
    configured["task_seconds"] = min(
        configured["task_seconds"], workload.get("task_seconds", configured["task_seconds"])
    )
    limits = Limits(**configured)
    result = asyncio.run(
        Collector(fetcher, observer=lambda event: print(json.dumps(event), flush=True)).capture(
            run_id, access, limits=limits, retain_raw_html=plan["retain_raw_html"]
        )
    )
    result.verify()
    return result
