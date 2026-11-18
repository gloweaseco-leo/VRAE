"""Trusted launcher provisioning into the ORIGINAL SSR, no alternate server."""
from pathlib import Path

import psycopg

from vrae.l2_ops.ledger import BriefLedger
from vrae.l2_ops.sources import OperationsDenied
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource
from .native_tasks import NativeTasks
from .source_profiles import selected
from . import readiness


def provision(app, cfg, *, root=Path("/state/l2-native"), connect=None):
    fields = {"version", "enabled", "accepted_performance_main", "source_profile", "policy_expires_at", "identity", "brief_password"}
    if (type(cfg) is not dict or set(cfg) not in (fields, fields | {"s5"}) or cfg["version"] != "C3_NATIVE_RUNTIME_1"
            or cfg["source_profile"] != "industrial-p40-v3" or type(cfg["enabled"]) is not bool
            or cfg["accepted_performance_main"] != readiness.ACCEPTED_PERFORMANCE_MAIN
            or cfg["enabled"] != readiness.enabled()
            or type(cfg["brief_password"]) is not str or not 16 <= len(cfg["brief_password"]) <= 256):
        raise OperationsDenied("L2_NATIVE_TRUSTED_RUNTIME_CONFIG_REQUIRED")
    ref, bundle, native = selected(cfg["source_profile"])
    port = L2Tasks(app.generated.workflow.client, [RegisteredSource(ref, native)])

    def original_connect():
        return psycopg.connect(host="127.0.0.1", port=5432, dbname="vrae_l2_internal",
            user="l2_ops_runtime", password=cfg["brief_password"], connect_timeout=3,
            options="-c statement_timeout=2000 -c lock_timeout=2000")

    connection = connect or original_connect
    with connection() as c:
        identity = c.execute("SELECT session_user,current_user,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb "
            "FROM pg_roles WHERE rolname=session_user").fetchone()
        if identity != ("l2_ops_runtime", "l2_ops_runtime", False, False, False, False):
            raise OperationsDenied("L2_NATIVE_BRIEF_RUNTIME_ROLE_REQUIRED")
        if c.execute("SELECT to_regclass('l2_ops_v1.briefs') IS NOT NULL").fetchone() != (True,):
            raise OperationsDenied("L2_NATIVE_BRIEF_STORAGE_REQUIRED")
    app.native_tasks = NativeTasks(app, port, bundle, BriefLedger(connection),
        policy_expires_at=cfg["policy_expires_at"], identity=cfg["identity"],
        private_root=root, enabled=cfg["enabled"])
    if 's5' in cfg:
        if cfg['s5'] != {'version':'S5_OFFLINE_ONLY_1'}:
            raise OperationsDenied('S5_TRUSTED_CONFIG_REQUIRED')
        from integration.s5_ops.adapter import S5Ports
        app.native_tasks.s5 = S5Ports(app.native_tasks)
    app.generated.native_tasks = app.native_tasks
    return app.native_tasks
