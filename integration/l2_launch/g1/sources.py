"""Fresh G1 recorded input plans, not pre-generated task evidence or reports.

A neutral source template is required by the existing immutable admission seam.
Only the independent Worker collection with the PG-assigned run is task evidence.
No old P40 bundle, job, report, or signed authorization is reused.
"""

import asyncio
import base64
from datetime import datetime, UTC, timedelta
from types import SimpleNamespace
from urllib.parse import urlsplit

from integration.l2_launch.security.adapter import (
    OfflineWorker,
    OfflinePermit,
    RecordedResolver,
    RecordedTransport,
    TaskPins,
    fingerprint,
)
from tests.collection.test_security import fixture
from vrae.collection.limits import Limits
from vrae.collection.policy import SourceAccess
from vrae.evidence import build_pack
from vrae.findings import build_findings
from vrae.persistence.contracts import frozen_reference
from vrae.reporting import build_draft
from vrae.reporting.common import VERSION, digest
from vrae.reporting.renderer import RENDERER_VERSION
from vrae.reviewing import SyntheticTrust
from vrae.reviewing.canonical import SOURCE_LIMIT, canonical, sha
from vrae.rules import execute
from vrae.l2_ops.native_input import NativeInput
from vrae.l2_ops.sources import SourceBundle, EvidenceInput

KINDS = ("manufacturer", "distributor", "forbidden", "robots", "unknown", "deadletter")
HOSTS = tuple("g1-" + name + ".example" for name in KINDS)


def table(title, fields, links=""):
    rows = "".join("<tr><th>" + k + "</th><td>" + v + "</td></tr>" for k, v in fields)
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>'
        + title
        + "</title><main><h1>"
        + title
        + "</h1><table>"
        + rows
        + "</table>"
        + links
        + "</main></html>"
    ).encode()


def policy_document(expires):
    now = datetime.now(UTC)
    policy = fixture("SourcePolicy")
    policy.update(
        tenant_id="tenant-test",
        permitted_hosts=list(HOSTS),
        scope_paths=["/"],
        authorization_reference="g1-controlled-synthetic-permission-not-real-site-right",
        created_at=(now - timedelta(seconds=1)).isoformat(),
        expires_at=expires,
        revoked_at=None,
    )
    return policy


