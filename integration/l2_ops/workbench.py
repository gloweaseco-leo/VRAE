"""Original one-SSR lifecycle with the controlled L2 task preparation catalog.

This mode never advertises an offline MP25 report as a new P40 task. P40 submit
stays disabled until the reproduced original lease issue and native C2 producer
are accepted; no repeated failed job is launched by opening this UI.
"""
import os

from integration.beta_review.codex3.m3_workbench import Workbench, serve
from integration.beta_review.codex3.runner import write
from .catalog import install
from .source_profiles import selected


class PreparationWorkbench(Workbench):
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
        self.r.lab.save()

    def bootstrap_identity(self):
        super().bootstrap_identity()
        self.profile_data["task_sources"] = {
            "404": {"source_ref": "accepted-404", "label": "制造业 · 联系路径404", "depth": "L1"},
            "200": {"source_ref": "accepted-200", "label": "制造业 · 静态路径200／证据不足", "depth": "L1"},
            "p40": {"source_ref": self.result["l2_input"]["source_ref"], "label": "工业泵阀 P40/V25 · L2 任务链待验收",
                    "depth": "L2", "enabled": False},
        }
        self.result["l2_readiness"] = {"mode": "PREPARATION_NOT_L2_E2E", "p40_submit_enabled": False,
            "worker_lease_red_retained": "nativep40scope311a", "c2_native_producer": "PENDING_OWNER_ACCEPTANCE",
            "single_original_ssr": True, "consultation": "UNLINKED", "cost_status": "UNKNOWN"}
        write(self.folder / "l2-readiness.json", self.result["l2_readiness"])


def main(label, minor):
    return serve(PreparationWorkbench(label, minor))
