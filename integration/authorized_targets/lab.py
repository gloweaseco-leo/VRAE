"""Disposable runnable vertical: real HTTPS, PG16, DNS/TLS Collector and report.

Only this test harness names tenants/sites. Runtime modules consume operator
configuration. No customer network, approval key or model provider exists here.
"""

from copy import deepcopy
from datetime import datetime, UTC, timedelta
import http.client
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import time
from types import SimpleNamespace

import psycopg
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from contracts.l2_launch.contract import canonical
from contracts.l2_launch.vf_b import submission_document
from integration.authorized_targets.provision import install
from integration.authorized_targets.authority import token_hash
from integration.l2_launch.g1 import supervisor as process
from integration.l2_launch.g1.tls import create as create_tls
from integration.l2_launch.g1.fixtures import submission
from integration.l2_launch.g1.http_server import MEDIA
from integration.authorized_targets.checks.issuer import Issuer

ROOT = Path("/evidence/.private-root")
ENV = process.ENV
ENV["R1A_ISOLATED_LAB"] = "1"


def check(value, label):
    if not value:
        raise AssertionError(label)
    checks.append(label)


def network(interfaces=None):
    assert os.geteuid() == 0 and set(os.listdir("/sys/class/net")) == set(interfaces or ["lo"])
    for address in ("93.184.216.20/32", "93.184.216.53/32"):
        subprocess.run(["ip", "addr", "add", address, "dev", "lo"], check=True, capture_output=True)
    for tool in ("iptables", "ip6tables"):
        for uid, ports in ((10001, (5432,)), (10007, (5432,)), (65532, (5432,))):
            base = [tool, "-A", "OUTPUT", "-m", "owner", "--uid-owner", str(uid)]
            subprocess.run(
                base + ["-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
                check=True,
            )
            if tool == "iptables":
                for port in ports:
                    subprocess.run(
                        base
                        + ["-p", "tcp", "-d", "127.0.0.1", "--dport", str(port), "-j", "ACCEPT"],
                        check=True,
                    )
                if uid == 65532:
                    subprocess.run(
                        base
                        + ["-p", "udp", "-d", "93.184.216.53", "--dport", "53", "-j", "ACCEPT"],
                        check=True,
                    )
                    subprocess.run(
                        base
                        + ["-p", "tcp", "-d", "93.184.216.20", "--dport", "443", "-j", "ACCEPT"],
                        check=True,
                    )
            subprocess.run(base + ["-j", "REJECT"], check=True)


def certificates(hosts, validity_hours=1):
    lab = Path("/tmp/lab")
    lab.mkdir(mode=0o755)
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Owned controlled origin test CA")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=validity_hours))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), False)
        .add_extension(
            x509.KeyUsage(True, False, False, False, False, True, True, None, None), True
        )
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(h) for h in hosts]), False)
        .sign(key, hashes.SHA256())
    )
    (lab / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (lab / "key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (lab / "key.pem").chmod(0o600)


def main():
    state = json.loads(sys.stdin.buffer.read())
    extension = None
    if state.get("delivery_bridge"):
        from integration.authorized_targets.checks.delivery_drill import Drill

        extension = Drill()
    if state.get("standalone"):
        from integration.authorized_targets.checks.api_drill import ApiDrill

        extension = ApiDrill(state)
    ROOT.mkdir(mode=0o700)
    network(sorted(os.listdir("/sys/class/net")) if state.get("standalone") else None)
    admin = psycopg.connect(
        host="127.0.0.1",
        dbname="vrae_ra4a_p1",
        user="postgres",
        password=state["admin_password"],
        autocommit=True,
    )
    admin.execute(Path("/work/db/migrations/0001_ra4a_test_only.sql").read_text())
    admin.execute(Path("/work/infra/authorized_targets/001_authority.sql").read_text())
    if extension:
        extension.migrate(admin)
    fixtures = json.loads(Path("/work/tests/fixtures/contracts/valid.json").read_bytes())

    def fixture(name):
        return deepcopy(next(c["data"] for c in fixtures if c["schema"] == name))

    now = datetime.now(UTC)
    expiry = (now + timedelta(hours=state.get("local_validity_hours", 1))).isoformat()
    tenants = []
    issuers = {}
    bindings = []
    workers = []
    reviewers = []
    all_subjects = []
    hosts = {}
    for slug in ("alpha", "beta"):
        t = "tenant-" + slug
        issuer = Issuer(t)
        issuers[t] = issuer
        actors = []
        for kind in ("APP", "WORKER"):
            b = {
                "role": "targets_" + slug + "_" + kind.lower(),
                "password": secrets.token_urlsafe(24),
                "kind": kind,
                "tenant_id": t,
            }
            actors.append(b)
            if kind == "APP":
                b.update(
                    service_sha256=token_hash("lab-" + slug), verification_keys=issuer.public()
                )
                bindings.append(b)
            else:
                workers.append(b)
        review_binding = {
            "role": "targets_" + slug + "_review",
            "password": secrets.token_urlsafe(24),
            "kind": "APP",
            "tenant_id": t,
            "port": "REVIEW",
        }
        actors.append(review_binding)
        reviewers.append(review_binding)
        plans = []
        for suffix in ("pumps", "systems"):
            host = slug + "-" + suffix + ".test"
            hosts[host] = slug + " " + suffix
            policy = fixture("SourcePolicy")
            policy.update(
                tenant_id=t,
                policy_id="pol-" + suffix,
                permitted_hosts=[host],
                authorization_reference="controlled-authorization-" + slug + "-" + suffix,
                created_at=(now - timedelta(minutes=1)).isoformat(),
                expires_at=expiry,
            )
            plans.append(
                {
                    "tenant_id": t,
                    "target_id": "target-" + suffix,
                    "origin": "https://" + host,
                    "exact_paths": [
                        "/robots.txt",
                        "/",
                        "/products/item",
                        "/applications",
                        "/proof",
                        "/rfq",
                        "/denied",
                        "/private",
                    ],
                    "terms_reference": "controlled-terms-v1",
                    "retain_raw_html": True,
                    "authorization_kind": "CONTROLLED_NON_CUSTOMER",
                    "expires_at": expiry,
                    "revoked": False,
                    "policy": policy,
                    "limits": {
                        "max_pages": 8,
                        "request_seconds": 10,
                        "task_seconds": 22,
                        "interval_seconds": 0.01,
                    },
                }
            )
        invitations = []
        for n in range(2):
            inv = {
                "token": secrets.token_urlsafe(24),
                "document": {
                    "tenant_id": t,
                    "reference": "inv-" + slug + "-" + str(n),
                    "subject_ref": "subject-" + slug + "-" + str(n),
                    "target_ids": [p["target_id"] for p in plans],
                    "expires_at": expiry,
                    "revoked": False,
                },
            }
            invitations.append(inv)
            all_subjects.append((slug, plans, inv))
        tenants.append(
            {
                "tenant_id": t,
                "expires_at": expiry,
                "max_pending": 2,
                "actors": actors,
                "plans": plans,
                "invitations": invitations,
            }
        )
    if extension:
        extension.configure(tenants)
    install(admin, tenants)
    if extension:
        extension.activate(admin, tenants)
    certificates(hosts, validity_hours=state.get("local_validity_hours", 1))
    if extension:
        extension.ready()
    Path("/tmp/lab/site.json").write_text(json.dumps({"hosts": hosts}))
    with (ROOT / "site.log").open("wb") as log:
        site = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "integration.authorized_targets.checks.site",
                "/tmp/lab/site.json",
            ],
            env=ENV,
            stdout=log,
            stderr=log,
            cwd="/work",
        )
    process.wait(lambda: Path("/tmp/lab/ready").exists())
    tls = extension.tls(ROOT / "tls") if hasattr(extension, "tls") else create_tls(ROOT / "tls")
    cfg = {
        "kind": "APP",
        "authority": "AUTHORIZED_TARGET_V1",
        "bindings": bindings,
        "source_sha": state["g1_source_sha"],
    }
    if extension:
        extension.api_config(cfg, tenants)
    appcfg = process.provision("targets-api", 10001, cfg, tls["facade"])
    app, log = process.spawn("targets-api", 10001, appcfg, "integration.authorized_targets.http")
    process.wait(lambda: b"AUTHORIZED_TARGET_HTTPS_READY" in log.read_bytes())
    context = ssl.create_default_context(cafile=tls["ca"])
    if hasattr(extension, "local_client_tls"):
        extension.local_client_tls(context)
    transcript = []

    def call(slug, method, path, body=None, session=None, bearer=True):
        headers = {"Origin": "https://127.0.0.1:8769", "Accept": MEDIA, "Content-Type": MEDIA}
        if bearer:
            headers["Authorization"] = "Bearer lab-" + slug
        if session:
            headers.update(Cookie=session[0], **{"X-CSRF-Token": session[1]})
        c = http.client.HTTPSConnection("127.0.0.1", 8769, context=context, timeout=5)
        c.request(method, path, None if body is None else canonical(body), headers)
        resp = c.getresponse()
        data = resp.read()
        hs = dict(resp.getheaders())
        c.close()
        result = json.loads(data)
        recorded = result
        if path == "/v1/internal/committed-input" and resp.status == 200:
            recorded = {
                "contract": result["contract"],
                "task": result["task"],
                "commit": result["commit"],
                "report_content_hash": result["artifact"]["version"]["content_hash"],
                "display_hash": result["artifact"]["display_hash"],
                "grants_report_access": False,
            }
        transcript.append({"method": method, "path": path, "status": resp.status, "body": recorded})
        return resp.status, result, hs

    sessions = []
    accepted = []
    for slug, plans, inv in all_subjects:
        status, body, hs = call(
            slug, "POST", "/v1/invitation-session", {"invitation_token": inv["token"]}
        )
        check(status == 200, "invitation exchange " + inv["document"]["reference"])
        cookie = hs["Set-Cookie"]
        check(
            all(x in cookie for x in ("HttpOnly", "Secure", "SameSite=Strict")),
            "secure cookie " + inv["document"]["reference"],
        )
        session = (cookie.split(";")[0], hs["X-CSRF-Token"])
        sessions.append(session)
        plan = plans[len(accepted) % 2]
        audit = fixture("AuditRequest")
        audit.update(
            tenant_id=plan["tenant_id"],
            site_url=plan["origin"] + "/",
            source_policy_ref=plan["policy"]["policy_id"],
        )
        value, _ = submission(
            SimpleNamespace(audit=audit, policy=plan["policy"]), issuers[plan["tenant_id"]]
        )
        value.update(
            subject_ref=inv["document"]["subject_ref"], invitation_ref=inv["document"]["reference"]
        )
        value["submission_proof"] = issuers[plan["tenant_id"]].sign(
            "permission", "permission", submission_document(value)
        )
        status, receipt, _ = call(slug, "POST", "/v1/audit-requests", value, session)
        check(status == 202, "original PG admission " + inv["document"]["reference"])
        check(
            call(slug, "POST", "/v1/audit-requests", value, session)[1] == receipt,
            "same intent replay " + inv["document"]["reference"],
        )
        check(
            call(slug, "GET", "/v1/audits/" + receipt["audit_ref"] + "/report", session=session)[0]
            == 403,
            "unreviewed report denied " + inv["document"]["reference"],
        )
        accepted.append((slug, value, receipt, session))
    # Another subject in the same tenant and another tenant cannot read a task.
    path = "/v1/audits/" + accepted[0][2]["audit_ref"]
    check(
        call("alpha", "GET", path, session=sessions[1])[0] == 403,
        "same tenant different subject denied",
    )
    check(call("beta", "GET", path, session=sessions[2])[0] == 403, "cross tenant denied")
    check(
        call("alpha", "GET", path, session=sessions[0], bearer=False)[0] == 403,
        "missing service identity denied",
    )
    check(call("alpha", "GET", path)[0] == 403, "missing session denied")
    slug, value, receipt, session = accepted[0]
    changed = deepcopy(value)
    changed["language"] = "en"
    changed["submission_proof"] = issuers["tenant-alpha"].sign(
        "permission", "permission", submission_document(changed)
    )
    check(
        call(slug, "POST", "/v1/audit-requests", changed, session)[0] == 409,
        "same key changed signed intent conflict",
    )
    extra = deepcopy(value)
    extra["command"]["request"]["idempotency_key"] = "capacity-" + secrets.token_hex(12)
    from contracts.l2_launch.contract import permission_document

    extra["command"]["permission_reference"]["proof"] = issuers["tenant-alpha"].sign(
        "permission",
        "permission",
        permission_document(extra["command"], tenants[0]["plans"][0]["policy"]),
    )
    extra["submission_proof"] = issuers["tenant-alpha"].sign(
        "permission", "permission", submission_document(extra)
    )
    check(
        call("alpha", "POST", "/v1/audit-requests", extra, session)[0] == 429,
        "actual pending capacity returns429",
    )

    def consume():
        worker_cfg = process.provision(
            "targets-worker-" + secrets.token_hex(3),
            65532,
            {
                "kind": "WORKER",
                "authority": "AUTHORIZED_TARGET_V1",
                "bindings": workers,
                "workload": {
                    "kind": "AUTHORIZED_EGRESS_V2" if extension else "CONTROLLED_NON_CUSTOMER"
                },
            },
        )
        worker, wlog = process.spawn(
            "targets-worker", 65532, worker_cfg, "integration.authorized_targets.worker"
        )
        worker.wait(timeout=120)
        if worker.returncode:
            raise AssertionError("ACTUAL_WORKER_RED " + wlog.read_text())
        return [d for x in wlog.read_text().splitlines() if (d := json.loads(x)).get("claimed")]

    receipts = consume()
    check(len(receipts) == 4, "four independent actual DNS TLS captures")
    check(
        call("alpha", "POST", "/v1/audit-requests", extra, session)[0] == 202,
        "capacity recovers after real worker COMMIT",
    )
    receipts += consume()
    for slug, value, receipt, session in accepted:
        status, current, _ = call(
            slug, "GET", "/v1/audits/" + receipt["audit_ref"], session=session
        )
        check(
            status == 200
            and current["task"]["status"] == "DRAFT_READY"
            and current["display_state"] != "completed",
            "actual unpublished draft " + receipt["audit_ref"],
        )
    # Durable artifacts come from real original queue jobs and current leases.
    rows = admin.execute(
        "SELECT r.tenant_id,r.run_id,r.job_id,r.artifact_sha256,r.artifact,j.state FROM target_v1.results r JOIN ra4a.jobs j USING(tenant_id,job_id)"
    ).fetchall()
    check(
        len(rows) == 5 and len({x[1] for x in rows}) == 5,
        "five retained unique runs without overwrite",
    )
    for tenant, run, job, sha, raw, job_state in rows:
        d = json.loads(raw)
        process.write(ROOT / ("artifact-" + str(job) + ".json"), d)
        check(
            job_state == "DRAFT_READY"
            and d["pack"]["run_id"] == str(run)
            and d["task"]["tenant_id"] == tenant,
            "same PG evidence report run " + str(run),
        )
        check(
            any(
                p["snapshot"]["status"] == "FETCHED"
                for p in d["pack"]["sources"][0]["document"]["pages"]
            ),
            "real fetched page " + str(run),
        )
        check(
            len(d["diagnosis"]["source_facts"]) > 0 and len(d["native_document"]["journey"]) == 5,
            "original facts and five dimensions " + str(run),
        )
        check(
            d["source_access_mode"] == "L1"
            and d["diagnostic_depth"] == "L2"
            and d["external_release"] is False,
            "source permission not diagnostic depth " + str(run),
        )
    if state.get("report_api"):
        from integration.authorized_targets.checks.report_api_drill import run as report_api_drill

        report_api_drill(admin, rows, reviewers, bindings, tls, state)
    # Actual signed controlled review through the ORIGINAL source and ledger.
    # No simulated identity is promoted to formal human approval.
    from integration.authorized_targets.review import current_review
    from integration.l2.support import Issuer as ReviewIssuer, login, pins
    from vrae.l2.identity import Directory, Person

    report = json.loads(rows[0][4])
    rid = report["version"]["report_id"]
    tenant = rows[0][0]
    issuer = ReviewIssuer()
    person = Person(
        "controlled-reviewer",
        "controlled-reviewer",
        "Controlled reviewer",
        tenant,
        "REVIEWER",
        (rid,),
    )
    directory = Directory(
        issuer=issuer.issuer,
        audience=issuer.audience,
        jwks=issuer.jwks,
        people=[person],
        expires=time.time() + 600,
    )
    sid = login(issuer, directory, person.subject)
    binding = next(b for b in reviewers if b["tenant_id"] == tenant)
    with current_review(binding, rows[0][2], ROOT / "review.sqlite", directory) as ledger:
        view = ledger.read(sid, rid)
        check(
            view.display_hash == report["display_hash"],
            "current PG source original NativeSource full replay",
        )
        review = ledger.review(
            sid,
            rid,
            **pins(view),
            action="APPROVE",
            reason="Controlled noncustomer item review, not formal approval",
            items={x["id"]: "ACK" for x in view.document["findings"] + view.document["blueprint"]},
            attest=True,
        )
        check(
            not review["formal_human_review"] and not review["external_delivery"],
            "controlled review cannot confer customer release",
        )
    process.write(ROOT / "controlled-review.json", review)
    from integration.authorized_targets import store

    def denied_sql(binding, statement, values, label):
        with store.connect(binding) as c:
            try:
                with c.transaction():
                    c.execute(statement, values).fetchall()
            except psycopg.Error as error:
                check(error.sqlstate in ("42501", "22023", "55000"), label)
            else:
                raise AssertionError(label)

    denied_sql(bindings[0], "SELECT * FROM target_v1.results", (), "APP cannot read raw results")
    denied_sql(
        workers[0],
        "SELECT target_v1.review_source(%s,%s)",
        ("tenant-alpha", rows[0][2]),
        "Worker cannot open review source",
    )
    denied_sql(
        bindings[0],
        "SELECT target_v1.review_source(%s,%s)",
        ("tenant-alpha", rows[0][2]),
        "BFF cannot open review source",
    )
    denied_sql(
        workers[0],
        "SELECT target_v1.load(%s,%s,%s,%s)",
        ("tenant-alpha", rows[0][2], "00000000-0000-0000-0000-000000000000", 1),
        "completed job cannot reuse lease",
    )
    # PG IDs/session authority survive an actual facade process replacement.
    process.stop(app)
    app, log = process.spawn(
        "targets-api-restarted", 10001, appcfg, "integration.authorized_targets.http"
    )
    process.wait(lambda: b"AUTHORIZED_TARGET_HTTPS_READY" in log.read_bytes())
    check(
        call("alpha", "POST", "/v1/audit-requests", accepted[0][1], sessions[0])[1]
        == accepted[0][2],
        "facade restart preserves idempotency and session",
    )
    # Recovery uses the original claim implementation, not a second scheduler.
    probe = deepcopy(accepted[0][1])
    probe["command"]["request"]["idempotency_key"] = "lease-probe-" + secrets.token_hex(12)
    probe["command"]["permission_reference"]["proof"] = issuers["tenant-alpha"].sign(
        "permission",
        "permission",
        permission_document(probe["command"], tenants[0]["plans"][0]["policy"]),
    )
    probe["submission_proof"] = issuers["tenant-alpha"].sign(
        "permission", "permission", submission_document(probe)
    )
    check(
        call("alpha", "POST", "/v1/audit-requests", probe, sessions[0])[0] == 202,
        "new request admitted for original lease recovery",
    )
    w = workers[0]
    first = store.claim(w)
    jid, run, token, seq, until = first
    denied_sql(
        w,
        "SELECT target_v1.commit(%s,%s,%s,%s,%s)",
        ("tenant-alpha", jid, token, seq, b"{}"),
        "missing draft fields rejected without SQL NULL bypass",
    )
    for attempt in range(3):
        admin.execute(
            "UPDATE ra4a.jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE tenant_id='tenant-alpha' AND job_id=%s",
            (jid,),
        )
        denied_sql(
            w,
            "SELECT target_v1.load(%s,%s,%s,%s)",
            ("tenant-alpha", jid, token, seq),
            "expired original lease denied " + str(attempt),
        )
        lease = store.claim(w)
        if attempt < 2:
            check(
                lease is not None and lease[0] == jid and lease[3] == seq + 1,
                "original lease reclaimed same job " + str(attempt),
            )
            denied_sql(
                w,
                "SELECT target_v1.load(%s,%s,%s,%s)",
                ("tenant-alpha", jid, token, seq),
                "stale lease token denied " + str(attempt),
            )
            jid, run, token, seq, until = lease
        else:
            check(lease is None, "original three attempt dead letter reached")
    check(
        admin.execute(
            "SELECT state,attempts FROM ra4a.jobs WHERE tenant_id='tenant-alpha' AND job_id=%s",
            (jid,),
        ).fetchone()
        == ("DEAD_LETTER", 3),
        "original DEAD_LETTER persisted",
    )
    if extension:
        extension.exercise(locals())
    if state.get("standalone"):
        admin.close()
        admin = psycopg.connect(
            host="127.0.0.1",
            dbname="vrae_ra4a_p1",
            user="postgres",
            password=state["admin_password"],
            autocommit=True,
        )

    # Plan edits cannot widen an already admitted task/source binding.
    admin.execute(
        "UPDATE target_v1.plans SET document=jsonb_set(document,'{terms_reference}','\"changed-terms\"') WHERE tenant_id=%s AND target_id=%s",
        (tenant, report["task"]["source_ref"]),
    )
    denied_sql(
        binding,
        "SELECT target_v1.review_source(%s,%s)",
        (tenant, rows[0][2]),
        "changed source plan invalidates retained review",
    )
    # Current invitation revocation applies to existing sessions immediately.
    admin.execute(
        "UPDATE target_v1.invitations SET revoked=true WHERE tenant_id='tenant-alpha' AND reference='inv-alpha-0'"
    )
    check(
        call("alpha", "GET", path, session=sessions[0])[0] == 403,
        "revoked invitation rejects current session",
    )
    if state.get("serve") and extension:
        extension.hold()
    process.stop(app)
    site.terminate()
    site.wait(timeout=5)
    process.write(
        Path("/evidence/targets.json"),
        {
            "status": "CONTROLLED_TARGET_VERTICAL_PASS_NOT_CUSTOMER_RELEASE",
            "checks": checks,
            "receipts": receipts,
            "http": transcript,
            "real_customer_network": False,
            "model_calls": 0,
            "cloud_resources": 0,
            "source_sha": state["g1_source_sha"],
        },
    )
    print(
        json.dumps(
            {
                "status": "CONTROLLED_TARGET_VERTICAL_PASS_NOT_CUSTOMER_RELEASE",
                "checks": len(checks),
                "tasks": len(rows),
            }
        ),
        flush=True,
    )


checks = []
if __name__ == "__main__":
    main()