def routes(kind):
    assert kind in KINDS
    origin = "https://g1-" + kind + ".example"
    robot = b"User-agent: *\nDisallow:\n" if kind != "robots" else b"User-agent: *\nDisallow: /\n"
    result = {origin + "/robots.txt": (200, {"content-type": "text/plain"}, robot)}
    if kind in ("forbidden", "robots", "unknown", "deadletter"):
        result[origin + "/"] = (
            403 if kind == "forbidden" else 200,
            {"content-type": "text/html"},
            b""
            if kind == "forbidden"
            else b"<!doctype html><main><h1>Synthetic G1 access case</h1></main>",
        )
        return result
    category = (
        '<a href="/products/p40">Pump model P40</a><a href="/products/p80">Pump model P80</a>'
    )
    menu = '<a href="/products">Product category</a><a href="/products/duty-selection">Application duty</a><a href="/products/supplier-proof">Supplier proof</a><a href="/products/rfq-guide">RFQ guide</a><a href="/contact">Contact</a>'
    pages = {
        "/": table("SYNTHETIC G1 " + kind, [], menu),
        "/products": table("SYNTHETIC pump range", [], category),
    }
    for model, flow in (("P40", "40 m3/h"), ("P80", "80 m3/h")):
        pages["/products/" + model.lower()] = table(
            "SYNTHETIC " + kind + " " + model,
            [
                ("Record type", "Product"),
                ("Product family", "process water pump"),
                ("Model", model),
                ("Rated flow", flow),
                ("Rated head", "50 m"),
                ("Motor power", "5 kW"),
                ("Supply voltage", "400 V"),
                ("Supply frequency", "50 Hz"),
                ("Maximum working pressure", "10 bar"),
                ("Maximum fluid temperature", "80 degC"),
                ("Permitted medium", "clean water"),
            ],
            '<a href="/contact">Request technical quotation</a>',
        )
    pages["/products/duty-selection"] = table(
        "SYNTHETIC recorded duty",
        [
            ("Record type", "Application"),
            ("Applicable models", "P40, P80"),
            ("Required flow", "50 m3/h"),
            ("Required head", "30 m"),
            ("Required pressure", "6 bar"),
            ("Fluid temperature", "40 degC"),
            ("Available voltage", "400 V"),
            ("Available frequency", "50 Hz"),
            ("Process medium", "clean water"),
            ("Order quantity", "2"),
        ],
    )
    pages["/products/supplier-proof"] = table(
        "SYNTHETIC supplier declaration",
        [
            ("Record type", "Supplier proof"),
            ("Applicable models", "P40, P80"),
            ("Certificate issuer", "Synthetic example institution"),
            ("Certificate reference", "G1-DEMO-NOT-A-CERTIFICATE"),
            ("Certificate valid until", "2030-01-01"),
        ],
    )
    pages["/products/rfq-guide"] = table(
        "SYNTHETIC RFQ preparation",
        [
            ("Record type", "RFQ guide"),
            ("Applicable models", "P40, P80"),
            ("Required RFQ inputs", "Model, Order quantity, Delivery destination"),
        ],
    )
    pages["/contact"] = table(
        "SYNTHETIC contact context",
        [],
        "<p>No form is submitted. Delivery and conversion are UNKNOWN.</p>",
    )
    result.update(
        {origin + path: (200, {"content-type": "text/html"}, body) for path, body in pages.items()}
    )
    return result


def audit_document(kind, policy, *, request_id, audit_id):
    value = fixture("AuditRequest")
    value.update(
        tenant_id="tenant-test",
        request_id=request_id,
        audit_id=audit_id,
        site_url="https://g1-" + kind + ".example/",
        audit_mode="L1",
        source_policy_ref=policy["policy_id"],
        source_policy_version=policy["policy_version"],
        requested_at=datetime.now(UTC).isoformat(),
        source_reference="g1-recorded-" + kind,
    )
    return value


def capture(kind, policy, audit, run_id, *, recorded=None, task_seconds=10):
    """Original R1A OfflineWorker -> original Collector, with no network factory."""
    source = SourceAccess(audit, lambda: policy, terms_reference="G1_SYNTHETIC_RECORDED_ONLY")
    permit = OfflinePermit(
        "https://" + urlsplit(audit["site_url"]).hostname,
        tuple(urlsplit(url).path for url in routes(kind)),
        datetime.fromisoformat(policy["created_at"]),
        datetime.fromisoformat(policy["expires_at"]),
        True,
    )
    held = TaskPins(
        audit["tenant_id"],
        audit["request_id"],
        run_id,
        policy["policy_id"],
        policy["policy_version"],
        fingerprint(policy),
    )
    transport = RecordedTransport(
        routes(kind) if recorded is None else recorded,
        error="TIMEOUT" if kind == "unknown" else None,
    )
    worker = OfflineWorker(
        source,
        held=held,
        permit=permit,
        resolver=RecordedResolver(),
        transport=transport,
        limits=Limits(
            max_pages=8,
            interval_seconds=0.01,
            task_seconds=task_seconds,
            request_seconds=min(5, task_seconds),
        ),
    )
    result = asyncio.run(worker.capture(run_id))
    return (
        result,
        worker.access,
        {
            "recorded_calls": len(transport.calls),
            "dns_checks": len(worker.resolver.checks),
            "origin_sha256": fingerprint({"origin": permit.origin}),
            "target_network_attempts": 0,
        },
    )


