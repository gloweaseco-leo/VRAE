"""Private server-to-server M1 adapter. No APP database connection/configuration.

The operator provisions the HTTP bearer, source allowlist and signed reader.
Task handles are server-held routing hints, never a grant of Reviewer authority.
"""

from dataclasses import dataclass, field
import http.client
import json
from uuid import UUID


AUTHORITY = "TEST_ONLY_PRIVATE_RUNTIME_NOT_HUMAN_APPROVAL"


class ConsumerDenied(ValueError):
    def __init__(self):
        super().__init__("M1_CONSUMER_DENIED")


def identifier(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ConsumerDenied()
    return value


@dataclass(frozen=True)
class TaskHandle:
    tenant_id: str
    source_ref: str
    request_id: str
    run_id: str
    job_id: str
    event_id: str


@dataclass(frozen=True)
class AppEndpoint:
    """Provision separately from the APP DB config; fixed loopback endpoint."""

    bearer: str = field(repr=False)
    tenant_id: str
    source_refs: frozenset[str]

    def __post_init__(self):
        if (
            type(self.bearer) is not str
            or not 32 <= len(self.bearer) <= 512
            or any(ord(c) < 33 or ord(c) > 126 for c in self.bearer)
            or self.tenant_id not in ("tenant-test", "tenant-beta")
            or type(self.source_refs) is not frozenset
            or not self.source_refs
            or any(type(s) is not str or not s or len(s) > 128 for s in self.source_refs)
        ):
            raise ConsumerDenied()


class TaskClient:
    def __init__(self, endpoint: AppEndpoint):
        if type(endpoint) is not AppEndpoint:
            raise ConsumerDenied()
        self.endpoint = endpoint

    def _request(self, method, path, body=None, key=None):
        headers = {
            "Host": "127.0.0.1:8765",
            "Origin": "http://127.0.0.1:8765",
            "Authorization": "Bearer " + self.endpoint.bearer,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if key is not None:
            headers["Idempotency-Key"] = key
        c = http.client.HTTPConnection("127.0.0.1", 8765, timeout=5)
        try:
            c.request(method, path, body=body, headers=headers)
            response = c.getresponse()
            raw = response.read(32769)
            if (
                response.status != (202 if method == "POST" else 200)
                or len(raw) > 32768
                or response.getheader("Content-Type") != "application/json"
                or response.getheader("Cache-Control") != "no-store"
            ):
                raise ConsumerDenied()
            result = json.loads(raw)
            if type(result) is not dict or result.get("authority") != AUTHORITY:
                raise ConsumerDenied()
            return result
        except Exception:
            raise ConsumerDenied() from None
        finally:
            c.close()

    def create(self, source_ref, *, idempotency_key):
        import re

        if (
            type(source_ref) is not str
            or source_ref not in self.endpoint.source_refs
            or type(idempotency_key) is not str
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", idempotency_key)
        ):
            raise ConsumerDenied()
        result = self._request(
            "POST", "/v1/audit-requests",
            json.dumps({"source_ref": source_ref}).encode(), idempotency_key,
        )
        try:
            return TaskHandle(
                self.endpoint.tenant_id, source_ref,
                *(identifier(result[k]) for k in ("request_id", "run_id", "job_id", "event_id")),
            )
        except Exception:
            raise ConsumerDenied() from None

    def status(self, task):
        try:
            if (
                type(task) is not TaskHandle
                or task.tenant_id != self.endpoint.tenant_id
                or task.source_ref not in self.endpoint.source_refs
            ):
                raise ConsumerDenied()
            for key in ("request_id", "run_id", "job_id", "event_id"):
                identifier(getattr(task, key))
            result = self._request("GET", "/v1/audit-requests/" + task.request_id)
            if (
                any(result.get(k) != getattr(task, k) for k in ("request_id", "run_id", "job_id", "source_ref"))
                or result.get("native_approval") is not None
                or result.get("share_grant") is not None
            ):
                raise ConsumerDenied()
            return result
        except Exception:
            raise ConsumerDenied() from None

    def read(self, task, reader, bearer, *, nonce):
        """DONE is only a prerequisite. Signed M1 read supplies result authority.

        Existing status.report_version is input reference metadata: never use it
        as a generated report pin. Only the signed result locator supplies pins.
        """
        status = self.status(task)
        if status.get("job_state") != "TEST_ONLY_DONE":
            raise ConsumerDenied()
        result = reader.read(bearer, task.tenant_id, task.job_id, nonce=nonce)
        if any(result.locator.get(k) != getattr(task, k) for k in ("tenant_id", "request_id", "run_id", "job_id")):
            raise ConsumerDenied()
        return result
