"""Content-addressed in-memory bundle. No implicit disk persistence or public storage."""
from dataclasses import dataclass
import hashlib
import json

from . import VERSION
from .errors import CollectionError
from .policy import SourceAccess


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def document_hash(document: dict) -> str:
    return sha256(json.dumps(document, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode())


@dataclass
class CaptureBundle:
    manifest: dict
    objects: dict[str, bytes]

    def verify(self):
        from .contracts import validate_document
        validate_document("CaptureManifest", self.manifest)
        doc = {k: v for k, v in self.manifest.items() if k != "manifest_sha256"}
        if document_hash(doc) != self.manifest["manifest_sha256"]:
            raise CollectionError("EVIDENCE_INTEGRITY")
        referenced = set()
        ids = set()
        for page in self.manifest["pages"]:
            snapshot = page["snapshot"]
            if snapshot["tenant_id"] != doc["tenant_id"] or snapshot["run_id"] != doc["run_id"]:
                raise CollectionError("EVIDENCE_INTEGRITY")
            if (snapshot["policy_id"] != doc["policy_id"]
                    or snapshot["policy_version"] != doc["policy_version"]):
                raise CollectionError("EVIDENCE_INTEGRITY")
            if snapshot["snapshot_id"] in ids:
                raise CollectionError("EVIDENCE_INTEGRITY")
            ids.add(snapshot["snapshot_id"])
            ref = snapshot["private_object_ref"]
            if page["raw_retained"] != (ref is not None):
                raise CollectionError("EVIDENCE_INTEGRITY")
            if ref is not None:
                referenced.add(ref)
                if (ref not in self.objects or sha256(self.objects[ref]) != snapshot["sha256"]
                        or len(self.objects[ref]) != page["bytes"]):
                    raise CollectionError("EVIDENCE_INTEGRITY")
            evidence = page["evidence"]
            if snapshot["status"] == "FETCHED":
                if (evidence is None or page["http_status"] != 200 or page["error"] is not None
                        or page["bytes"] == 0 or not page["redirect_trace"]
                        or page["redirect_trace"][-1]["url"] != snapshot["final_url"]
                        or page["redirect_trace"][-1]["status"] != 200):
                    raise CollectionError("EVIDENCE_INTEGRITY")
            elif evidence is not None or page["error"] is None:
                raise CollectionError("EVIDENCE_INTEGRITY")
            if evidence is not None and any((
                evidence["snapshot_id"] != snapshot["snapshot_id"],
                evidence["tenant_id"] != doc["tenant_id"], evidence["run_id"] != doc["run_id"],
                evidence["checksum"] != snapshot["sha256"], snapshot["status"] != "FETCHED",
                evidence["certainty"] != "OBSERVED", evidence["observed_at"] != snapshot["captured_at"],
            )):
                raise CollectionError("EVIDENCE_INTEGRITY")
        if referenced != set(self.objects):
            raise CollectionError("EVIDENCE_INTEGRITY")


def page_record(access: SourceAccess, run_id: str, url: str, role: str, *,
                response=None, trace=None, error: CollectionError | None = None,
                retain_raw: bool = False) -> tuple[dict, dict[str, bytes]]:
    stamp = access.now().isoformat()
    identity = document_hash({"tenant": access.audit["tenant_id"], "run": run_id, "url": url})
    digest = sha256(response.body) if response is not None and error is None else None
    snapshot = {"schema_version": "1.0", "tenant_id": access.audit["tenant_id"],
        "snapshot_id": "snap-" + identity, "run_id": run_id,
        "policy_id": access.audit["source_policy_ref"],
        "policy_version": access.audit["source_policy_version"], "url": url,
        "final_url": response.url if response is not None else None,
        "captured_at": stamp, "capture_mode": "HTTP", "sha256": digest,
        "private_object_ref": "body-" + digest if digest and retain_raw else None,
        "status": "FETCHED" if digest else ("ACCESS_BLOCKED" if error and error.code in (
            "ACCESS_BLOCKED", "ROBOTS_DISALLOWED", "SOURCE_NOT_ALLOWED", "POLICY_REVOKED",
            "POLICY_EXPIRED") else "UNKNOWN")}
    evidence = None
    if digest:
        evidence = {"schema_version": "1.0", "tenant_id": snapshot["tenant_id"],
            "evidence_id": "ev-" + identity, "run_id": run_id,
            "snapshot_id": snapshot["snapshot_id"], "locator": "http-response-body",
            "excerpt": None, "certainty": "OBSERVED", "checksum": digest, "observed_at": stamp}
    objects = {snapshot["private_object_ref"]: response.body} if digest and retain_raw else {}
    return {"snapshot": snapshot, "evidence": evidence, "role": role,
        "http_status": response.status if response is not None else None,
        "redirect_trace": trace or [], "bytes": len(response.body) if response else 0,
        "raw_retained": bool(objects), "error": error.document() if error else None}, objects


def seal(access: SourceAccess, run_id: str, pages: list[dict], objects: dict[str, bytes],
         items: list[dict], budget, robots: dict, errors: list[dict], truncated: bool) -> CaptureBundle:
    from .discovery import ROLES
    from .contracts import validate_document
    validate_document("PageInventory", {"schema_version": "1.0", "items": items, "truncated": truncated})
    covered = sorted({p["role"] for p in pages if p["snapshot"]["status"] == "FETCHED"})
    result = {"schema_version": "1.0", "tenant_id": access.audit["tenant_id"], "run_id": run_id,
        "audit_id": access.audit["audit_id"], "policy_id": access.audit["source_policy_ref"],
        "policy_version": access.audit["source_policy_version"], "terms_reference": access.terms_reference,
        "collector_version": VERSION, "rules_version": "http-evidence-1.0.0",
        "pages": pages, "inventory": items, "robots": robots, "errors": errors,
        "requests": budget.requests, "received_body_bytes": budget.bytes,
        "coverage": {"observed_roles": covered, "unverified_roles": sorted(set(ROLES) - set(covered)),
                     "inventory_truncated": truncated,
                     "note": "Unvisited or blocked pages do not prove absence or website defects."}}
    result["manifest_sha256"] = document_hash(result)
    bundle = CaptureBundle(result, objects)
    bundle.verify()
    return bundle
