"""Local bounded evidence ingestion; no HTTP client or live-site fetcher."""
from pathlib import Path, PureWindowsPath

from vrae.reviewing.canonical import parse

from .sources import EvidenceInput, OperationsDenied, SourceBundle, digest


def load_source(manifest_path):
    path = Path(manifest_path).resolve(strict=True)
    root = path.parent
    with path.open("rb") as stream:
        manifest = parse(stream.read(131_073), limit=131_072)
    keys = {"contract_version", "tenant_id", "bundle_id", "access_mode", "inputs",
            "external_run_permission_reference"}
    if type(manifest) is not dict or set(manifest) != keys or manifest["contract_version"] != "l2-local-input-v1":
        raise OperationsDenied("L2_INPUT_MANIFEST_SHAPE")
    rows = manifest["inputs"]
    if type(rows) is not list or not 1 <= len(rows) <= 16:
        raise OperationsDenied("L2_SOURCE_MODE_OR_BOUND")
    inputs = []
    row_keys = {"reference", "media_type", "file", "origin_reference", "analysis_basis_reference",
                "synthetic", "reuse_permission_reference", "expected_sha256"}
    for row in rows:
        if type(row) is not dict or set(row) != row_keys or type(row["file"]) is not str:
            raise OperationsDenied("L2_INPUT_MANIFEST_SHAPE")
        relative = Path(row["file"])
        if relative.anchor or PureWindowsPath(row["file"]).anchor or ".." in relative.parts or ".." in PureWindowsPath(row["file"]).parts:
            raise OperationsDenied("L2_SOURCE_PATH_ESCAPE")
        file = (root / relative).resolve(strict=True)
        if not file.is_relative_to(root) or not file.is_file():
            raise OperationsDenied("L2_SOURCE_PATH_ESCAPE")
        with file.open("rb") as stream:
            raw = stream.read(2_000_001)
        evidence = EvidenceInput(row["reference"], row["media_type"], raw, row["origin_reference"],
                                 row["analysis_basis_reference"], row["synthetic"],
                                 row["reuse_permission_reference"])
        if row["expected_sha256"] is not None and digest(row["expected_sha256"]) != evidence.descriptor()["sha256"]:
            raise OperationsDenied("L2_SOURCE_HASH_MISMATCH")
        inputs.append(evidence)
    return SourceBundle(manifest["tenant_id"], manifest["bundle_id"], manifest["access_mode"],
                        tuple(inputs), manifest["external_run_permission_reference"])
