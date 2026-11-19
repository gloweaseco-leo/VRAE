"""One explicit controlled exercise exporter; never imported by deployment runtime."""

from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import time
from contracts.l2_launch.contract import canonical
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from integration.l2.support import Issuer
from integration.authorized_targets.checks.delivery_drill import signed
from integration.authorized_targets.authority import token_hash


def export(drill, scope, receipts):
    root = Path("/evidence/service-operator")
    root.mkdir(mode=0o700)

    def save(name, value):
        p = root / name
        p.write_bytes(value if isinstance(value, bytes) else canonical(value))
        p.chmod(0o600)

    save("trust.json", Path("/run/vrae-targets/trust.json").read_bytes())
    save(
        "deployment-key",
        drill.keys["deployment"]
        .private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        .hex()
        .encode(),
    )
    old = json.loads(Path("/run/vrae-targets/deployment.json").read_bytes())["document"]
    intent = {
        k: deepcopy(old[k])
        for k in (
            "source_class",
            "purpose",
            "not_before",
            "expires_at",
            "authorization_hashes",
            "deployment_go",
            "source_network_fee_go",
            "model_fee_go",
            "nameservers",
        )
    }
    intent.update(
        contract="vrae.linux-service-intent.v1", destination_ips=old["permitted_destination_ips"]
    )
    save("deployment-intent.json", signed(drill.keys["deployment"], "deployment", intent))
    save(
        "manifest.json",
        {
            "contract": "vrae.linux-service.v1",
            "source_sha": drill.state["g1_source_sha"],
            "source_class": "CONTROLLED_NON_CUSTOMER",
            "network_mode": "internal",
            "controlled_fixture": True,
            "publish": [],
        },
    )
    for name, source in [
        ("source-ca.pem", "/tmp/lab/cert.pem"),
        ("source-key.pem", "/tmp/lab/key.pem"),
        ("client-ca.pem", drill.pki["ca"]),
        ("server.pem", drill.pki["facade"]["certificate"]),
        ("server-key.pem", drill.pki["facade"]["key"]),
    ]:
        save(name, Path(source).read_bytes())
    api = deepcopy(scope["cfg"])
    api["bindings"] = [b for b in api["bindings"] if not b.get("port")]
    api.update(certificate="server.pem", certificate_key="server-key.pem")
    api["transport"]["hosts"] += ["localhost:18769", "127.0.0.1:18769"]
    save("api.json", api)
    save(
        "worker.json",
        {
            "kind": "WORKER",
            "authority": "AUTHORIZED_TARGET_V1",
            "bindings": scope["workers"],
            "workload": {"kind": "AUTHORIZED_EGRESS_V2"},
        },
    )
    save(
        "ai.json",
        {
            "kind": "APP",
            "authority": "AUTHORIZED_TARGET_V1",
            "bindings": drill.ai,
            "buyer_selection": {
                "tenant-beta/" + plan["target_id"]: {
                    "model": "TX10",
                    "rules": ["INFO-02", "TRUST-02"],
                    "subject_url": plan["origin"] + "/products/item",
                }
                for plan, _ in drill.external
            },
        },
    )
    admin = scope["admin"]
    # The parent connection was deliberately invalidated by actual PG restart.
    import psycopg

    admin = psycopg.connect(
        host="127.0.0.1",
        dbname="vrae_ra4a_p1",
        user="postgres",
        password=drill.state["admin_password"],
        autocommit=True,
    )
    admin.execute(Path("/work/infra/linux_service/004_ai_pending.sql").read_text())
    job = receipts[0]["task"]["job_id"]
    raw = admin.execute(
        "SELECT artifact FROM target_v1.results WHERE tenant_id=%s AND job_id=%s",
        ("tenant-beta", job),
    ).fetchone()[0]
    rid = json.loads(bytes(raw))["version"]["report_id"]
    issuer = Issuer()
    directory = {
        "issuer": issuer.issuer,
        "audience": issuer.audience,
        "jwks": issuer.jwks,
        "mode": "CONTROLLED",
        "expires": time.time() + 3600 * drill.state.get("local_validity_hours", 1),
        "people": [
            {
                "actor_id": n,
                "subject": n,
                "name": "Controlled " + n,
                "tenant_id": "tenant-beta",
                "role": role,
                "report_ids": [rid],
            }
            for n, role in [("owner", "OWNER"), ("reviewer", "REVIEWER"), ("reader", "READER")]
        ],
    }
    binding = deepcopy(next(b for b in scope["reviewers"] if b["tenant_id"] == "tenant-beta"))
    bearer = secrets.token_urlsafe(32)
    binding.update(
        service_sha256=token_hash(bearer),
        client_certificate_sha256=drill.pki["client"]["der_sha256"],
    )
    review = {
        "kind": "APP",
        "authority": "AUTHORIZED_TARGET_V1",
        "bindings": [binding],
        "source_sha": drill.state["g1_source_sha"],
        "report_directory": directory,
        "ledger_root": "/ledger",
        "max_inflight": 4,
        "certificate": "server.pem",
        "certificate_key": "server-key.pem",
        "transport": {
            "bind": "0.0.0.0",
            "port": 8770,
            "hosts": ["vrae-api:8770", "localhost:18770", "127.0.0.1:18770"],
            "origins": [],
            "mtls": True,
            "client_ca": "client-ca.pem",
        },
    }
    verified = drill.state.get("verified_linux_service", False)
    reader_subject = "reader"
    if verified:
        from datetime import datetime, UTC, timedelta
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import PublicFormat
        from vrae.l2.verified import PROFILE, CURRENT_REPORTS

        admin.execute(Path("/work/infra/authorized_targets/004_verified_reports.sql").read_text())
        context = admin.execute(
            "SELECT target_v1.report_context(%s,%s)", ("tenant-beta", job)
        ).fetchone()[0]
        reader_subject = context["recipient_subject"]
        directory["mode"] = "VERIFIED_DIRECTORY"
        for person in directory["people"]:
            person["report_ids"] = [CURRENT_REPORTS]
            person["verification_ref"] = "ISOLATED_PROTOCOL_TEST_NOT_HUMAN-" + person["actor_id"]
            if person["role"] == "READER":
                person["subject"] = reader_subject
        now = datetime.now(UTC)
        authority_key = Ed25519PrivateKey.generate()
        document = {
            "contract": "vrae.verified-report-authority.v1",
            "profile": PROFILE,
            "reference": "ISOLATED_DEPLOYMENT_PROTOCOL_TEST_NOT_CUSTOMER_SIGNOFF",
            "allowed_source_classes": ["CONTROLLED_NON_CUSTOMER"],
            "not_before": (now - timedelta(minutes=1)).isoformat(),
            "expires_at": datetime.fromtimestamp(directory["expires"], UTC).isoformat(),
            "directory": directory,
        }
        save("report-trust.json", {"keys": {"test-report-authority": {
            "role": "REPORT_AUTHORITY", "revoked": False,
            "public": authority_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
        }}})
        save("report-authority.json", signed(authority_key, "test-report-authority", document))
        review["report_profile"] = PROFILE
        review.pop("report_directory")
    save("review.json", review)
    save("pg-password", drill.state["admin_password"].encode())
    save("site.json", Path("/tmp/lab/site.json").read_bytes())
    # Private external probe key never enters service config/image or public artifact.
    client = Path("/client-share/service-report.json")
    client.write_bytes(
        canonical(
            {
                "bearer": bearer,
                "verified": verified,
                "reader_subject": reader_subject,
                "job": job,
                "issuer_kid": issuer.kid,
                "jwks": issuer.jwks,
                "issuer_key": issuer.key.private_bytes(
                    Encoding.Raw, PrivateFormat.Raw, NoEncryption()
                ).hex(),
            }
        )
    )
    client.chmod(0o600)
    os.chown(client, 10004, 10004)
    admin.close()
