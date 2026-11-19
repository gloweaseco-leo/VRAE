"""Original EvidencePack -> industry/Guard -> NativeSource; no new report engine."""

import base64
from vrae.evidence import build_pack
from vrae.application.ra4b_p2.m1.consumer import TaskHandle
from vrae.l2_ops.tasks import WorkerEvidence
from vrae.l2_ops.native_diagnosis import analyze
from vrae.l2_ops.sources import EvidenceInput, SourceBundle
from integration.l2_ops.native_report import produce
from contracts.l2_launch.contract import canonical


def produce_capture(captured, task, authorization_ref, created_at):
    pack = build_pack([captured])
    if pack.document["tenant_id"] != task["tenant_id"] or pack.document["run_id"] != task["run_id"]:
        raise ValueError("ORIGINAL_TASK_CAPTURE_BINDING")
    archive = canonical(
        {
            "pack": pack.document,
            "objects_base64": {k: base64.b64encode(v).decode() for k, v in pack.objects.items()},
        }
    )
    source = SourceBundle(
        task["tenant_id"],
        "capture-" + task["job_id"],
        "PUBLIC_READONLY_CAPTURE",
        (
            EvidenceInput(
                "actual-" + task["job_id"],
                "application/json",
                archive,
                authorization_ref,
                "ACTUAL_AUTHORIZED_READONLY_HTTP",
                False,
            ),
        ),
        authorization_ref,
    )
    handle = TaskHandle(**task)
    evidence = WorkerEvidence(
        handle,
        pack,
        source.document()["content_sha256"],
        pack.ref,
        {"port": "AUTHORIZED_TARGET_V1_CURRENT_PG_LEASE"},
    )
    diagnosis = analyze(evidence)
    native = produce(diagnosis, source, created_at=created_at)
    view = native.read()
    assert view.version["status"] == "REVIEW_REQUIRED" and view.version["run_id"] == task["run_id"]
    envelope = {
        "task": task,
        "pack": pack.document,
        "objects_base64": {k: base64.b64encode(v).decode() for k, v in pack.objects.items()},
        "diagnosis": diagnosis.document,
        "native_document": view.document,
        "version": view.version,
        "display_hash": view.display_hash,
        "pack_ref": pack.ref,
        "diagnosis_ref": diagnosis.result_ref,
        "source_bundle_sha256": source.document()["content_sha256"],
        "source_access_mode": "L1",
        "diagnostic_depth": "L2",
        "ai_state": "NO_MODEL",
        "publication": "UNPUBLISHED",
        "authority": "GENERATED_DRAFT_NOT_HUMAN_APPROVED",
        "external_release": False,
    }
    return envelope
