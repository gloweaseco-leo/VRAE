"""Bootstrap a new immutable synthetic input; never seed a Worker result.

The legacy admission reference is a source-bound, zero-issue coverage preview,
not an L2 report. Its complete bytes are independently replayed before INSERT.
"""
import base64

from psycopg import sql
from psycopg.types.json import Jsonb

from tests.collection.test_security import fixture
from vrae.findings import build_findings
from vrae.persistence.contracts import frozen_reference
from vrae.reporting import build_draft
from vrae.reporting.common import VERSION, digest
from vrae.reporting.renderer import RENDERER_VERSION
from vrae.reviewing import SyntheticTrust
from vrae.reviewing.canonical import SOURCE_LIMIT, canonical, sha
from vrae.rules import execute

SOURCE_REF = "l2-industrial-native-v1"


def admission(native, *, source_ref=SOURCE_REF):
    from .source_profiles import SOURCE_REFS
    assert source_ref in SOURCE_REFS
    pack = native.pack
    scope = {k: pack.document[k] for k in ("tenant_id", "run_id", "policy_id", "policy_version")}
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version="ra2b6-1.0.0")
    pins = {"expected_pack_ref": pack.ref, "expected_execution_ref": execution["execution_ref"],
            "expected_builder_version": "ra2c3-1.0.0", "expected_evaluator_version": "ra2b6-1.0.0"}
    package = build_findings(pack, execution, **pins)
    metadata = {"report_id": "l2-industrial-input-coverage-v1" if source_ref == SOURCE_REF else source_ref + "-input-coverage", "version": 1,
                "created_at": pack.document["sources"][0]["document"]["pages"][0]["snapshot"]["captured_at"],
                "created_by": "c3-synthetic-input-bootstrap", "mode": "SYNTHETIC_PRIVATE_PREVIEW",
                "finding_selection": None}
    pins.update(expected_package_ref=package.ref, expected_scope=scope,
                expected_guard_version="ra3b-1.0.0", expected_guard_refs=[],
                expected_metadata_sha256=digest(metadata), expected_reporting_version=VERSION,
                expected_renderer_version=RENDERER_VERSION)
    draft = build_draft(pack, package, [], metadata, **pins)
    if draft.document["issues"] or draft.document["native_report_version"] is not None:
        raise ValueError("L2_INPUT_MUST_BE_NEUTRAL_COVERAGE")
    source = canonical({"pack": pack.document, "package": package.document, "guard_inputs": [],
        "metadata": metadata, "objects_base64": {k: base64.b64encode(v).decode() for k, v in pack.objects.items()}}, limit=SOURCE_LIMIT)
    held = {"pins": pins, "expected_draft_ref": draft.ref, "expected_html_sha256": sha(draft.html_bytes),
            "expected_issue_count": 0, "expected_payload_sha256": sha(draft._payload), "expected_source_sha256": sha(source)}
    policy = {"kind": "TEST_ONLY_POLICY_SNAPSHOT", "scope": scope,
              "allowed_purpose": "OFFLINE_REVIEW_SIMULATION", "current_authorization": "NOT_IMPLEMENTED"}
    artifact = f"synthetic-object://{scope['tenant_id']}/{metadata['report_id']}/v1/{sha(draft.html_bytes)}"
    trust = SyntheticTrust("TEST_ONLY_ACCEPTED_SYNTHETIC_SOURCE", canonical(held), canonical(policy), artifact)
    reference = frozen_reference(source_ref, draft._payload, draft.html_bytes, source, trust=trust)
    return reference, source


def install(lab, native, *, source_ref=SOURCE_REF):
    reference, raw = admission(native, source_ref=source_ref)
    with lab.connect(dbname="vrae_ra4a_p1") as c, c.transaction():
        before = c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone()[0]
        keys = list(reference)
        c.execute(sql.SQL("INSERT INTO ra4a.references ({}) VALUES ({})").format(
            sql.SQL(",").join(map(sql.Identifier, keys)), sql.SQL(",").join(sql.Placeholder() for _ in keys)),
            [Jsonb(reference[k]) if k == "metadata" else reference[k] for k in keys])
        expiry = c.execute("SELECT expires_at FROM ra4a.policies WHERE(tenant_id,policy_id,version)=(%s,%s,%s)",
            (reference["tenant_id"], reference["policy_id"], reference["policy_version"])).fetchone()[0]
        policy, audit = fixture("SourcePolicy"), fixture("AuditRequest")
        policy.update(tenant_id=reference["tenant_id"], policy_id=reference["policy_id"],
            policy_version=reference["policy_version"], permitted_hosts=["example.org"], scope_paths=["/"],
            expires_at=expiry.isoformat(), revoked_at=None)
        audit.update(tenant_id=reference["tenant_id"], source_policy_ref=reference["policy_id"],
                     source_policy_version=reference["policy_version"])
        c.execute("INSERT INTO ra4b_p2.m1_inputs(tenant_id,source_ref,reference_sha256,source_record,policy_document,audit_document,reviewer_role) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (reference["tenant_id"], source_ref, reference["ref_sha256"], raw, Jsonb(policy), Jsonb(audit), "p2b1_test_a_reviewer"))
        assert c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (before,)
    return {"source_ref": source_ref, "source_record_sha256": sha(raw), "original_pack_ref": native.pack.ref,
            "reference_sha256": reference["ref_sha256"], "policy_expires_at": expiry.isoformat(), "seeded_worker_results": 0, "input_preview": "SYNTHETIC_NEUTRAL_COVERAGE_NOT_L2"}
