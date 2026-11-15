"""Import an authorized recorded CaptureManifest into a distinct job scope.

Raw bytes/status/timestamps are preserved. This is declared offline input replay,
not a claim that an HTTP request was made again or that an old report is output.
"""

import base64
from datetime import datetime, timezone
import json

from vrae.collection.manifest import CaptureBundle, document_hash
from vrae.collection.policy import SourceAccess
from vrae.evidence import EvidencePack
from .producer import CandidateDenied, LeaseContext, capture_digest


def load(c, tenant, lease):
    cur = c.execute(
        "SELECT * FROM ra4b_p2.load_leased_source(%s,%s,%s,%s)",
        (tenant, lease[0], lease[2], lease[3]),
    )
    row = cur.fetchone()
    if row is None:
        raise CandidateDenied("S2_AUTHORIZED_INPUT_UNAVAILABLE")
    return dict(zip([v.name for v in cur.description], row))


def materialize(row, lease):
    source = json.loads(bytes(row["raw_source"]))
    objects = {k: base64.b64decode(v, validate=True) for k, v in source["objects_base64"].items()}
    pack = EvidencePack.load(source["pack"], objects, expected_ref=source["pack"]["pack_ref"])
    entries = pack.document["sources"]
    if len(entries) != 1 or entries[0]["kind"] != "CaptureManifest":
        raise CandidateDenied("S2_SINGLE_OFFLINE_CAPTURE_REQUIRED")
    origin = entries[0]
    capture = CaptureBundle(
        json.loads(json.dumps(origin["document"])),
        {k: objects[v] for k, v in origin["object_refs"].items()},
    )
    capture.verify()
    audit = dict(row["audit_document"])
    audit["audit_id"] = str(row["request_id"])
    policy = dict(row["policy_document"])
    scope = {
        "tenant_id": row["tenant_id"],
        "run_id": str(row["run_id"]),
        "policy_id": audit["source_policy_ref"],
        "policy_version": audit["source_policy_version"],
    }
    capture.manifest.update(scope)
    capture.manifest["audit_id"] = audit["audit_id"]
    for page in capture.manifest["pages"]:
        snap = page["snapshot"]
        snap.update(scope)
        identity = document_hash(
            {"tenant": scope["tenant_id"], "run": scope["run_id"], "url": snap["url"]}
        )
        snap["snapshot_id"] = "snap-" + identity
        if page["evidence"] is not None:
            page["evidence"].update(
                tenant_id=scope["tenant_id"],
                run_id=scope["run_id"],
                snapshot_id=snap["snapshot_id"],
                evidence_id="ev-" + identity,
            )
    capture.manifest["manifest_sha256"] = document_hash(
        {k: v for k, v in capture.manifest.items() if k != "manifest_sha256"}
    )
    capture.verify()
    access = SourceAccess(
        audit, lambda: policy, terms_reference=capture.manifest["terms_reference"]
    )
    context = LeaseContext(
        scope["tenant_id"],
        str(row["request_id"]),
        scope["run_id"],
        str(row["job_id"]),
        row["worker_role"],
        str(lease[2]),
        lease[3],
        row["lease_until"].isoformat(),
        row["origin_epoch"],
        row["source_ref"],
        row["reference_sha256"],
        capture_digest(capture),
        scope["policy_id"],
        scope["policy_version"],
        document_hash(policy),
        row["loaded_at"].isoformat(),
    )
    return capture, access, context


def build(c, tenant, lease):
    from .producer import generate

    with c.transaction():
        row = load(c, tenant, lease)
    capture, access, context = materialize(row, lease)
    return generate(capture, access, context, now=datetime.now(timezone.utc)), context


def stage(c, tenant, lease, candidate):
    with c.transaction():
        return c.execute(
            "SELECT ra4b_p2.commit_generated_result(%s,%s,%s,%s,%s,%s,%s)",
            (
                tenant,
                lease[0],
                lease[2],
                lease[3],
                candidate._payload,
                candidate._source,
                candidate._html,
            ),
        ).fetchone()[0]
