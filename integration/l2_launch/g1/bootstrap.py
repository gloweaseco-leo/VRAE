"""Trusted new-run provisioning. Source templates are input, NEVER task results."""

import base64
import json
from pathlib import Path
import secrets
from types import SimpleNamespace

from psycopg import sql
from psycopg.types.json import Jsonb
from vrae.l2_ops.sources import EvidenceInput, SourceBundle
from vrae.l2_ops.native_input import load_native
from integration.l2_launch.g1.sources import KINDS, policy_document, input_plan, admission

ROOT = Path(__file__).resolve().parents[3]


def serialize(plan):
    return {
        "kind": plan.kind,
        "ref": plan.ref,
        "policy": plan.policy,
        "audit": plan.audit,
        "pack_ref": plan.native.pack.ref,
        "template_run": plan.native.pack.document["run_id"],
        "bundle_id": plan.bundle.bundle_id,
        "inputs": [
            {
                "reference": i.reference,
                "media_type": i.media_type,
                "raw": base64.b64encode(i.raw).decode(),
                "origin_reference": i.origin_reference,
                "analysis_basis_reference": i.analysis_basis_reference,
                "synthetic": i.synthetic,
            }
            for i in plan.bundle.inputs
        ],
    }


def hydrate(value):
    bundle = SourceBundle(
        "tenant-test",
        value["bundle_id"],
        "OFFLINE_SYNTHETIC",
        tuple(
            EvidenceInput(
                i["reference"],
                i["media_type"],
                base64.b64decode(i["raw"], validate=True),
                i["origin_reference"],
                i["analysis_basis_reference"],
                i["synthetic"],
            )
            for i in value["inputs"]
        ),
    )
    native = load_native(
        bundle,
        value["inputs"][0]["reference"],
        expected_pack_ref=value["pack_ref"],
        expected_capture_run_id=value["template_run"],
    )
    return SimpleNamespace(
        kind=value["kind"],
        ref=value["ref"],
        policy=value["policy"],
        audit=value["audit"],
        bundle=bundle,
        native=native,
    )


def install(lab):
    from integration.ra4a import support as old
    from integration.ra4b.support import migrate, seed
    from integration.beta_review.codex3.m3_bootstrap import install as m1_install

    migrate()
    seed()
    m1_install(lab)
    state = json.loads(old.STATE.read_bytes())
    password = secrets.token_urlsafe(32)
    with lab.connect() as c:
        c.execute(
            sql.SQL(
                "CREATE ROLE g1_http_a LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB PASSWORD {}"
            ).format(sql.Literal(password))
        )
        c.execute((ROOT / "infra/l2_g1/metadata.sql").read_text(encoding="utf-8"))
        expiry = c.execute(
            "SELECT expires_at FROM ra4a.policies WHERE tenant_id='tenant-test'"
        ).fetchone()[0]
    policy = policy_document(expiry.isoformat())
    plans = {}
    for kind in KINDS:
        plan = input_plan(kind, policy)
        reference, raw = admission(plan)
        with lab.connect() as c, c.transaction():
            keys = list(reference)
            c.execute(
                sql.SQL("INSERT INTO ra4a.references ({}) VALUES ({})").format(
                    sql.SQL(",").join(map(sql.Identifier, keys)),
                    sql.SQL(",").join(sql.Placeholder() for _ in keys),
                ),
                [Jsonb(reference[k]) if k == "metadata" else reference[k] for k in keys],
            )
            c.execute(
                "INSERT INTO ra4b_p2.m1_inputs(tenant_id,source_ref,reference_sha256,source_record,policy_document,audit_document,reviewer_role) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    "tenant-test",
                    plan.ref,
                    reference["ref_sha256"],
                    raw,
                    Jsonb(policy),
                    Jsonb(plan.audit),
                    "p2b1_test_a_reviewer",
                ),
            )
            document = serialize(plan)
            c.execute(
                "INSERT INTO g1_http.sourceplans VALUES(%s,%s,%s)",
                (plan.ref, "tenant-test", Jsonb(document)),
            )
            assert c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone() == (0,)
        plans[kind] = {
            "source_ref": plan.ref,
            "binding": {
                "sha256": reference["ref_sha256"],
                "policy_id": "pol-001",
                "policy_version": 1,
            },
            "input_template_pack_ref": plan.native.pack.ref,
            "source_bundle_sha256": plan.bundle.document()["content_sha256"],
        }
    state["runtime_passwords"]["g1_http_a"] = password
    state["g1_plans"] = plans
    old.STATE.write_text(json.dumps(state))
    old.STATE.chmod(0o600)
    return state