def input_plan(kind, policy):
    """Trusted bootstrap template only; never a Worker COMMIT or report result."""
    audit = audit_document(kind, policy, request_id="g1-input-" + kind, audit_id="g1-input-" + kind)
    captured, _, _ = capture(kind, policy, audit, "g1-input-template-" + kind)
    pack = build_pack([captured])
    archive = canonical(
        {
            "pack": pack.document,
            "objects_base64": {k: base64.b64encode(v).decode() for k, v in pack.objects.items()},
        },
        limit=SOURCE_LIMIT,
    )
    evidence = EvidenceInput(
        "g1-input-plan-" + kind,
        "application/json",
        archive,
        "G1_NEW_SYNTHETIC_RECORDED_INPUT_PLAN_NOT_TASK_EVIDENCE",
        "INPUT_PLAN_NOT_DIAGNOSIS",
        True,
    )
    bundle = SourceBundle("tenant-test", "g1-new-" + kind, "OFFLINE_SYNTHETIC", (evidence,))
    native = NativeInput(pack, bundle.document()["content_sha256"], evidence.reference, ())
    return SimpleNamespace(
        kind=kind,
        ref="g1-recorded-" + kind,
        policy=policy,
        audit=audit,
        bundle=bundle,
        native=native,
    )


def admission(plan):
    """Original neutral source admission representation; no generated rows seeded."""
    pack = plan.native.pack
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version="ra2b6-1.0.0")
    pins = {
        "expected_pack_ref": pack.ref,
        "expected_execution_ref": execution["execution_ref"],
        "expected_builder_version": "ra2c3-1.0.0",
        "expected_evaluator_version": "ra2b6-1.0.0",
    }
    package = build_findings(pack, execution, **pins)
    metadata = {
        "report_id": "g1-input-coverage-" + plan.kind,
        "version": 1,
        "created_at": pack.document["sources"][0]["document"]["pages"][0]["snapshot"][
            "captured_at"
        ],
        "created_by": "g1-input-plan-bootstrap",
        "mode": "SYNTHETIC_PRIVATE_PREVIEW",
        "finding_selection": None,
    }
    pins.update(
        expected_package_ref=package.ref,
        expected_scope={
            k: pack.document[k] for k in ("tenant_id", "run_id", "policy_id", "policy_version")
        },
        expected_guard_version="ra3b-1.0.0",
        expected_guard_refs=[],
        expected_metadata_sha256=digest(metadata),
        expected_reporting_version=VERSION,
        expected_renderer_version=RENDERER_VERSION,
    )
    draft = build_draft(pack, package, [], metadata, **pins)
    assert not draft.document["issues"] and draft.document["native_report_version"] is None
    source = canonical(
        {
            "pack": pack.document,
            "package": package.document,
            "guard_inputs": [],
            "metadata": metadata,
            "objects_base64": {k: base64.b64encode(v).decode() for k, v in pack.objects.items()},
        },
        limit=SOURCE_LIMIT,
    )
    held = {
        "pins": pins,
        "expected_draft_ref": draft.ref,
        "expected_html_sha256": sha(draft.html_bytes),
        "expected_issue_count": 0,
        "expected_payload_sha256": sha(draft._payload),
        "expected_source_sha256": sha(source),
    }
    scope = pins["expected_scope"]
    snapshot = {
        "kind": "TEST_ONLY_POLICY_SNAPSHOT",
        "scope": scope,
        "allowed_purpose": "OFFLINE_REVIEW_SIMULATION",
        "current_authorization": "NOT_IMPLEMENTED",
    }
    trust = SyntheticTrust(
        "TEST_ONLY_ACCEPTED_SYNTHETIC_SOURCE",
        canonical(held),
        canonical(snapshot),
        "synthetic-object://"
        + scope["tenant_id"]
        + "/"
        + metadata["report_id"]
        + "/v1/"
        + sha(draft.html_bytes),
    )
    return frozen_reference(plan.ref, draft._payload, draft.html_bytes, source, trust=trust), source
