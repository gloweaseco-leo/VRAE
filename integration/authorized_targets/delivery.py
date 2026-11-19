"""Authoritative committed inputs for C2/C1. This is not report access."""

import hashlib
from contextlib import contextmanager
from contracts.l2_launch.contract import canonical
from integration.authorized_targets.store import connect


@contextmanager
def committed_input(binding, job_id, *, purpose):
    with connect(binding) as c, c.transaction():

        def read():
            value = c.execute(
                "SELECT target_v1.committed_input(%s,%s,%s)",
                (binding["tenant_id"], job_id, purpose),
            ).fetchone()[0]
            if "source_authority" in value["artifact"]:
                from integration.authorized_targets.source_authority import authorization

                auth = value["artifact"]["source_authority"]
                authorization(
                    auth["authorization"], value["source_plan"], plan_sha256=auth["plan_sha256"]
                )
            return value

        first = read()
        if (
            first["task"]["job_id"] != str(job_id)
            or first["task"]["tenant_id"] != binding["tenant_id"]
        ):
            raise ValueError("COMMITTED_TASK_SCOPE")
        if (
            hashlib.sha256(canonical(first["artifact"])).hexdigest()
            != first["commit"]["artifact_sha256"]
        ):
            raise ValueError("COMMITTED_ARTIFACT_HASH")
        yield first
        if read() != first:
            raise ValueError("CURRENT_DELIVERY_INPUT_CHANGED")
