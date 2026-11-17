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
        with self.r.lab.connect(dbname="postgres") as c:
            old_acl = c.execute("SELECT datacl::text FROM pg_database WHERE datname='vrae_ra4a_p1'").fetchone()[0]
            c.execute(sql.SQL("CREATE ROLE l2_ops_runtime LOGIN PASSWORD {}").format(sql.Literal(self.r.lab.state["l2_brief_password"])))
            c.execute("CREATE DATABASE vrae_l2_internal OWNER postgres")
            c.execute("REVOKE ALL ON DATABASE vrae_l2_internal FROM PUBLIC")
            c.execute("GRANT CONNECT ON DATABASE vrae_l2_internal TO l2_ops_runtime")
            assert c.execute("SELECT datacl::text FROM pg_database WHERE datname='vrae_ra4a_p1'").fetchone()[0] == old_acl
            assert c.execute("SELECT has_database_privilege('l2_ops_runtime','vrae_ra4a_p1','CONNECT')").fetchone() == (False,)
        with self.r.lab.connect(dbname="vrae_l2_internal") as c:
            install_briefs(c, "l2_ops_runtime")
        self.result["l2_business_storage"] = {"same_pg_instance": True, "database": "vrae_l2_internal",
            "runtime_role": "l2_ops_runtime", "old_database_acl_unchanged": True, "old_database_connect": False}
        write(self.folder / "l2-business-storage.json", self.result["l2_business_storage"])
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
        try:
            result = super().cleanup()
        finally:
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
            "p40": {"source_ref": self.result["l2_input"]["source_ref"], "label": "工业泵阀 P40/V25 · 合成深度诊断",
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

    def await_job(self, job):
        result = super().await_job(job)
        if self.web_tasks[job]["source_ref"] == "l2-industrial-p40-v3":
            with self.r.lab.connect(dbname="vrae_ra4a_p1") as c:
                row = c.execute("SELECT jsonb_build_object('worker_role',worker_role,'lease_seq',lease_seq,"
                    "'lease_until',lease_until,'row_created_at',created_at,'transaction_id',transaction_id,"
                    "'inside_original_lease',created_at < lease_until,'origin_epoch',origin_epoch,"
                    "'source_ref',source_ref,'finish_event',finish_event) FROM ra4b_p2.m1_results "
                    "WHERE tenant_id='tenant-test' AND job_id=%s", (job,)).fetchone()
            assert row and row[0]["inside_original_lease"]
            result = {**result, "lease_commit": row[0]}
            write(self.folder/("s0-worker-"+job+".json"), result)
        return result

    def audit_control(self, case, *, read=False):
        from integration.beta_review.codex3.runner import cmd
        from .runtime_audit import CASES
        assert case in CASES, "S0_CLOSED_AUDIT_CASE_REQUIRED"
        if read:
            return json.loads(cmd(["docker", "exec", "--user", "10003:10003", self.ssr_name,
                "python", "-c", "from pathlib import Path; import sys; print(Path(sys.argv[1]).read_text())",
                "/state/l2-native/s0-audit-" + case + ".json"]))
        proof = json.loads(cmd(["docker", "exec", "--user", "10003:10003", self.ssr_name,
            "python", "-c", "from pathlib import Path; print(Path('/state/l2-native/active-proof.json').read_text())"]))
        assert proof["task"]["job_id"] in self.web_tasks
        command = json.dumps({"case": case, "job_id": proof["task"]["job_id"]})
        cmd(["docker", "exec", "--user", "10003:10003", self.ssr_name, "python", "-c",
             "from pathlib import Path; import sys; p=Path('/state/l2-native/s0-audit-request.json'); "
             "f=p.open('x'); f.write(sys.argv[1]); f.close(); p.chmod(0o600)", command])
        return {"queued": case, "job_id": proof["task"]["job_id"]}

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
