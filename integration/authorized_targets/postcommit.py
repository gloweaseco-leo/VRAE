"""C1 injection point after original COMMIT and lease end, NO_MODEL by default.

C1 supplies its trusted Session adapter; this module never constructs a provider,
changes SourcePolicy, rewrites PUBLIC_READONLY_CAPTURE as synthetic, or issues a
review/ShareGrant. Browser input cannot supply this adapter.
"""

from copy import deepcopy
from datetime import datetime, UTC
import secrets
from psycopg.types.json import Jsonb
from integration.authorized_targets.delivery import committed_input
from integration.authorized_targets.store import connect


def run(binding, job_id, adapter=None, *, operation_id=None):
    operation = operation_id or "ai-" + secrets.token_hex(16)
    if type(operation) is not str or not 8 <= len(operation) <= 128:
        raise ValueError("AI_OPERATION_REQUIRED")
    with committed_input(binding, job_id, purpose="POST_COMMIT_AI_INPUT") as current:
        artifact = current["artifact"]
        result = {
            "state": "AI_UNAVAILABLE",
            "reason": "PROVIDER_GO_NOT_GRANTED",
            "real_model_calls": 0,
            "usage": None,
            "cost_status": "NOT_INCURRED_BY_THIS_OPERATION",
        }
        if adapter is not None:
            # Trusted C1 composition supplies Session.run(mode='REAL_QWEN') only
            # after its own current permission/price/fee and input bridge checks.
            request = deepcopy(current)
            request["ai_operation_id"] = operation
            result = adapter(request)
            if result.get("model", "qwen4-max") != "qwen4-max":
                raise ValueError("STRICT_QWEN4_REQUIRED")
        if result["state"] not in ("AI_UNAVAILABLE", "AI_CANDIDATES_FOR_HUMAN_REVIEW"):
            raise ValueError("AI_CANDIDATE_ONLY")
        provider_operation = result.get("operation_id")
        receipt = {
            **{k: v for k, v in result.items() if k != "operation_id"},
            "operation_id": operation,
            "provider_operation_id": provider_operation,
            "task": current["task"],
            "artifact_sha256": current["commit"]["artifact_sha256"],
            "report_content_hash": artifact["version"]["content_hash"],
            "display_hash": artifact["display_hash"],
            "model_constraint": "qwen4-max",
            "grants_report_access": False,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        with connect(binding) as c, c.transaction():
            c.execute(
                "SELECT target_v1.ai_record(%s,%s,%s,%s)",
                (binding["tenant_id"], job_id, operation, Jsonb(receipt)),
            )
        return receipt
