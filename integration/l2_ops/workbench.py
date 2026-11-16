"""Original one-SSR lifecycle with the controlled L2 task preparation catalog.

This mode never advertises an offline MP25 report as a new P40 task. P40 submit
stays disabled until the reproduced original lease issue and native C2 producer
are accepted; no repeated failed job is launched by opening this UI.
"""
import os
import json
import secrets
import time

from psycopg import sql
from vrae.l2_ops.ledger import install as install_briefs

from integration.beta_review.codex3.m3_workbench import Workbench, serve
from integration.beta_review.codex3.runner import write
from .catalog import install
from .source_profiles import selected
from . import readiness


class PreparationWorkbench(Workbench):
    def __init__(self, label, minor):
        super().__init__(label, minor)
        self.l2_issuer = None
        self.l2_nonces = set()
        if readiness.enabled():
            from integration.beta_review.codex3.runner import cmd
            for ref in ("HEAD", "origin/main"):
                cmd(["git", "merge-base", "--is-ancestor", readiness.ACCEPTED_PERFORMANCE_MAIN, ref])

    def start_pg(self):
        super().start_pg()
        source_ref, _, native = selected("industrial-p40-v3")
        self.result["l2_input"] = install(self.r.lab, native, source_ref=source_ref)
        self.allowed_source_refs = ("accepted-404", "accepted-200", source_ref)
        self.r.lab.state["l2_source_refs"] = [source_ref]
        self.r.lab.state["l2_source_binding"] = {"sha256": self.result["l2_input"]["reference_sha256"],
                                               "policy_id": "pol-001", "policy_version": 1}
        if os.name == "posix":
            self.r.lab.state["l2_evidence_owner"] = {"uid": os.getuid(), "gid": os.getgid()}
        self.r.lab.state["l2_brief_password"] = secrets.token_urlsafe(32)
        self.secret_values.append(self.r.lab.state["l2_brief_password"])
        with self.r.lab.connect(dbname="vrae_ra4a_p1") as c:
            c.execute(sql.SQL("CREATE ROLE l2_ops_runtime LOGIN PASSWORD {}").format(sql.Literal(self.r.lab.state["l2_brief_password"])))
            install_briefs(c, "l2_ops_runtime")
        from integration.beta_review.codex3.runner import cmd
        owned = json.loads(cmd(["docker", "inspect", self.r.lab.name, "--format", "{{json .Mounts}}"] ))
        self.result["l2_owned_pg_mounts"] = [{k: row[k] for k in ("Type", "Name", "Destination") if k in row} for row in owned]
        self.result["l2_owned_pg_container_id"] = cmd(["docker", "inspect", self.r.lab.name, "--format", "{{.Id}}"] ).decode().strip()
        self.r.lab.save()

    def cleanup(self):
        from integration.beta_review.codex3.runner import cmd
        recorded = self.result.get("l2_owned_pg_container_id")
        if recorded:
            actual = cmd(["docker", "inspect", self.r.lab.name, "--format", "{{.Id}}"] ).decode().strip()
            assert actual == recorded, "L2_OWNED_PG_ID_CHANGED"
        result = super().cleanup()
        if recorded:
            assert not cmd(["docker", "ps", "-aq", "--no-trunc", "--filter", "id="+recorded]).strip()
            for mount in self.result["l2_owned_pg_mounts"]:
                if mount["Type"] == "volume":
                    assert not cmd(["docker", "volume", "ls", "-q", "--filter", "name=^"+mount["Name"]+"$"]).strip(), "L2_OWNED_PG_VOLUME_REMAINS"
            self.result["l2_cleanup"] = {"recorded_container_absent": True, "recorded_pg_volumes_absent": True,
                "old_anonymous_volumes": "UNKNOWN_UNTOUCHED", "global_prune": False}
            write(self.folder / "l2-owned-cleanup.json", self.result["l2_cleanup"])
        return result

    def bootstrap_identity(self):
        super().bootstrap_identity()
        self.profile_data["task_sources"] = {
            "404": {"source_ref": "accepted-404", "label": "制造业 · 联系路径404", "depth": "L1"},
            "200": {"source_ref": "accepted-200", "label": "制造业 · 静态路径200／证据不足", "depth": "L1"},
            "p40": {"source_ref": self.result["l2_input"]["source_ref"], "label": "工业泵阀 P40/V25 · L2 任务链待验收",
                    "depth": "L2", "enabled": readiness.enabled()},
        }
        self.result["l2_readiness"] = {"mode": "RUNTIME_READY_NOT_ACCEPTED_E2E" if readiness.enabled() else "PREPARATION_NOT_L2_E2E", "p40_submit_enabled": readiness.enabled(),
            "worker_lease_red_retained": "nativep40scope311a", "c2_native_producer": "ACCEPTED_PR113_RUNTIME_WIRED",
            "single_original_ssr": True, "consultation": "UNLINKED", "cost_status": "UNKNOWN"}
        self.result["l2_readiness"]["accepted_performance_main"] = readiness.ACCEPTED_PERFORMANCE_MAIN
        self.result["l2_readiness"]["business_role"] = "l2_ops_runtime_OWN_NAMESPACE_ONLY"
        write(self.folder / "l2-readiness.json", self.result["l2_readiness"])

    def ssr_configuration(self):
        from integration.l2.support import Issuer as ControlledIssuer
        from tests.identity.issuer import ISSUER
        # Parent-only key; every new SSR boot gets new C2 keys/nonces.
        self.l2_issuer = ControlledIssuer()
        self.l2_nonces.clear()
        cfg = super().ssr_configuration()
        cfg["native"] = {"version": "C3_NATIVE_RUNTIME_1", "enabled": readiness.enabled(),
            "accepted_performance_main": readiness.ACCEPTED_PERFORMANCE_MAIN,
            "source_profile": "industrial-p40-v3", "policy_expires_at": self.result["l2_input"]["policy_expires_at"],
            "brief_password": self.r.lab.state["l2_brief_password"],
            "identity": {"issuer": self.l2_issuer.issuer, "audience": self.l2_issuer.audience,
                "jwks": self.l2_issuer.jwks, "expires": self.profile_data["anchor"]["expires"],
                "task_issuer": ISSUER, "task_subject": "synthetic-reviewer-1", "subject": "synthetic-reviewer-1",
                "actor_id": "c3-controlled-reviewer", "name": "内部受控审阅员（合成身份）", "tenant_id": "tenant-test"}}
        return cfg

    def observe(self, method, path, status, raw):
        super().observe(method, path, status, raw)
        if method == "POST" and path == "/b5a/l2/challenge" and status == 200:
            self.l2_nonces.add(json.loads(raw)["nonce"])

    def sign(self, nonce):
        if nonce not in self.l2_nonces:
            return super().sign(nonce)
        self.l2_nonces.remove(nonce)
        observed = self.nonces.pop(nonce, None)
        assert observed is not None and time.monotonic()-observed < 30, "M3_OBSERVED_CHALLENGE_REQUIRED"
        return self.l2_issuer.token("synthetic-reviewer-1", nonce)


def main(label, minor):
    return serve(PreparationWorkbench(label, minor))
