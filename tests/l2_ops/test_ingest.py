import json

import pytest

from vrae.l2_ops.ingest import load_source
from vrae.l2_ops.sources import OperationsDenied


def manifest(tmp_path):
    (tmp_path / "catalog.txt").write_text("SYNTHETIC_ONLY 工业零件：材料未知，不承诺客户事实。", encoding="utf-8")
    result = {"contract_version": "l2-local-input-v1", "tenant_id": "tenant-test",
              "bundle_id": "offline-catalog", "access_mode": "CLIENT_PROVIDED",
              "external_run_permission_reference": None,
              "inputs": [{"reference": "catalog", "media_type": "text/plain", "file": "catalog.txt",
                          "origin_reference": "synthetic-client-upload-example",
                          "analysis_basis_reference": "controlled-test-only-not-customer-authorization",
                          "synthetic": True, "reuse_permission_reference": None, "expected_sha256": None}]}
    path = tmp_path / "input.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return path, result


def test_local_provided_capture_needs_no_external_auth_or_network(tmp_path):
    path, _ = manifest(tmp_path)
    result = load_source(path).document()
    assert result["diagnostic_level"] == "L2" and result["execution"] == "OFFLINE_CAPTURE_ONLY"
    assert result["inputs"][0]["synthetic"] is True
    assert "工业零件" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("file", ["../outside.txt", "/outside.txt", "C:/outside.txt"])
def test_local_ingestion_rejects_path_escape_before_read(tmp_path, file):
    path, value = manifest(tmp_path)
    value["inputs"][0]["file"] = file
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(OperationsDenied, match="PATH_ESCAPE"):
        load_source(path)


def test_source_digest_change_and_oversize_fail_closed(tmp_path):
    path, value = manifest(tmp_path)
    value["inputs"][0]["expected_sha256"] = "a" * 64
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(OperationsDenied, match="HASH_MISMATCH"):
        load_source(path)
    (tmp_path / "catalog.txt").write_bytes(b"x" * 2_000_001)
    with pytest.raises(OperationsDenied, match="BOUNDED_EVIDENCE"):
        load_source(path)
