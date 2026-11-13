"""Pure optional-PG contracts: no driver import, credential discovery or network."""

import hashlib
import json
import re

from vrae.reviewing import build_target


class PersistenceError(ValueError):
    pass


def production_port(*args, **kwargs):
    """Verified identity, object bytes and transactional human review are absent."""
    raise PersistenceError("RA4A_PRODUCTION_AUTH_OBJECT_REVIEW_NOT_IMPLEMENTED") from None


def admission_payload(source_ref=None, expected_ref_sha256=None):
    if source_ref is not None and (
        type(source_ref) is not str or not re.fullmatch(r"[a-zA-Z0-9_.-]{3,96}", source_ref)
    ):
        raise PersistenceError("RA4A_REFERENCE_INVALID")
    if (source_ref is None) != (expected_ref_sha256 is None) or (
        expected_ref_sha256 is not None
        and (
            type(expected_ref_sha256) is not str
            or not re.fullmatch("[0-9a-f]{64}", expected_ref_sha256)
        )
    ):
        raise PersistenceError("RA4A_REFERENCE_INVALID")
    raw = json.dumps(
        {
            "mode": "SYNTHETIC_INTERNAL_ONLY",
            "source_ref": source_ref,
            "expected_ref_sha256": expected_ref_sha256,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def frozen_reference(ref_id, document, html, source, *, trust):
    """Replay before migration-only fixture registration; never trust a naked row."""
    target = build_target(document, html, source, trust=trust)
    t = target.document
    return {
        "tenant_id": t["tenant_id"],
        "ref_id": ref_id,
        "policy_id": t["policy_id"],
        "policy_version": t["policy_version"],
        "report_id": t["report_id"],
        "source_run_id": t["run_id"],
        "report_version": t["report_version"],
        "kind": t["kind"],
        "issue_count": len(json.loads(document)["issues"]),
        "native_h0": t["native_content_hash"],
        "native_id": t["native_report_version_id"],
        "target_digest": target.target_digest,
        "ref_sha256": hashlib.sha256(target.payload).hexdigest(),
        "metadata": t,
    }
