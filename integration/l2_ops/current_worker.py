"""Application-layer composition of original M2 sessions and C3 task evidence.

The core task/evidence package does not depend on the operator web application.
"""
from contextlib import contextmanager
from datetime import UTC, datetime

from vrae.l2_ops.sources import OperationsDenied
from vrae.l2_ops.tasks import L2Tasks


@contextmanager
def current_worker(port, task, sessions, sid, *, policy_expires_at):
    """Hold the existing M2 signed session and actual PG source locks.

    Yielded snapshot/deadline is usable only INSIDE this context, including
    the caller's Brief COMMIT. This does not authenticate any C2 deep report.
    """
    from apps.operator_console.b5b_m2_sessions import GeneratedSessions

    if type(port) is not L2Tasks:
        raise OperationsDenied("L2_ORIGINAL_TASK_PORT_REQUIRED")
    source = port._source(task)
    if type(sessions) is not GeneratedSessions:
        raise OperationsDenied("L2_ORIGINAL_GENERATED_SESSIONS_REQUIRED")
    if (type(policy_expires_at) is not datetime or policy_expires_at.tzinfo is None
            or policy_expires_at.utcoffset() is None):
        raise OperationsDenied("L2_CURRENT_POLICY_DEADLINE_REQUIRED")
    with sessions.request(sid) as (_, view):
        session = sessions.require(sid)
        bound = sessions.task_handles.get((task.tenant_id, task.job_id))
        if bound is None or bound[1] != task:
            raise OperationsDenied("L2_CURRENT_TASK_BINDING_REQUIRED")
        deadline = min(policy_expires_at, datetime.fromtimestamp(min(
            session.expires, session.assignment.expires, sessions.reader.anchor.expires), UTC))
        if datetime.now(UTC) >= deadline:
            raise OperationsDenied("L2_CURRENT_AUTHORITY_EXPIRED")
        yield port._from_authorized_result(task, source, view.payload), deadline
        sessions.require(sid)
        if datetime.now(UTC) >= deadline:
            raise OperationsDenied("L2_CURRENT_AUTHORITY_EXPIRED")

