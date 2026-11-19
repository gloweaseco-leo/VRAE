"""The accepted task drill exposed to a separate mTLS service container."""

from copy import deepcopy
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
import os
import secrets
import shutil
import time
from pathlib import Path
from types import SimpleNamespace
from contracts.l2_launch.vf_b import submission_document
from integration.authorized_targets.checks.delivery_drill import Drill
from integration.authorized_targets.checks.api_tls import create
from integration.l2_launch.g1.fixtures import submission
from integration.l2_launch.g1 import supervisor as process


class ApiDrill(Drill):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.external = []

    def migrate(self, admin):
        super().migrate(admin)
        admin.execute(Path("/work/infra/authorized_targets/003_api.sql").read_text())

    def deployment_environment(self):
        if self.state.get("network_internal") is not True or not self.state.get("network_id"):
            raise PermissionError("OWNED_INTERNAL_NETWORK_REQUIRED")
        return {
            "parent_network_mode": "internal",
            "network_internal": True,
            "network_id": self.state["network_id"],
            "interfaces": sorted(os.listdir("/sys/class/net")),
        }

    def configure(self, tenants):
        super().configure(tenants)
        tenant = next(t for t in tenants if t["tenant_id"] == "tenant-beta")
        for n, plan in enumerate(tenant["plans"]):
            inv = {
                "token": secrets.token_urlsafe(32),
                "document": {
                    "tenant_id": tenant["tenant_id"],
                    "reference": "external-invite-" + str(n),
                    "subject_ref": "external-service-subject-" + str(n),
                    "target_ids": [plan["target_id"]],
                    "expires_at": tenant["expires_at"],
                    "revoked": False,
                },
            }
            tenant["invitations"].append(inv)
            self.external.append((plan, inv))

    def tls(self, path):
        self.pki = create(path)
        return self.pki

    def local_client_tls(self, context):
        context.load_cert_chain(self.pki["client"]["certificate"], self.pki["client"]["key"])

    def api_config(self, cfg, tenants):
        super().api_config(cfg, tenants)
        ca = Path("/tmp/api-client-ca.pem")
        shutil.copyfile(self.pki["ca"], ca)
        ca.chmod(0o444)
        cfg["transport"] = {
            "bind": "0.0.0.0",
            "port": 8769,
            "hosts": ["vrae-api:8769", "127.0.0.1:8769"],
            "origins": ["https://vrae-api:8769", "https://127.0.0.1:8769"],
            "mtls": True,
            "client_ca": str(ca),
        }
        for binding in cfg["bindings"]:
            binding["client_certificate_sha256"] = self.pki["client"]["der_sha256"]

    def exercise(self, scope):
        super().exercise(scope)
        shared = Path("/client-share")
        requests = []
        for plan, invite in self.external:
            audit = scope["fixture"]("AuditRequest")
            audit.update(
                tenant_id="tenant-beta",
                site_url=plan["origin"] + "/",
                source_policy_ref=plan["policy"]["policy_id"],
                source_system="vrae",
                source_reference="external-trusted-service",
            )
            value, _ = submission(
                SimpleNamespace(audit=audit, policy=plan["policy"]), scope["issuers"]["tenant-beta"]
            )
            value.update(
                subject_ref=invite["document"]["subject_ref"],
                invitation_ref=invite["document"]["reference"],
            )
            value["submission_proof"] = scope["issuers"]["tenant-beta"].sign(
                "permission", "permission", submission_document(value)
            )
            changed = deepcopy(value)
            changed["language"] = "en"
            changed["submission_proof"] = scope["issuers"]["tenant-beta"].sign(
                "permission", "permission", submission_document(changed)
            )
            requests.append(
                {
                    "invitation_token": invite["token"],
                    "submit": value,
                    "variant": changed,
                    "target_id": plan["target_id"],
                }
            )
        for source, name in (
            (self.pki["ca"], "ca.pem"),
            (self.pki["client"]["certificate"], "client.pem"),
            (self.pki["client"]["key"], "client-key.pem"),
            (self.pki["other-client"]["certificate"], "other-client.pem"),
            (self.pki["other-client"]["key"], "other-client-key.pem"),
        ):
            p = shared / name
            shutil.copyfile(source, p)
            p.chmod(0o600)
            os.chown(p, 10004, 10004)
        cfg = {
            "host": "vrae-api",
            "port": 8769,
            "bearer": "lab-beta",
            "requests": requests,
            "permission_key": scope["issuers"]["tenant-beta"]
            .key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            .hex(),
        }
        p = shared / "config.json"
        process.write(p, cfg)
        os.chown(p, 10004, 10004)
        process.write(
            Path("/evidence/api-ready.json"),
            {"phase": "READY_FOR_EXTERNAL_SERVICE", "api_version": "vrae.diagnosis-api.v1"},
        )
        process.wait(lambda: (shared / "submit.done").exists(), seconds=180)
        receipts = scope["consume"]()
        successful = [x for x in receipts if x.get("task", {}).get("tenant_id") == "tenant-beta"]
        if len(successful) != 2:
            raise AssertionError("EXTERNAL_TASKS_NOT_ACTUALLY_CONSUMED")
        process.write(
            Path("/evidence/api-captured.json"),
            {"phase": "COMMITTED", "runs": [x["task"]["run_id"] for x in successful]},
        )
        process.wait(lambda: (shared / "read.done").exists(), seconds=180)
        process.wait(lambda: (shared / "recovered.done").exists(), seconds=180)
        # Actual API process replacement keeps PG sessions, returns and IDs.
        process.stop(scope["app"])
        app, log = process.spawn(
            "targets-api-process-restart",
            10001,
            scope["appcfg"],
            "integration.authorized_targets.http",
        )
        process.wait(lambda: b"AUTHORIZED_TARGET_HTTPS_READY" in log.read_bytes())
        scope["app"] = app
        process.write(Path("/evidence/api-restarted.json"), {"phase": "API_RESTARTED"})
        process.wait(lambda: (shared / "restart.done").exists(), seconds=180)
        process.write(
            Path("/evidence/api.json"),
            {
                "contract": "vrae.standalone-api-drill.v1",
                "source_sha": self.state["g1_source_sha"],
                "independent_client_namespace": True,
                "mutual_tls": True,
                "new_external_tasks": [x["task"] for x in successful],
                "api_process_restart": True,
                "original_pg_process_restart": True,
                "customer_targets": 0,
                "model_calls": 0,
                "cloud_resources": 0,
            },
        )
        self.app = app
        self.workers = scope["workers"]
        if self.state.get("linux_service"):
            from infra.linux_service.controlled import export

            export(self, scope, successful)

    def hold(self):
        config = process.provision(
            "api-continuous-worker",
            65532,
            {
                "kind": "WORKER",
                "authority": "AUTHORIZED_TARGET_V1",
                "bindings": self.workers,
                "workload": {"kind": "AUTHORIZED_EGRESS_V2"},
                "poll_interval_seconds": 0.5,
            },
        )
        process.spawn(
            "api-continuous-worker", 65532, config, "integration.authorized_targets.worker"
        )
        process.write(
            Path("/evidence/serving.json"),
            {"endpoint": "https://vrae-api:8769", "scope": "CONTROLLED_NON_CUSTOMER"},
        )
        while True:
            time.sleep(1)
