"""Two independent invited identities, signed verified-protocol test realm.

These isolated signing keys prove the production protocol, not actual customer
identity vetting or a real human signature. No customer source/delivery occurs.
"""

import base64
from datetime import datetime, UTC, timedelta
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from contracts.l2_launch.contract import canonical
from integration.authorized_targets.authority import token_hash
from integration.authorized_targets.store import connect
from integration.authorized_targets.checks.api_tls import create as pki
from integration.authorized_targets.report_api import BASE, MEDIA
from integration.authorized_targets.report_authority import TRUST, AUTHORITY
from integration.l2_launch.g1 import supervisor as process
from vrae.l2.verified import PROFILE, CURRENT_REPORTS


def b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def run(admin, rows, reviewers, state):
    tenant = rows[0][0]
    binding = next(b for b in reviewers if b["tenant_id"] == tenant)
    selected = []
    subjects = set()
    for row in rows:
        if row[0] == tenant:
            with connect(binding) as c, c.transaction():
                ctx = c.execute(
                    "SELECT target_v1.report_context(%s,%s)", (tenant, row[2])
                ).fetchone()[0]
            if ctx["recipient_subject"] not in subjects:
                subjects.add(ctx["recipient_subject"])
                selected.append((row, ctx))
    assert len(selected) >= 2
    selected = selected[:2]
    assert len({ctx["source_plan"]["target_id"] for _, ctx in selected}) == 2
    identity_key = Ed25519PrivateKey.generate()
    authority_key = Ed25519PrivateKey.generate()
    issuer = "https://verified-protocol-test.invalid"
    audience = "vrae-verified-report-test"
    kid = "isolated-test-mfa-key"
    now = datetime.now(UTC)
    people = [
        {
            "actor_id": role.lower(),
            "subject": role.lower(),
            "name": "Protocol test " + role,
            "tenant_id": tenant,
            "role": role,
            "report_ids": [CURRENT_REPORTS],
            "verification_ref": "TEST_PROTOCOL_NOT_ACTUAL_HUMAN-" + role,
        }
        for role in ("OWNER", "REVIEWER")
    ]
    for _, ctx in selected:
        s = ctx["recipient_subject"]
        people.append(
            {
                "actor_id": s,
                "subject": s,
                "name": "Invited protocol test subject",
                "tenant_id": tenant,
                "role": "READER",
                "report_ids": [CURRENT_REPORTS],
                "verification_ref": "TEST_PROTOCOL_NOT_ACTUAL_HUMAN-" + s,
            }
        )
    directory = {
        "issuer": issuer,
        "audience": audience,
        "jwks": {
            "keys": [
                {
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "use": "sig",
                    "alg": "EdDSA",
                    "kid": kid,
                    "x": b64(
                        identity_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
                    ),
                }
            ]
        },
        "mode": "VERIFIED_DIRECTORY",
        "expires": (now + timedelta(minutes=50)).timestamp(),
        "people": people,
    }
    doc = {
        "contract": "vrae.verified-report-authority.v1",
        "profile": PROFILE,
        "reference": "ISOLATED_SIGNED_IDENTITY_PROTOCOL_TEST_NOT_CUSTOMER_SIGNOFF",
        "allowed_source_classes": ["CONTROLLED_NON_CUSTOMER"],
        "not_before": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "directory": directory,
    }
    registry = {
        "keys": {
            "report-test-authority": {
                "role": "REPORT_AUTHORITY",
                "revoked": False,
                "public": authority_key.public_key()
                .public_bytes(Encoding.Raw, PublicFormat.Raw)
                .hex(),
            }
        }
    }
    TRUST.parent.mkdir(mode=0o750, exist_ok=True)
    os.chown(TRUST.parent, 0, 10007)

    def root_write(path, value):
        if path.exists():
            path.chmod(0o644)
        path.write_bytes(canonical(value))
        os.chown(path, 0, 10007)
        path.chmod(0o640)

    root_write(TRUST, registry)
    root_write(
        AUTHORITY,
        {
            "key_id": "report-test-authority",
            "document": doc,
            "signature": authority_key.sign(canonical(doc)).hex(),
        },
    )
    tls = pki(process.ROOT / "verified-report-tls")
    ca = TRUST.parent / "client-ca.pem"
    shutil.copyfile(tls["ca"], ca)
    ca.chmod(0o444)
    root = Path("/evidence/verified-report-ledger")
    root.mkdir(mode=0o700)
    os.chown(root, 10007, 10007)
    service = secrets.token_urlsafe(32)
    binding = next(b for b in reviewers if b["tenant_id"] == tenant)
    cfg = process.provision(
        "verified-report",
        10007,
        {
            "kind": "APP",
            "authority": "AUTHORIZED_TARGET_V1",
            "source_sha": state["g1_source_sha"],
            "report_profile": PROFILE,
            "ledger_root": str(root),
            "max_inflight": 4,
            "bindings": [
                {
                    **binding,
                    "service_sha256": token_hash(service),
                    "client_certificate_sha256": tls["client"]["der_sha256"],
                }
            ],
            "transport": {
                "bind": "127.0.0.1",
                "port": 8770,
                "hosts": ["127.0.0.1:8770"],
                "origins": ["https://127.0.0.1:8770"],
                "mtls": True,
                "client_ca": str(ca),
            },
        },
        tls["facade"],
    )
    child, log = process.spawn(
        "verified-report", 10007, cfg, "integration.authorized_targets.report_api"
    )
    context = ssl.create_default_context(cafile=tls["ca"])
    context.load_cert_chain(tls["client"]["certificate"], tls["client"]["key"])
    events = []
    checks = []
    completed = False
    failure = None

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    def call(label, method, path, body=None, sid=None, extra=None, expected=200, ctx=None):
        h = {
            "Authorization": "Bearer " + service,
            "Origin": "https://127.0.0.1:8770",
            "Accept": MEDIA,
            "Content-Type": MEDIA,
            "X-Report-Profile": PROFILE,
        }
        if sid:
            h["X-Report-Session"] = sid
        h.update(extra or {})
        c = http.client.HTTPSConnection("127.0.0.1", 8770, context=ctx or context, timeout=40)
        t = time.monotonic()
        try:
            c.connect()
            check(
                hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()
                == tls["facade"]["der_sha256"],
                label + " TLS pin",
            )
            c.request(method, path, None if body is None else canonical(body), h)
            r = c.getresponse()
            raw = r.read(2_000_001)
            check(len(raw) <= 2_000_000, label + " bound")
            events.append(
                {
                    "probe_id": label,
                    "http_status": r.status,
                    "expected": expected,
                    "response_sha256": hashlib.sha256(raw).hexdigest(),
                    "elapsed_seconds": round(time.monotonic() - t, 6),
                }
            )
            check(r.status == expected, label + " HTTP")
            check(
                r.getheader("X-VRAE-Scope") == PROFILE
                and r.getheader("X-VRAE-Source-SHA") == state["g1_source_sha"],
                label + " scope/source",
            )
            check("no-store" in r.getheader("Cache-Control", ""), label + " no-store")
            return json.loads(raw)
        finally:
            c.close()

            def idle():
                admin.execute("SELECT pg_stat_clear_snapshot()")
                return (
                    admin.execute(
                        "SELECT count(*) FROM pg_stat_activity WHERE usename=%s AND xact_start IS NOT NULL",
                        (binding["role"],),
                    ).fetchone()[0]
                    == 0
                )

            process.wait(idle)
            time.sleep(0.03)

    def login(subject, acr="VERIFIED_PERSON_MFA", expected=200, expired=False, bad_signature=False):
        ch = call(subject + " challenge", "POST", BASE + "/challenge", {})
        ts = int(time.time())
        header = {"alg": "EdDSA", "kid": kid, "typ": "vrae-responsible-review+jwt"}
        claims = {
            "iss": issuer,
            "aud": audience,
            "sub": subject,
            "iat": ts,
            "nbf": ts,
            "exp": ts - 1 if expired else ts + 300,
            "jti": secrets.token_urlsafe(24),
            "nonce": ch["nonce"],
            "acr": acr,
        }
        hp = ".".join(b64(canonical(x)) for x in (header, claims))
        signature = identity_key.sign(hp.encode())
        if bad_signature:
            signature = bytes([signature[0] ^ 1]) + signature[1:]
        bearer = "Bearer " + hp + "." + b64(signature)
        response = call(
            subject + " signed MFA login",
            "POST",
            BASE + "/session",
            {"responsible_bearer": bearer, "nonce": ch["nonce"], "csrf": ch["csrf"]},
            expected=expected,
        )
        return response.get("report_session")

    def mutate(label, path, sid, op, view, body, expected=200):
        a = call(label + " action", "POST", path + "/actions", {"operation": op}, sid)
        return call(
            label,
            "POST",
            path + "/" + op,
            body,
            sid,
            {"If-Match": '"' + view["display_hash"] + '"', "X-Report-Action": a["action_token"]},
            expected,
        )

    def approval(view):
        return {
            "action": "APPROVE",
            "reason": "Isolated signed protocol verification, not actual customer human signoff",
            "items": {
                x["id"]: "ACK" for x in view["report"]["findings"] + view["report"]["blueprint"]
            },
            "attest": True,
        }

    try:
        process.wait(lambda: b"REPORT_AUTHORITY_HTTPS_READY" in log.read_bytes())
        call("verified health", "GET", BASE + "/health")
        wrong_context = ssl.create_default_context(cafile=tls["ca"])
        wrong_context.load_cert_chain(
            tls["other-client"]["certificate"], tls["other-client"]["key"]
        )
        call("wrong bound mTLS service", "GET", BASE + "/health", ctx=wrong_context, expected=403)
        call(
            "missing verified profile",
            "GET",
            BASE + "/health",
            extra={"X-Report-Profile": ""},
            expected=406,
        )
        login("reviewer", "CONTROLLED_TEST_PERSON", 403)
        login("reviewer", expected=403, expired=True)
        login("reviewer", expected=403, bad_signature=True)
        sids = {p["subject"]: login(p["subject"]) for p in people}
        paths = [BASE + "/audits/" + ctx["audit_ref"] for _, ctx in selected]
        updated_views = []
        for i, (row, source_ctx) in enumerate(selected):
            if i:
                sids = {p["subject"]: login(p["subject"]) for p in people}
            who = source_ctx["recipient_subject"]
            other = selected[1 - i][1]["recipient_subject"]
            path = paths[i]
            view = call(
                "reviewer reads committed " + str(i), "GET", path + "/report", sid=sids["reviewer"]
            )
            original = json.loads(row[4])
            check(view["display_hash"] == original["display_hash"], "original view hash " + str(i))
            check(
                any(x["kind"] == "UNKNOWN" for x in view["report"]["findings"]),
                "UNKNOWN retained " + str(i),
            )
            call(
                "unreviewed reader denied " + str(i),
                "GET",
                path + "/report",
                sid=sids[who],
                expected=403,
            )
            review = mutate(
                "Reviewer approval " + str(i),
                path,
                sids["reviewer"],
                "decisions",
                view,
                approval(view),
            )
            check(
                review["receipt"]["formal_human_review"] is True
                and review["receipt"]["directory_mode"] == "VERIFIED_DIRECTORY",
                "signed verified protocol receipt " + str(i),
            )
            # Reviewer approval is sufficient; Owner does not re-approve content.
            grant = mutate(
                "directed grant " + str(i),
                path,
                sids["owner"],
                "grants",
                view,
                {"recipient_id": who, "ttl": 300},
            )
            gh = {
                "X-Report-Grant": grant["grant"]["grant_id"],
                "X-Report-Token": grant["access_token"],
            }
            released = call(
                "own released report " + str(i), "GET", path + "/report", sid=sids[who], extra=gh
            )
            check(
                released["external_release"]
                and released["formal_human_review"]
                and released["report_version"]["status"] == "APPROVED",
                "verified customer envelope " + str(i),
            )
            check(
                released["review_decision"]["reviewer_id"] == "reviewer",
                "no Owner content reapproval " + str(i),
            )
            call(
                "wrong invited subject denied " + str(i),
                "GET",
                path + "/report",
                sid=sids[other],
                extra=gh,
                expected=403,
            )
            mutate(
                "wrong recipient grant denied " + str(i),
                path,
                sids["owner"],
                "grants",
                view,
                {"recipient_id": other, "ttl": 300},
                403,
            )
            call(
                "stale pin denied " + str(i),
                "GET",
                path + "/report",
                sid=sids["reviewer"],
                extra={"If-Match": '"' + "0" * 64 + '"'},
                expected=409,
            )
            proposal = {
                view["report"]["blueprint"][0][
                    "id"
                ]: "Revised proposal; original evidence and UNKNOWN retained."
            }
            revision = mutate(
                "revision " + str(i),
                path,
                sids["reviewer"],
                "revisions",
                view,
                {"changes": proposal},
            )
            check(
                revision["review_required"] and revision["external_release"] is False,
                "revision not published " + str(i),
            )
            call(
                "revision needs review " + str(i),
                "GET",
                path + "/report",
                sid=sids[who],
                extra=gh,
                expected=403,
            )
            mutate(
                "stale approval denied " + str(i),
                path,
                sids["reviewer"],
                "decisions",
                view,
                approval(view),
                409,
            )
            updated = call("current draft " + str(i), "GET", path + "/report", sid=sids["reviewer"])
            updated_views.append(updated)
            check(
                updated["report"]["findings"] == view["report"]["findings"]
                and updated["report"]["evidence"] == view["report"]["evidence"],
                "facts immutable " + str(i),
            )
            mutate(
                "new version review " + str(i),
                path,
                sids["reviewer"],
                "decisions",
                updated,
                approval(updated),
            )
            call(
                "old grant stale " + str(i),
                "GET",
                path + "/report",
                sid=sids[who],
                extra=gh,
                expected=409,
            )
            newgrant = mutate(
                "new version grant " + str(i),
                path,
                sids["owner"],
                "grants",
                updated,
                {"recipient_id": who, "ttl": 300},
            )
            nh = {
                "X-Report-Grant": newgrant["grant"]["grant_id"],
                "X-Report-Token": newgrant["access_token"],
            }
            call(
                "current approved version " + str(i),
                "GET",
                path + "/report",
                sid=sids[who],
                extra=nh,
            )
            mutate(
                "revoke " + str(i),
                path,
                sids["owner"],
                "revocations",
                updated,
                {"grant_id": newgrant["grant"]["grant_id"]},
            )
            call(
                "revoked read denied " + str(i),
                "GET",
                path + "/report",
                sid=sids[who],
                extra=nh,
                expected=403,
            )
            check(
                admin.execute(
                    "SELECT artifact_sha256 FROM target_v1.results WHERE tenant_id=%s AND job_id=%s",
                    (tenant, row[2]),
                ).fetchone()[0]
                == row[3],
                "original PG COMMIT unchanged " + str(i),
            )
        sids["reviewer"] = login("reviewer")
        registry["keys"]["report-test-authority"]["revoked"] = True
        root_write(TRUST, registry)
        call(
            "root report authority revoked",
            "GET",
            paths[0] + "/report",
            sid=sids["reviewer"],
            expected=403,
        )
        registry["keys"]["report-test-authority"]["revoked"] = False
        root_write(TRUST, registry)
        # Current source authorization, independent of identity/report approval.
        sids = {p["subject"]: login(p["subject"]) for p in people}
        active_headers = []
        for i, (_, source_ctx) in enumerate(selected):
            who = source_ctx["recipient_subject"]
            fresh = mutate(
                "fresh current grant before source withdrawal " + str(i),
                paths[i],
                sids["owner"],
                "grants",
                updated_views[i],
                {"recipient_id": who, "ttl": 300},
            )
            gh = {
                "X-Report-Grant": fresh["grant"]["grant_id"],
                "X-Report-Token": fresh["access_token"],
            }
            active_headers.append(gh)
            call(
                "current legal recipient before withdrawal " + str(i),
                "GET",
                paths[i] + "/report",
                sid=sids[who],
                extra=gh,
            )
        target = selected[0][1]["artifact"]["task"]["source_ref"]
        admin.execute(
            "UPDATE target_v1.authorizations SET revoked=true WHERE tenant_id=%s AND target_id=%s",
            (tenant, target),
        )
        call(
            "current source permission revoked",
            "GET",
            paths[0] + "/report",
            sid=sids["reviewer"],
            expected=403,
        )
        call(
            "active customer grant rejected after source withdrawal",
            "GET",
            paths[0] + "/report",
            sid=sids[selected[0][1]["recipient_subject"]],
            extra=active_headers[0],
            expected=403,
        )
        call(
            "other source and customer remain accessible",
            "GET",
            paths[1] + "/report",
            sid=sids[selected[1][1]["recipient_subject"]],
            extra=active_headers[1],
        )
        admin.execute(
            "UPDATE target_v1.authorizations SET revoked=false WHERE tenant_id=%s AND target_id=%s",
            (tenant, target),
        )
        completed = True
    except Exception as error:
        failure = type(error).__name__
        raise
    finally:
        process.stop(child)
        process.write(
            Path("/evidence/verified-reports.json"),
            {
                "contract": "vrae.verified-reports.protocol-drill.v1",
                "source_sha": state["g1_source_sha"],
                "completed": completed,
                "failure_class": failure,
                "checks": checks,
                "http": events,
                "independent_invited_identities": 2,
                "identity_evidence": "ISOLATED_SIGNED_MFA_PROTOCOL_TEST_NOT_ACTUAL_HUMAN_CUSTOMER_SIGNOFF",
                "actual_human_signature": False,
                "real_customer_network": False,
                "actual_customer_delivery": False,
                "model_calls": 0,
            },
        )
