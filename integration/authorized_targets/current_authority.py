"""Authenticated PG facts for C1; short transactions never span model latency."""

from copy import deepcopy
from datetime import datetime, UTC
import json
from contracts.l2_launch.contract import canonical
from integration.authorized_targets.delivery import committed_input
from integration.authorized_targets.store import connect


class CurrentCommittedAuthority:
    def __init__(self, binding, job_id):
        self._binding = deepcopy(binding)
        self._job = str(job_id)
        self._snapshot = self._read()
        self._pins = canonical(self._snapshot)

    def __repr__(self):
        return "CurrentCommittedAuthority(<server-held>)"

    def _read(self):
        with connect(self._binding) as c, c.transaction():
            versioned = c.execute(
                "SELECT to_regprocedure('target_v1.completion_facts(text,uuid)') IS NOT NULL"
            ).fetchone()[0]
            if versioned:
                data = c.execute(
                    "SELECT target_v1.completion_facts(%s,%s)",
                    (self._binding["tenant_id"], self._job),
                ).fetchone()[0]
            else:
                data = c.execute(
                    "SELECT target_v1.committed_input(%s,%s,'POST_COMMIT_AI_INPUT')",
                    (self._binding["tenant_id"], self._job),
                ).fetchone()[0]
                grant = data["artifact"]["source_authority"]["authorization"]["document"]
                data["authority_expires_at"] = min(
                    grant["expires_at"], data["source_plan"]["expires_at"]
                )
            data["authority_profile"] = (
                "AUTHORIZED_TARGET_V2_COMMIT_V3" if versioned else "LEGACY_NO_MODEL"
            )
        # Reuse accepted retained-input/hash/current source signature validation.
        with committed_input(self._binding, self._job, purpose="POST_COMMIT_AI_INPUT") as checked:
            if data["commit"] != checked["commit"] or data["artifact"] != checked["artifact"]:
                raise PermissionError("CURRENT_TASK_CHANGED")
        return data

    def snapshot(self):
        return json.loads(canonical(self._snapshot))

    def check_current(self):
        data = self._read()
        if canonical(data) != self._pins or datetime.now(UTC) >= datetime.fromisoformat(
            data["authority_expires_at"]
        ):
            raise PermissionError("CURRENT_TASK_CHANGED")
        return self.snapshot()
