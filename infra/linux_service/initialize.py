"""Explicit administrator bootstrap/additive migrations; never runs in an API UID."""

import json
from pathlib import Path
import psycopg
from infra.linux_service.supervisor import private, INPUT, write
from integration.authorized_targets.provision import install
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
                "SELECT to_regprocedure('target_v1.ai_pending(text)') IS NOT NULL",
                "infra/linux_service/004_ai_pending.sql",
            ),
        ]
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
    print('{"phase":"SCHEMA_READY","existing_authority_not_reactivated":true}')


if __name__ == "__main__":
    main()
