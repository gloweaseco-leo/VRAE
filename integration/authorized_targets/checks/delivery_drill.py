"""Small extension of the accepted actual vertical, never customer permission."""

from copy import deepcopy
from datetime import datetime, UTC, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from contracts.l2_launch.contract import canonical, digest, permission_document
from contracts.l2_launch.vf_b import submission_document
from integration.authorized_targets.source_authority import TRUST, DEPLOYMENT, AuthorityDenied
from integration.authorized_targets.operator import activate, revoke
from integration.authorized_targets.authority import token_hash
from integration.authorized_targets import store
from integration.l2_launch.g1 import supervisor as process


def signed(key, kid, document):
    return {"key_id": kid, "document": document, "signature": key.sign(canonical(document)).hex()}


class Drill:
    def __init__(self):
        self.keys = {k: Ed25519PrivateKey.generate() for k in ("source", "deployment")}
        self.grants = []
        self.ai = []
        self.checks = []

    def migrate(self, admin):
        admin.execute(Path("/work/infra/authorized_targets/002_delivery.sql").read_text())

    def configure(self, tenants):
        for tenant in tenants:
            t = tenant["tenant_id"]
            slug = t[7:]
            for plan in tenant["plans"]:
                plan.update(
                    execution_profile="ADMIN_TARGET_V2",
                    authorization_kind="ADMIN_AUTHORIZED_READONLY",
                    source_class="CONTROLLED_NON_CUSTOMER",
                )
            b = {
                "tenant_id": t,
                "role": "targets_" + slug + "_ai",
                "password": os.urandom(24).hex(),
                "kind": "APP",
                "port": "AI",
            }
            tenant["actors"].append(b)
            self.ai.append(b)

    def activate(self, admin, tenants):
        keys = {
            kid: {
                "public": key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
                "role": "SOURCE_ADMIN" if kid == "source" else "DEPLOYMENT_OWNER",
                "source_class": "CONTROLLED_NON_CUSTOMER",
                "revoked": False,
            }
            for kid, key in self.keys.items()
        }
        TRUST.write_text(json.dumps({"keys": keys}))
        TRUST.chmod(0o444)
        for tenant in tenants:
            for plan in tenant["plans"]:
                sha = admin.execute(
                    "SELECT encode(sha256(convert_to(document::text,'UTF8')),'hex') FROM target_v1.plans WHERE tenant_id=%s AND target_id=%s",
                    (plan["tenant_id"], plan["target_id"]),
                ).fetchone()[0]
                d = {
                    k: deepcopy(plan[k])
                    for k in (
                        "tenant_id",
                        "target_id",
                        "source_class",
                        "origin",
                        "exact_paths",
                        "limits",
                    )
                }
                d.update(
                    contract="vrae.target-authorization.v2",
                    reference=plan["policy"]["authorization_reference"],
                    plan_sha256=sha,
                    purpose="READONLY_DIAGNOSIS",
                    methods=["GET", "HEAD"],
                    legal_reference="CONTROLLED_ORIGIN_OWNERSHIP_NOT_CUSTOMER_PERMISSION",
                    terms_reference=plan["terms_reference"],
                    robots="ENFORCE",
                    not_before=plan["policy"]["created_at"],
                    expires_at=plan["expires_at"],
                    retention_until=(
                        datetime.fromisoformat(plan["expires_at"]) + timedelta(hours=1)
                    ).isoformat(),
                    destination_ips=["93.184.216.20"],
                )
                envelope = signed(self.keys["source"], "source", d)
                activate(admin, envelope)
                self.grants.append(envelope)
        wrong = deepcopy(self.grants[0])
        wrong["document"]["origin"] = "https://unpermitted.test"
        wrong = signed(self.keys["source"], "source", wrong["document"])
        try:
            activate(admin, wrong)
        except AuthorityDenied:
            self.checks.append("administrator cannot activate mismatched domain")
        else:
            raise AssertionError("MISMATCHED_LEGAL_SCOPE_ACCEPTED")

    def ready(self):
        d = {
            "contract": "vrae.bounded-egress-deployment.v2",
            "source_class": "CONTROLLED_NON_CUSTOMER",
            "purpose": "READONLY_DIAGNOSIS",
            "not_before": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "expires_at": self.grants[0]["document"]["expires_at"],
            "authorization_hashes": [digest(g) for g in self.grants],
            "deployment_go": "GRANTED",
            "source_network_fee_go": "GRANTED",
            "model_fee_go": "NOT_GRANTED",
            "namespace_inode": os.stat("/proc/self/ns/net").st_ino,
            "interfaces": ["lo"],
            "parent_network_mode": "none",
            "nameservers": ["93.184.216.53"],
            "cafile": "/tmp/lab/cert.pem",
            "ca_sha256": hashlib.sha256(Path("/tmp/lab/cert.pem").read_bytes()).hexdigest(),
        }
        from infra.authorized_targets.egress_policy import install

        policy = install(
            namespace_inode=d["namespace_inode"],
            parent_network_mode=d["parent_network_mode"],
            interfaces=d["interfaces"],
            destination_ips=["93.184.216.20"],
            nameservers=d["nameservers"],
        )
        d["firewall_policy_sha256"] = policy.pop("policy_sha256")
        d["firewall_policy"] = policy
        d["permitted_destination_ips"] = ["93.184.216.20"]
        DEPLOYMENT.write_text(json.dumps(signed(self.keys["deployment"], "deployment", d)))
        DEPLOYMENT.chmod(0o444)

    def api_config(self, cfg, tenants):
        cfg["bindings"] = list(cfg["bindings"])
        for tenant in tenants:
            for actor in tenant["actors"]:
                if actor.get("port") == "REVIEW":
                    cfg["bindings"].append(
                        {
                            **actor,
                            "service_sha256": token_hash("lab-review-" + tenant["tenant_id"][7:]),
                        }
                    )

    def exercise(self, scope):
        admin = scope["admin"]
        call = scope["call"]

        def check(value, label):
            if not value:
                raise AssertionError(label)
            self.checks.append(label)

        rows = scope["rows"]
        alpha = next(row for row in rows if row[0] == "tenant-alpha")
        beta = next(row for row in rows if row[0] == "tenant-beta")
        job = alpha[2]
        artifact = json.loads(alpha[4])
        path = "/v1/internal/committed-input"
        code, current, _ = call("review-alpha", "POST", path, {"job_id": str(job)})
        check(
            code == 200 and current["task"] == artifact["task"],
            "C2 real BFF same committed task input",
        )
        check(
            current["commit"]["artifact_sha256"] == alpha[3]
            and current["artifact"]["display_hash"] == artifact["display_hash"],
            "C2 input binds actual artifact report version display hash",
        )
        check(
            current["grants_report_access"] is False
            and current["artifact"]["native_document"]["meta"]["source_access_mode"]
            == "PUBLIC_READONLY_CAPTURE",
            "delivery input neither synthetic relabel nor report grant",
        )
        check(
            call("alpha", "POST", path, {"job_id": str(job)}, scope["sessions"][0])[0] == 403,
            "customer service cannot open internal delivery input",
        )
        check(
            call("review-alpha", "POST", path, {"job_id": str(beta[2])})[0] == 403,
            "review input cross tenant denied",
        )
        for row in rows:
            d = json.loads(row[4])
            check(
                d["source_authority"]["authorization"] in self.grants,
                "actual report retains signed source authorization " + str(row[1]),
            )
        count = admin.execute(
            "SELECT count(*) FROM target_v1.capture_audit WHERE phase='CAPTURE_COMMITTED'"
        ).fetchone()[0]
        check(count == 5, "actual COMMIT source and retention records persisted")
        b = self.ai[0]
        from integration.authorized_targets.postcommit import run

        until = admin.execute(
            "SELECT lease_until FROM ra4a.jobs WHERE tenant_id=%s AND job_id=%s",
            ("tenant-alpha", job),
        ).fetchone()[0]
        if datetime.now(UTC) < until:
            try:
                run(b, job)
            except Exception as error:
                check(
                    getattr(error, "sqlstate", None) == "55000",
                    "AI cannot start inside original lease",
                )
            else:
                raise AssertionError("AI_STARTED_INSIDE_LEASE")
            time.sleep(max(0, (until - datetime.now(UTC)).total_seconds()) + 0.02)
        ai = run(b, job)
        check(
            ai["state"] == "AI_UNAVAILABLE"
            and ai["real_model_calls"] == 0
            and ai["task"] == artifact["task"],
            "C1 post COMMIT same run unavailable fallback no model call",
        )
        check(
            datetime.fromisoformat(ai["recorded_at"]) >= until,
            "AI receipt is after actual original lease end",
        )
        check(
            ai["artifact_sha256"] == alpha[3] and not ai["grants_report_access"],
            "AI usage receipt binds report and cannot publish",
        )
        try:
            with store.connect(scope["bindings"][0]) as c:
                c.execute("SELECT * FROM target_v1.ai_receipts")
        except Exception as error:
            check(getattr(error, "sqlstate", None) == "42501", "BFF cannot read AI raw receipts")
        else:
            raise AssertionError("AI_RAW_TABLE_LEAK")
        # Real kernel policy rejects source Worker -> BFF and metadata sockets.
        code = "import socket,json;out=[]\nfor ip,port in [('127.0.0.1',8769),('169.254.169.254',80)]:\n try:s=socket.create_connection((ip,port),timeout=.3);s.close();out.append(False)\n except OSError:out.append(True)\nprint(json.dumps(out))"
        p = subprocess.run(
            [sys.executable, "-c", code],
            env=process.ENV,
            user=65532,
            group=65532,
            extra_groups=[],
            capture_output=True,
            check=True,
        )
        check(
            json.loads(p.stdout) == [True, True],
            "actual worker kernel denies BFF and metadata destinations",
        )
        # Queue one authorized task, then withdraw its source before the Worker.
        accepted = scope["accepted"][0]
        value = deepcopy(accepted[1])
        value["command"]["request"]["idempotency_key"] = "withdraw-" + os.urandom(12).hex()
        policy = scope["tenants"][0]["plans"][0]["policy"]
        issuer = scope["issuers"]["tenant-alpha"]
        value["command"]["permission_reference"]["proof"] = issuer.sign(
            "permission", "permission", permission_document(value["command"], policy)
        )
        value["submission_proof"] = issuer.sign(
            "permission", "permission", submission_document(value)
        )
        check(
            call("alpha", "POST", "/v1/audit-requests", value, scope["sessions"][0])[0] == 202,
            "new target task admitted before legal withdrawal",
        )
        revoke(admin, "tenant-alpha", "target-pumps")
        failed = scope["consume"]()
        check(
            any(x.get("capture_failed") for x in failed),
            "withdrawn legal source records safe worker failure",
        )
        check(
            admin.execute(
                "SELECT count(*) FROM target_v1.capture_audit WHERE phase='CAPTURE_FAILED'"
            ).fetchone()[0]
            >= 1,
            "withdrawal failure audit persists without evidence overwrite",
        )
        affected = next(
            row
            for row in rows
            if row[0] == "tenant-alpha"
            and json.loads(row[4])["task"]["source_ref"] == "target-pumps"
        )
        check(
            call("review-alpha", "POST", path, {"job_id": str(affected[2])})[0] == 403,
            "source withdrawal closes previously committed delivery input",
        )
        check(
            call("alpha", "POST", "/v1/audit-requests", value, scope["sessions"][0])[0] == 403,
            "source withdrawal rejects new submissions",
        )
        code, withdrawn, _ = call(
            "alpha",
            "GET",
            "/v1/audits/" + scope["accepted"][0][2]["audit_ref"],
            session=scope["sessions"][0],
        )
        check(
            code == 200
            and withdrawn["access"]["state"] == "ENDED"
            and withdrawn["display_state"] == "access-ended",
            "BFF current source withdrawal remains separate from persisted task state",
        )
        # The other subject/target continues under the very same service.
        other = scope["accepted"][1]
        check(
            call("alpha", "GET", "/v1/audits/" + other[2]["audit_ref"], session=other[3])[0] == 200,
            "withdrawal does not revoke unrelated target subject",
        )
        check(
            '"objects_base64"' not in canonical(scope["transcript"]).decode(),
            "public HTTP evidence omits private committed artifact bytes",
        )
        process.write(
            Path("/evidence/delivery.json"),
            {
                "contract": "vrae.authorized-target-delivery-drill.v2",
                "checks": self.checks,
                "committed_input": {
                    "task": current["task"],
                    "commit": current["commit"],
                    "version": current["artifact"]["version"],
                    "display_hash": artifact["display_hash"],
                    "grants_report_access": False,
                },
                "ai_receipt": ai,
                "actual_customer_targets": 0,
                "model_calls": 0,
                "source_class": "CONTROLLED_NON_CUSTOMER",
                "authorization_hashes": [digest(g) for g in self.grants],
            },
        )
