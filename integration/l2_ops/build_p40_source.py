"""Create a fresh tenant-test capture from accepted C1 synthetic bytes, no sockets."""
import asyncio
import base64
import json
from pathlib import Path

from integration.industry_l2.fixture import NOW, RecordedResolver, RecordedTransport
from tests.collection.test_security import fixture
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess
from vrae.evidence import build_pack
from vrae.l2_ops.sources import digest
from vrae.reviewing.canonical import sha


def build():
    folder = Path(__file__).parent / "fixtures"
    if (folder / "industrial-p40-worker.archive").exists() or (folder / "native-p40-worker.json").exists():
        raise FileExistsError("VERSIONED_CAPTURE_ALREADY_EXISTS_DO_NOT_OVERWRITE")
    audit, policy = fixture("AuditRequest"), fixture("SourcePolicy")
    audit.update(tenant_id="tenant-test", audit_mode="L1", audit_id="audit-c3-p40-v3")
    policy.update(tenant_id="tenant-test")
    access = SourceAccess(audit, lambda: policy, terms_reference="synthetic-c1-p40-bytes-worker-compatible-robots-v3", now=lambda: NOW)
    transport = RecordedTransport(overrides={"/robots.txt": b"User-agent: *\nDisallow:\n"})
    capture = asyncio.run(Collector(SafeFetcher(RecordedResolver(), transport)).capture(
        "l2-p40-worker-capture-v3", access, limits=Limits(max_pages=8, interval_seconds=0.01), retain_raw_html=True))
    pack = build_pack([capture])
    assert pack.document["tenant_id"] == "tenant-test" and len(pack.document["snapshots"]) == 8
    archive = json.dumps({"pack": pack.document, "objects_base64": {
        k: base64.b64encode(v).decode() for k, v in pack.objects.items()}}, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    folder = Path(__file__).parent / "fixtures"
    (folder / "industrial-p40-worker.archive").write_bytes(archive)
    manifest = {"contract_version": "l2-local-input-v1", "tenant_id": "tenant-test",
        "bundle_id": "c1-p40-controlled-native-v3", "access_mode": "OFFLINE_SYNTHETIC",
        "external_run_permission_reference": None, "inputs": [{"reference": "industrial-p40-worker",
        "media_type": "application/json", "file": "industrial-p40-worker.archive",
        "origin_reference": "accepted-C1-P40-V25-recorded-bytes-new-tenant-test-capture",
        "analysis_basis_reference": "internal-controlled-synthetic-not-client-authorization", "synthetic": True,
        "reuse_permission_reference": None, "expected_sha256": digest(sha(archive))}]}
    (folder / "native-p40-worker.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"pack_ref": pack.ref, "archive_sha256": sha(archive), "offline_exchanges": len(transport.requests),
                      "tenant_id": pack.document["tenant_id"], "run_id": pack.document["run_id"]}))


if __name__ == "__main__":
    build()
