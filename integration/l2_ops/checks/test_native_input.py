import base64
import json
from dataclasses import replace

import pytest

from tests.evidence.synthetic import http
from vrae.evidence import build_pack
from vrae.l2_ops.native_input import load_native
from vrae.l2_ops.sources import EvidenceInput, OperationsDenied, SourceBundle


@pytest.fixture
def archive_input():
    pack = build_pack([http()])
    archive = {"pack": pack.document,
               "objects_base64": {k: base64.b64encode(v).decode("ascii") for k, v in pack.objects.items()}}
    raw = json.dumps(archive, ensure_ascii=False, allow_nan=False).encode("utf-8")
    evidence = EvidenceInput("native-capture", "application/json", raw,
                             "existing-offline-synthetic-capture", "internal-synthetic-analysis", True)
    bundle = SourceBundle(pack.document["tenant_id"], "native-controlled-input", "OFFLINE_SYNTHETIC", (evidence,))
    return bundle, pack, archive


@pytest.mark.parametrize("mode", ["OFFLINE_SYNTHETIC", "PUBLIC_READONLY_CAPTURE", "CLIENT_PROVIDED"])
def test_three_input_capabilities_use_native_replay_without_new_capture(archive_input, mode):
    bundle, original, _ = archive_input
    bundle = replace(bundle, access_mode=mode)
    value = load_native(bundle, "native-capture", expected_pack_ref=original.ref,
                        expected_capture_run_id=original.document["run_id"])
    assert value.pack.document == original.document
    assert dict(value.pack.objects) == dict(original.objects)
    metadata = value.metadata()
    assert metadata["state"] == "NATIVE_SOURCE_VERIFIED_NOT_DIAGNOSED"
    assert metadata["network_requests"] == 0 and metadata["worker_task_created"] is False
    assert metadata["report_version"] is None and metadata["task_handle"] is None
    assert metadata["original_capture_run_id"] == original.document["run_id"]
    assert "objects_base64" not in metadata


@pytest.mark.parametrize("change", ["object", "quote", "stale_pin", "tenant", "run", "nonfinite", "duplicate"])
def test_native_graph_scope_and_parser_mismatches_refuse(archive_input, change):
    bundle, original, archive = archive_input
    pin, run = original.ref, original.document["run_id"]
    if change == "object":
        key = next(iter(archive["objects_base64"]))
        archive["objects_base64"][key] = base64.b64encode(b"changed body").decode()
    elif change == "quote":
        archive["pack"]["sources"][0]["document"]["pages"][0]["evidence"]["excerpt"] = "forged quotation"
    elif change == "stale_pin":
        pin = "ep-" + "a" * 64
    elif change == "tenant":
        bundle = replace(bundle, tenant_id="another-tenant")
    elif change == "run":
        run = "another-capture-run"
    raw = json.dumps(archive).encode()
    if change == "nonfinite":
        raw = b'{"pack":NaN,"objects_base64":{}}'
    if change == "duplicate":
        raw = b'{"pack":{},"pack":{},"objects_base64":{}}'
    bundle = replace(bundle, inputs=(replace(bundle.inputs[0], raw=raw),))
    with pytest.raises(OperationsDenied):
        load_native(bundle, "native-capture", expected_pack_ref=pin, expected_capture_run_id=run)


def test_raw_material_is_preserved_as_unconsumed_not_fabricated_http(archive_input):
    bundle, original, _ = archive_input
    raw_document = EvidenceInput("customer-spec", "text/plain", b"synthetic unparsed material",
                                "synthetic-provided-example", "internal-test", True)
    bundle = replace(bundle, inputs=(*bundle.inputs, raw_document))
    value = load_native(bundle, "native-capture", expected_pack_ref=original.ref,
                        expected_capture_run_id=original.document["run_id"])
    assert value.metadata()["inputs_not_in_native_pack"] == ["customer-spec"]
    assert value.pack.ref == original.ref
    with pytest.raises(OperationsDenied, match="CAPTURE_ARCHIVE_REQUIRED"):
        load_native(bundle, "customer-spec", expected_pack_ref=original.ref,
                    expected_capture_run_id=original.document["run_id"])
