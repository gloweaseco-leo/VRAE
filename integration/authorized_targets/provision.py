"""Operator-only configurable provisioning. Never reachable from the BFF."""

from psycopg import sql
from psycopg.types.json import Jsonb
from integration.authorized_targets.authority import token_hash


def install(connection, tenants):
    # Caller is a separate migration administrator. Runtime roles receive no
    # provisioning privilege; invite counts are deliberately not a constraint.
    for tenant in tenants:
        t = tenant["tenant_id"]
        connection.execute("INSERT INTO ra4a.tenants VALUES(%s,'AUTHORIZED_TARGET_V1')", (t,))
        connection.execute(
            "INSERT INTO target_v1.capacity VALUES(%s,%s)", (t, tenant["max_pending"])
        )
        for binding in tenant["actors"]:
            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {} IN ROLE {}"
                ).format(
                    sql.Identifier(binding["role"]),
                    sql.Literal(binding["password"]),
                    sql.Identifier(
                        "target_v1_ai"
                        if binding.get("port") == "AI"
                        else "target_v1_reviewer"
                        if binding.get("port") == "REVIEW"
                        else "target_v1_" + binding["kind"].lower()
                    ),
                )
            )
            connection.execute(
                "INSERT INTO ra4a_private.principals VALUES(%s,%s,%s,true,'AUTHORIZED_TARGET_V1')",
                (binding["role"], t, binding["kind"]),
            )
            connection.execute(
                "INSERT INTO ra4a_private.assignments VALUES(%s,%s,true)", (binding["role"], t)
            )
            connection.execute(
                "INSERT INTO target_v1.actors VALUES(%s,%s,%s,1,true,%s)",
                (binding["role"], t, binding["kind"], tenant["expires_at"]),
            )
        policies = set()
        for plan in tenant["plans"]:
            p = plan["policy"]
            key = (p["policy_id"], p["policy_version"])
            if key not in policies:
                connection.execute(
                    "INSERT INTO ra4a.policies VALUES(%s,%s,%s,'ALLOWED',%s,'AUTHORIZED_READONLY')",
                    (t, *key, p["expires_at"]),
                )
                policies.add(key)
            connection.execute(
                "INSERT INTO target_v1.plans VALUES(%s,%s,%s,%s,false)",
                (t, plan["target_id"], plan["origin"], Jsonb(plan)),
            )
        for invitation in tenant["invitations"]:
            d = invitation["document"]
            connection.execute(
                "INSERT INTO target_v1.invitations VALUES(%s,%s,%s,%s,%s,false,false)",
                (t, d["reference"], d["subject_ref"], token_hash(invitation["token"]), Jsonb(d)),
            )
