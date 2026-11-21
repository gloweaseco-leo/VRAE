"""Explicit administrator bootstrap/additive migrations; never runs in an API UID."""

import json
from pathlib import Path
import psycopg
from infra.linux_service.supervisor import private, INPUT, write
from integration.authorized_targets.provision import install, grant_automatic_sessions
from integration.authorized_targets.operator import activate
from integration.authorized_targets.source_authority import TRUST


def main():
    TRUST.parent.mkdir(parents=True, exist_ok=True)
    write(TRUST, private(INPUT / "trust.json"), mode=0o444)
    with psycopg.connect(
        host="127.0.0.1",
        dbname="vrae_ra4a_p1",
        user="postgres",
        password=private(INPUT / "pg-password").decode(),
        autocommit=True,
    ) as c:
        checks = [
            ("SELECT to_regnamespace('ra4a') IS NOT NULL", "db/migrations/0001_ra4a_test_only.sql"),
            (
                "SELECT to_regnamespace('target_v1') IS NOT NULL",
                "infra/authorized_targets/001_authority.sql",
            ),
            (
                "SELECT to_regprocedure('target_v1.committed_input(text,uuid,text)') IS NOT NULL",
                "infra/authorized_targets/002_delivery.sql",
            ),
            (
                "SELECT to_regprocedure('target_v1.readiness(text)') IS NOT NULL",
                "infra/authorized_targets/003_api.sql",
            ),
            (
                "SELECT to_regprocedure('target_v1.report_context(text,uuid)') IS NOT NULL",
                "infra/authorized_targets/004_verified_reports.sql",
            ),
            (
                "SELECT to_regprocedure('target_v1.recipient_context(text,text,text,text)') IS NOT NULL",
                "infra/windows_service/005_recipient.sql",
            ),
            (
                "SELECT to_regprocedure('target_v1.ai_pending(text)') IS NOT NULL",
                "infra/linux_service/004_ai_pending.sql",
            ),
        ]
        checks.append((
            "SELECT to_regprocedure('target_v1.automatic_diagnosis(text,text,text,text)') IS NOT NULL",
            "infra/authorized_targets/006_automatic_diagnosis.sql",
        ))
        checks.append((
            "SELECT to_regprocedure('target_v1.automatic_session(text,text,text)') IS NOT NULL",
            "infra/authorized_targets/007_automatic_sessions.sql",
        ))
        checks.append((
            "SELECT position('request_language' in pg_get_functiondef('target_v1.committed_input(text,uuid,text)'::regprocedure))>0",
            "infra/authorized_targets/008_committed_language.sql",
        ))
        checks.append((
            "SELECT position('l2-industrial-1.0.4' in pg_get_functiondef('target_v1.committed_input(text,uuid,text)'::regprocedure))>0",
            "infra/authorized_targets/009_committed_scoped_language.sql",
        ))
        checks.append((
            "SELECT position('l2-industrial-1.0.5' in pg_get_functiondef('target_v1.committed_input(text,uuid,text)'::regprocedure))>0",
            "infra/authorized_targets/010_committed_context_language.sql",
        ))
        checks.append((
            "SELECT position('l2-industrial-1.0.6' in pg_get_functiondef('target_v1.committed_input(text,uuid,text)'::regprocedure))>0",
            "infra/authorized_targets/011_committed_procurement_language.sql",
        ))
        checks.append((
            "SELECT position('l2-industrial-1.0.7' in pg_get_functiondef('target_v1.committed_input(text,uuid,text)'::regprocedure))>0",
            "infra/authorized_targets/012_committed_purchase_tasks.sql",
        ))
        for query, file in checks:
            if not c.execute(query).fetchone()[0]:
                c.execute((Path("/work") / file).read_text())
        if (INPUT / "provision.json").exists():
            tenants = json.loads(private(INPUT / "provision.json"))
            with c.transaction():
                new = [
                    t
                    for t in tenants
                    if not c.execute(
                        "SELECT 1 FROM ra4a.tenants WHERE tenant_id=%s", (t["tenant_id"],)
                    ).fetchone()
                ]
                install(c, new)
                for envelope in json.loads(private(INPUT / "authorizations.json")):
                    if envelope["document"]["tenant_id"] in {t["tenant_id"] for t in new}:
                        activate(c, envelope)
        api = json.loads(private(INPUT / 'api.json'))
        if api.get('target_intake_enabled') is True:
            with c.transaction():
                for binding in api['bindings']:
                    if (binding.get('kind') == 'APP' and binding.get('port') is None
                            and binding.get('health_probe') is None):
                        grant_automatic_sessions(c, binding)
    print('{"phase":"SCHEMA_READY","existing_authority_not_reactivated":true}')


if __name__ == "__main__":
    main()
