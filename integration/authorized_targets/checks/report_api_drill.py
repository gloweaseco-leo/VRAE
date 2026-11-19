"""Actual TLS/PG report operations on newly COMMITted controlled captures."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import ssl
import time

from contracts.l2_launch.contract import canonical
from integration.authorized_targets.report_api import BASE, MEDIA
from integration.authorized_targets.authority import token_hash
from integration.l2.support import Issuer
from integration.l2_launch.g1 import supervisor as process


def run(admin, rows, reviewers, app_bindings, tls, state):
    tenant, _, job, original_sha, raw, _ = rows[0]
    job = str(job)
    original = json.loads(raw)
    rid = original["version"]["report_id"]
    issuer = Issuer()
    names = {"owner": "OWNER", "reviewer": "REVIEWER", "reader-a": "READER", "reader-b": "READER"}
    people = [
        {
            "actor_id": n,
            "subject": n,
            "name": "Controlled " + n,
            "tenant_id": tenant,
            "role": role,
            "report_ids": [rid],
        }
        for n, role in names.items()
    ]
    secrets_by_tenant = {b["tenant_id"]: secrets.token_urlsafe(32) for b in reviewers}
    bindings = [
        {**b, "service_sha256": token_hash(secrets_by_tenant[b["tenant_id"]])} for b in reviewers
    ]
    app_secret = secrets.token_urlsafe(32)
    bindings.append({**app_bindings[0], "service_sha256": token_hash(app_secret)})
    directory = {
        "issuer": issuer.issuer,
        "audience": issuer.audience,
        "jwks": issuer.jwks,
        "expires": time.time() + 3600,
        "mode": "CONTROLLED",
        "people": people,
    }
    root = Path("/evidence/report-authority-ledger")
    root.mkdir(mode=0o700)
    os.chown(root, 10001, 10001)
    config = {
        "kind": "APP",
        "authority": "AUTHORIZED_TARGET_V1",
        "bindings": bindings,
        "source_sha": state["g1_source_sha"],
        "report_directory": directory,
        "ledger_root": str(root),
        "max_inflight": 1,
    }
    cfg = process.provision("report-api", 10001, config, tls["facade"])
    child, log = process.spawn(
        "report-api", 10001, cfg, "integration.authorized_targets.report_api"
    )
    context = ssl.create_default_context(cafile=tls["ca"])
    events = []
    checks = []

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    def call(label, method, path, body=None, *, sid=None, headers=None, expected=200, service=None):
        h = {
            "Origin": "https://127.0.0.1:8770",
            "Accept": MEDIA,
            "Content-Type": MEDIA,
            "Authorization": "Bearer " + (service or secrets_by_tenant[tenant]),
        }
        if sid:
            h["X-Report-Session"] = sid
        h.update(headers or {})
        c = http.client.HTTPSConnection("127.0.0.1", 8770, context=context, timeout=15)
        start = time.monotonic()
        try:
            c.connect()
            check(
                hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()
                == tls["facade"]["der_sha256"],
                label + " TLS pin",
            )
            c.request(method, path, None if body is None else canonical(body), h)
            response = c.getresponse()
            data = response.read(2_000_001)
            check(len(data) <= 2_000_000, label + " bounded response")
            check(
                response.getheader("Content-Type") == MEDIA
                and response.getheader("X-VRAE-Source-SHA") == state["g1_source_sha"],
                label + " profile source",
            )
            check("no-store" in response.getheader("Cache-Control", ""), label + " no store")
            events.append(
                {
                    "probe_id": label,
                    "http_status": response.status,
                    "expected_status": expected,
                    "response_sha256": hashlib.sha256(data).hexdigest(),
                    "elapsed_seconds": round(time.monotonic() - start, 6),
                }
            )
            check(response.status == expected, label + " HTTP status")
            return json.loads(data)
        finally:
            c.close()
            # A Content-Length response can reach the client while the held PG
            # context is finishing its final authority replay. Capacity=1 is
            # deliberate in this drill. Wait for that real transaction to finish
            # before the next isolated assertion; never retry the assertion.
            if label != "bounded report capacity":
                role = next(b["role"] for b in reviewers if b["tenant_id"] == tenant)

                def idle():
                    admin.execute("SELECT pg_stat_clear_snapshot()")
                    return (
                        admin.execute(
                            "SELECT count(*) FROM pg_stat_activity WHERE usename=%s AND xact_start IS NOT NULL",
                            (role,),
                        ).fetchone()[0]
                        == 0
                    )

                process.wait(idle)
                time.sleep(0.02)

    def login(subject):
        challenge = call(subject + " challenge", "POST", BASE + "/challenge", {})
        return call(
            subject + " signed login",
            "POST",
            BASE + "/session",
            {
                "responsible_bearer": issuer.token(subject, challenge["nonce"]),
                "nonce": challenge["nonce"],
                "csrf": challenge["csrf"],
            },
        )["report_session"]

    path = BASE + "/jobs/" + job

    def action(sid, operation, view, body, *, expected=200, label=None, token=None):
        if token is None:
            token = call(
                operation + " action", "POST", path + "/actions", {"operation": operation}, sid=sid
            )["action_token"]
        return call(
            label or operation,
            "POST",
            path + "/" + operation,
            body,
            sid=sid,
            headers={"If-Match": '"' + view["display_hash"] + '"', "X-Report-Action": token},
            expected=expected,
        )

    def approval(view):
        doc = view["report"]
        return {
            "action": "APPROVE",
            "reason": "Controlled source and UNKNOWN check, not formal human approval",
            "items": {x["id"]: "ACK" for x in doc["findings"] + doc["blueprint"]},
            "attest": True,
        }

    try:
        process.wait(lambda: b"REPORT_AUTHORITY_HTTPS_READY" in log.read_bytes())
        call("health", "GET", BASE + "/health")
        call("bad service", "GET", BASE + "/health", service="not-authorized", expected=403)
        call(
            "APP cannot use REVIEW service",
            "GET",
            BASE + "/health",
            service=app_secret,
            expected=403,
        )
        sids = {n: login(n) for n in names}
        call("service alone cannot read", "GET", path + "/report", expected=403)
        view = call("reviewer committed report", "GET", path + "/report", sid=sids["reviewer"])
        check(
            view["display_hash"] == original["display_hash"]
            and view["report_version"] == original["version"],
            "exact committed original pins",
        )
        check(
            view["report"]["native_context"]["native_pack_ref"]
            == original["native_document"]["native_context"]["native_pack_ref"],
            "same committed EvidencePack",
        )
        check(any(x["kind"] == "UNKNOWN" for x in view["report"]["findings"]), "UNKNOWN retained")
        check(
            view["external_release"] is False and view["formal_human_review"] is False,
            "controlled report never formal release",
        )
        other_job = str(next(r[2] for r in rows if str(r[2]) != job and r[0] == tenant))
        call(
            "different report scope denied",
            "GET",
            BASE + "/jobs/" + other_job + "/report",
            sid=sids["reviewer"],
            expected=403,
        )
        other_tenant = next(t for t in secrets_by_tenant if t != tenant)
        call(
            "cross tenant session denied",
            "GET",
            path + "/report",
            sid=sids["reviewer"],
            service=secrets_by_tenant[other_tenant],
            expected=403,
        )
        call(
            "stale report pin",
            "GET",
            path + "/report",
            sid=sids["reviewer"],
            headers={"If-Match": '"' + "0" * 64 + '"'},
            expected=409,
        )
        call(
            "reader without directed grant denied",
            "GET",
            path + "/report",
            sid=sids["reader-a"],
            expected=403,
        )
        token = call(
            "one use decision action",
            "POST",
            path + "/actions",
            {"operation": "decisions"},
            sid=sids["reviewer"],
        )["action_token"]
        receipt = action(sids["reviewer"], "decisions", view, approval(view), token=token)
        check(receipt["receipt"]["formal_human_review"] is False, "synthetic review not human")
        action(
            sids["reviewer"],
            "decisions",
            view,
            approval(view),
            token=token,
            expected=403,
            label="action replay denied",
        )
        action(
            sids["reviewer"],
            "grants",
            view,
            {"recipient_id": "reader-a", "ttl": 300},
            expected=403,
            label="reviewer cannot issue Owner grant",
        )
        grant = action(sids["owner"], "grants", view, {"recipient_id": "reader-a", "ttl": 300})
        gh = {"X-Report-Grant": grant["grant"]["grant_id"], "X-Report-Token": grant["access_token"]}
        call(
            "directed reader current report",
            "GET",
            path + "/report",
            sid=sids["reader-a"],
            headers=gh,
        )
        call(
            "other recipient denied",
            "GET",
            path + "/report",
            sid=sids["reader-b"],
            headers=gh,
            expected=403,
        )
        action(sids["owner"], "revocations", view, {"grant_id": grant["grant"]["grant_id"]})
        call(
            "revoked grant denied",
            "GET",
            path + "/report",
            sid=sids["reader-a"],
            headers=gh,
            expected=403,
        )
        grant = action(sids["owner"], "grants", view, {"recipient_id": "reader-a", "ttl": 300})
        gh = {"X-Report-Grant": grant["grant"]["grant_id"], "X-Report-Token": grant["access_token"]}
        changes = {
            view["report"]["blueprint"][0][
                "id"
            ]: "Controlled revision: verify buyer input against retained source."
        }
        revision = action(sids["reviewer"], "revisions", view, {"changes": changes})
        check(
            revision["report_version"]["version"] == 2 and revision["review_required"],
            "revision requires current review",
        )
        call(
            "old review cannot release revision",
            "GET",
            path + "/report",
            sid=sids["reader-a"],
            headers=gh,
            expected=403,
        )
        action(
            sids["reviewer"],
            "decisions",
            view,
            approval(view),
            expected=409,
            label="old version decision denied",
        )
        updated = call("current revision read", "GET", path + "/report", sid=sids["reviewer"])
        check(
            updated["report"]["findings"] == view["report"]["findings"]
            and updated["report"]["evidence"] == view["report"]["evidence"],
            "revision cannot rewrite source facts",
        )
        action(sids["reviewer"], "decisions", updated, approval(updated))
        call(
            "old grant cannot read newly reviewed version",
            "GET",
            path + "/report",
            sid=sids["reader-a"],
            headers=gh,
            expected=409,
        )
        grant = action(sids["owner"], "grants", updated, {"recipient_id": "reader-a", "ttl": 300})
        gh = {"X-Report-Grant": grant["grant"]["grant_id"], "X-Report-Token": grant["access_token"]}
        call(
            "new grant reads reviewed revision",
            "GET",
            path + "/report",
            sid=sids["reader-a"],
            headers=gh,
        )
        history = call("review history", "GET", path + "/history", sid=sids["reviewer"])
        check(
            len(history["versions"]) == 2 and len(history["decisions"]) == 2,
            "original durable version and decision history",
        )
        # Process replacement retains original ledger versions; old in-memory
        # responsible sessions deliberately require fresh signed authentication.
        process.stop(child)
        child, log = process.spawn(
            "report-api-restarted", 10001, cfg, "integration.authorized_targets.report_api"
        )
        process.wait(lambda: b"REPORT_AUTHORITY_HTTPS_READY" in log.read_bytes())
        call(
            "old session after restart denied",
            "GET",
            path + "/report",
            sid=sids["reviewer"],
            expected=403,
        )
        sids["reviewer"] = login("reviewer")
        restored = call(
            "durable revision after restart", "GET", path + "/report", sid=sids["reviewer"]
        )
        check(
            restored["display_hash"] == updated["display_hash"],
            "restart retains current version pins",
        )

        # Actual original row lock: first read waits; resource capacity returns
        # safe 429; bounded PG lock failure returns safe 503, with no fake result.
        def waiting_for_lock():
            admin.execute("SELECT pg_stat_clear_snapshot()")
            return (
                admin.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' AND usename=%s",
                    (next(b["role"] for b in reviewers if b["tenant_id"] == tenant),),
                ).fetchone()[0]
                > 0
            )

        with admin.transaction():
            admin.execute(
                "SELECT artifact_sha256 FROM target_v1.results WHERE tenant_id=%s AND job_id=%s FOR UPDATE",
                (tenant, job),
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(
                    call,
                    "bounded PG unavailable",
                    "GET",
                    path + "/report",
                    sid=sids["reviewer"],
                    expected=503,
                )
                process.wait(waiting_for_lock)
                call("bounded report capacity", "GET", BASE + "/health", expected=429)
                pending.result(timeout=10)
        call("PG lock recovery", "GET", path + "/report", sid=sids["reviewer"])
        admin.execute(
            "UPDATE target_v1.invitations SET revoked=true WHERE tenant_id=%s AND reference=(SELECT invitation_ref FROM target_v1.bindings WHERE tenant_id=%s AND request_id=(SELECT request_id FROM ra4a.jobs WHERE tenant_id=%s AND job_id=%s))",
            (tenant, tenant, tenant, job),
        )
        call(
            "current source invitation revoked",
            "GET",
            path + "/report",
            sid=sids["reviewer"],
            expected=403,
        )
        # Restore only this controlled fixture to leave the accepted base drill
        # independent. This is not a customer reauthorization route.
        admin.execute(
            "UPDATE target_v1.invitations SET revoked=false WHERE tenant_id=%s AND reference=(SELECT invitation_ref FROM target_v1.bindings WHERE tenant_id=%s AND request_id=(SELECT request_id FROM ra4a.jobs WHERE tenant_id=%s AND job_id=%s))",
            (tenant, tenant, tenant, job),
        )
        check(
            admin.execute(
                "SELECT artifact_sha256 FROM target_v1.results WHERE tenant_id=%s AND job_id=%s",
                (tenant, job),
            ).fetchone()[0]
            == original_sha,
            "PG original COMMIT immutable",
        )
    finally:
        process.stop(child)
        process.write(
            Path("/evidence/report-api.json"),
            {
                "contract": "vrae.report-authority.drill.v1",
                "source_sha": state["g1_source_sha"],
                "checks": checks,
                "http": events,
                "customer_release": False,
                "formal_human_review": False,
                "model_calls": 0,
                "real_customer_network": False,
            },
        )
