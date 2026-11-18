"""Private callable adapter proposal. No HTTP listener or new queue/report engine."""

from dataclasses import asdict, dataclass
import time
import math

from vrae.application.ra4b_p2.m1.consumer import ConsumerDenied, TaskClient, TaskHandle

CANDIDATE = "R1B_PRIVATE_RUNTIME_CANDIDATE_DEPLOYMENT_GO_PENDING"


class Denied(ValueError):
    def __init__(self, code, status=403):
        self.code, self.status = code, status
        super().__init__(code)


@dataclass(frozen=True)
class LocalPolicy:
    tenant: str
    expires: float
    mode: str = "OFFLINE_SYNTHETIC"
    bind: str = "127.0.0.1"
    model: str = "NO_MODEL"
    public: bool = False

    def require(self, tenant):
        if (
            self.tenant not in ("tenant-test", "tenant-beta")
            or tenant != self.tenant
            or self.mode != "OFFLINE_SYNTHETIC"
            or self.bind != "127.0.0.1"
            or self.model != "NO_MODEL"
            or self.public is not False
            or type(self.expires) not in (int, float)
            or not math.isfinite(self.expires)
            or time.time() >= self.expires
        ):
            raise Denied("PRIVATE_SYNTHETIC_AUTHORITY_REQUIRED")


class PrivateAdapter:
    """Original APP credential and PG are authoritative. Routing hints are not grants."""

    def __init__(self, client, policy):
        if type(client) is not TaskClient or type(policy) is not LocalPolicy:
            raise Denied("ORIGINAL_CLIENT_REQUIRED")
        policy.require(client.endpoint.tenant_id)
        self.client, self.policy = client, policy

    def submit(self, tenant, body, key):
        self.policy.require(tenant)
        if type(body) is not dict or set(body) != {"source_ref"}:
            raise Denied("SERVER_REGISTERED_SOURCE_ONLY")
        try:
            task = self.client.create(body["source_ref"], idempotency_key=key)
        except ConsumerDenied:
            raise Denied("ORIGINAL_ADMISSION_REFUSED") from None
        return (
            202,
            {
                "schema_version": "1.0",
                "tenant_id": tenant,
                "request_id": task.request_id,
                "audit_id": task.request_id,
                "status": "CREATED",
            },
            task,
        )

    def status(self, tenant, task):
        self.policy.require(tenant)
        if type(task) is not TaskHandle or task.tenant_id != tenant:
            raise Denied("TASK_SCOPE_DENIED")
        try:
            row = self.client.status(task)
        except ConsumerDenied:
            raise Denied("ORIGINAL_CURRENT_STATUS_DENIED") from None
        native = row["job_state"]
        # A lease or DONE alone does not prove collection or a readable report.
        mapped = "FAILED" if native == "DEAD_LETTER" else "QUEUED"
        return {
            "schema_version": "1.0",
            "tenant_id": tenant,
            "audit_id": task.request_id,
            "run_id": task.run_id,
            "request_id": task.request_id,
            "status": mapped,
            "native_job_state": native,
            "attempt": row["attempts"],
            "progress_percent": None,
            "report_available": False,
            "next_required": "CURRENT_SIGNED_EVIDENCE_AND_REPORT_VERIFICATION",
            "contract": "PRIVATE_ADAPTER_PROPOSAL_NOT_V1_AUDITRUN_RESPONSE",
        }

    def cancel(self, tenant, task):
        self.policy.require(tenant)
        self.client.status(task)
        raise Denied("CANCEL_NOT_IMPLEMENTED", 501)

    def approved_report(self, tenant, task):
        self.policy.require(tenant)
        self.client.status(task)
        raise Denied("REAL_REVIEW_SHARE_AND_G0_REQUIRED")

    def routing_hint(self, task):
        self.status(self.policy.tenant, task)
        return asdict(task)
