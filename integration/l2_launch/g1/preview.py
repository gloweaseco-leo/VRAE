"""Separately Owner-signed SYNTHETIC preview; standard report remains closed."""

from datetime import datetime, UTC
from psycopg.types.json import Jsonb
from contracts.l2_launch.contract import Refused
from integration.l2_launch.g1.fixture_keys import verifier
from integration.l2_launch.g1.projection import project
from integration.l2_launch.g1.storage import REALM_LOCK


def fixture(handler, method, ref, operation):
    store = handler.app.store
    with store.connect() as c, c.transaction():
        c.execute("SELECT pg_advisory_xact_lock_shared(%s)", (REALM_LOCK,))
        record = store.current_record(c, ref)
        with handler.app.flow.current(record) as current:
            _, pins = project(record, current)
            if method == "GET" and operation == "pins":
                return handler.send(200, pins)
            if method != "POST":
                raise Refused("FORBIDDEN_ROLE")
            body = handler.body()
            if operation == "review":
                if body != {"pins": pins, "action": "APPROVE_SYNTHETIC_ONLY"}:
                    raise Refused("REPORT_VERSION_STALE", 409)
                view = current.view
                receipt = current.ledger.review(
                    current.review_sid,
                    current.report_id,
                    version=view.version["version"],
                    content_hash=view.version["content_hash"],
                    display_hash=view.display_hash,
                    action="APPROVE",
                    reason="CONTROLLED synthetic fixture review only; no human approval.",
                    items={
                        item["id"]: "ACK"
                        for key in ("findings", "blueprint")
                        for item in view.document[key]
                    },
                    attest=True,
                )
                assert receipt["formal_human_review"] is False
                return handler.send(
                    200,
                    {
                        "synthetic_review": True,
                        "formal_human_review": False,
                        "external_release": False,
                    },
                )
            if operation == "preview-permit":
                if set(body) != {"document", "proof"}:
                    raise Refused("FORBIDDEN_ROLE")
                expected = {
                    "tenant_id": store.cfg["tenant"],
                    "audit_ref": ref,
                    "subject_ref": record["subject_ref"],
                    "purpose": "SYNTHETIC_PREVIEW_ONLY",
                    "pins": pins,
                }
                document = body["document"]
                if {k: v for k, v in document.items() if k != "expires_at"} != expected:
                    raise Refused("REPORT_VERSION_STALE", 409)
                if datetime.fromisoformat(document["expires_at"]) <= datetime.now(UTC):
                    raise Refused("FORBIDDEN_ROLE")
                verifier(store.realm(c)["keys"]).verify(
                    body["proof"], "share", document, store.cfg["tenant"], datetime.now(UTC)
                )
                c.execute(
                    "INSERT INTO g1_http.preview_permits VALUES(%s,%s,%s,%s,false) ON CONFLICT(audit_ref) DO UPDATE SET document=EXCLUDED.document,proof=EXCLUDED.proof,revoked=false",
                    (store.cfg["tenant"], ref, Jsonb(document), Jsonb(body["proof"])),
                )
                return handler.send(
                    201, {"synthetic_preview_permit": True, "real_share_grant": False}
                )
            raise Refused("FORBIDDEN_ROLE")


def preview(handler, ref):
    from integration.l2_launch.g1.http_server import COOKIE

    store = handler.app.store
    with store.connect() as c, c.transaction():
        c.execute("SELECT pg_advisory_xact_lock_shared(%s)", (REALM_LOCK,))
        record = store.session(
            c, ref, handler.cookies().get(COOKIE), handler.headers.get("X-G1-CSRF")
        )
        row = c.execute(
            "SELECT document,proof,revoked FROM g1_http.preview_permits WHERE audit_ref=%s FOR SHARE",
            (ref,),
        ).fetchone()
        if not row or row[2]:
            raise Refused("REPORT_NOT_APPROVED")
        document, proof, _ = row
        verifier(store.realm(c)["keys"]).verify(
            proof, "share", document, store.cfg["tenant"], datetime.now(UTC)
        )
        if (
            document["subject_ref"] != record["subject_ref"]
            or document["purpose"] != "SYNTHETIC_PREVIEW_ONLY"
            or datetime.fromisoformat(document["expires_at"]) <= datetime.now(UTC)
        ):
            raise Refused("FORBIDDEN_ROLE")
        with handler.app.flow.current(record) as current:
            result, pins = project(record, current)
            if pins != document["pins"] or handler.headers.get("If-Match") != pins["view_sha256"]:
                raise Refused("REPORT_VERSION_STALE", 409)
            # Authority and original M1 current-worker transaction remain held
            # until the bounded whitelisted response has been written.
            return handler.send(200, result, [("ETag", pins["view_sha256"])])
