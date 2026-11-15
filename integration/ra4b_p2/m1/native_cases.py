"""Real APP HTTP202, separate UID Worker, immutable report and signed reads."""

import hashlib
from uuid import uuid4
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time

import psycopg
from psycopg.types.json import Jsonb
import pytest

from integration.ra4a import support
from integration.ra4b import support as bootstrap
from integration.ra4b.runtime_check import signal_child
from integration.ra4b_p2.audit_cases import runtime as runtime
from integration.ra4b_p2.interface_cases import admit, fingerprint
from tests.collection.test_security import fixture
from tests.reviewing.synthetic import inputs
from tests.identity.issuer import Issuer, ISSUER, AUDIENCE
from vrae.identity.boundary import TrustAnchor, IdentityDenied
from vrae.application.ra4b import store
from vrae.application.ra4b_p2.m1.reader import SignedGeneratedReader, JobAssignment
from vrae.application.ra4b_p2.m1.runtime import load, build, commit
from vrae.application.ra4b_p2.producer import encode

OUT = Path("/evidence")


@pytest.fixture(scope="module")
def m1(runtime):
    with support.connect() as c:
        before = fingerprint(c)
        graphs = c.execute("SELECT count(*) FROM ra4a_bytes.graphs").fetchone()[0]
        c.execute(Path("/work/db/ra4b_p2/m1/001_runtime.sql").read_text())
        for case in ("404", "200"):
            raw = inputs(case).source
            ref = c.execute(
                "SELECT tenant_id,policy_id,policy_version,ref_sha256,metadata FROM ra4a.references WHERE ref_id=%s",
                ("accepted-" + case,),
            ).fetchone()
            assert hashlib.sha256(raw).hexdigest() == ref[4]["source_record_sha256"]
            audit, policy = fixture("AuditRequest"), fixture("SourcePolicy")
            audit.update(tenant_id=ref[0], source_policy_ref=ref[1], source_policy_version=ref[2])
            expiry = c.execute(
                "SELECT expires_at FROM ra4a.policies WHERE(tenant_id,policy_id,version)=(%s,%s,%s)",
                ref[:3],
            ).fetchone()[0]
            policy.update(
                tenant_id=ref[0],
                policy_id=ref[1],
                policy_version=ref[2],
                permitted_hosts=["example.org"],
                scope_paths=["/"],
                expires_at=expiry.isoformat(),
                revoked_at=None,
            )
            c.execute(
                "INSERT INTO ra4b_p2.m1_inputs(tenant_id,source_ref,reference_sha256,source_record,policy_document,audit_document,reviewer_role) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    ref[0],
                    "accepted-" + case,
                    ref[3],
                    raw,
                    Jsonb(policy),
                    Jsonb(audit),
                    "p2b1_test_a_reviewer",
                ),
            )
        assert fingerprint(c) == before
    children = []

    def spawn(crash=False):
        cfg = bootstrap.config("WORKER")
        folder = Path("/tmp/m1-worker-" + str(len(children)))
        folder.mkdir(mode=0o700)
        path = folder / "config.json"
        path.write_bytes(encode(cfg))
        path.chmod(0o600)
        os.chown(path, 10002, 10002)
        os.chown(folder, 10002, 10002)
        logpath = OUT / ("m1-worker-" + str(len(children)) + ".log")
        log = logpath.open("wb")
        p = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "integration.ra4b_p2.m1.crash_probe"
                if crash
                else "vrae.application.ra4b_p2.m1.runtime",
                "--config",
                str(path),
            ],
            user=10002,
            group=10002,
            extra_groups=[],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "PYTHONPATH": "/work",
                "PYTHONDONTWRITEBYTECODE": "1",
                "VRAE_RA4B_TEST_ONLY": "1",
                "PYTHONUNBUFFERED": "1",
            },
        )
        p.b4_uid = 10002
        children.append((p, log))
        if crash:
            deadline = time.monotonic() + 90
            while b"READY_UNCOMMITTED" not in logpath.read_bytes():
                assert p.poll() is None and time.monotonic() < deadline
                time.sleep(0.05)
            signal_child(p, signal.SIGKILL)
            p.wait(timeout=15)
            assert p.returncode == -signal.SIGKILL
            return {"worker_uid": 10002, "actual_sigkill": True}
        p.wait(timeout=90)  # Own process wait; DB lease remains30s.
        log.flush()
        assert p.returncode == 0
        return json.loads(logpath.read_bytes().splitlines()[-1])

    value = {"runtime": runtime, "spawn": spawn, "results": {}, "catalog_before": before}
    try:
        yield value
    finally:
        for p, log in children:
            if p.poll() is None:
                signal_child(p, signal.SIGTERM)
            p.wait(timeout=15)
            log.close()
        with support.connect() as c:
            assert fingerprint(c) == before
            assert c.execute("SELECT count(*) FROM ra4a_bytes.graphs").fetchone()[0] == graphs
            n = c.execute("SELECT count(*) FROM ra4b_p2.m1_results").fetchone()[0]
        (OUT / "m1-proof.json").write_bytes(
            encode(
                {
                    "protected_catalog_except_exact_three_policies": before,
                    "legacy_graph_count_unchanged": True,
                    "generated_rows": n,
                    "real_worker_uid": 10002,
                    "results": value["results"],
                    "scope": "SYNTHETIC_M1_NOT_FULL_BETA_EXIT",
                }
            )
        )
        restart_state = OUT / "private-restart-state.json"
        restart_state.write_bytes(support.STATE.read_bytes())
        restart_state.chmod(0o600)


def reader(m1, request, role="p2b1_test_a_reviewer", tenant="tenant-test"):
    issuer = Issuer()
    now = int(time.time())
    nonce = secrets.token_urlsafe(24)
    anchor = TrustAnchor(ISSUER, AUDIENCE, issuer.jwks(), now + 180)
    assignment = JobAssignment(
        ISSUER, "synthetic-reviewer-1", role, tenant, request["job_id"], now + 180
    )
    port = SignedGeneratedReader(anchor=anchor, assignments=[assignment], connect=support.connect)
    token = issuer.token({"iat": now, "nbf": now, "exp": now + 120, "nonce": nonce})
    m1["runtime"]["held"].setdefault("extra_secret_values", []).append(token)
    return port, token, nonce


@pytest.mark.parametrize("case", ["404", "200"])
def test_00_real_http_worker_same_job_signed_generated_read(m1, case):
    request = admit(m1["runtime"], "m1-real-" + case, "accepted-" + case)
    cfg = m1["runtime"]["held"]["APP"]
    with store.connect(cfg) as c:
        assert store.status(c, cfg, request["request_id"])["job_state"] == "PENDING"
    receipt = m1["spawn"]()
    assert all(receipt[k] == request[k] for k in ("request_id", "run_id", "job_id"))
    with store.connect(cfg) as c:
        assert store.status(c, cfg, request["request_id"])["job_state"] == "TEST_ONLY_DONE"
    port, token, nonce = reader(m1, request)
    report = port.read(token, "tenant-test", request["job_id"], nonce=nonce)
    assert report.locator == receipt
    doc = json.loads(report.report)
    assert len(doc["issues"]) == (1 if case == "404" else 0)
    assert doc["approval_status"] == "NOT_APPROVED" and not doc["shareable"]
    if case == "200":
        assert report.editorial_selection["full_fact_count"] == 17
        assert report.editorial_selection["omitted_positive_facts"] == 14
    # Old API idempotency and actual restarted Worker cannot create another row.
    assert admit(m1["runtime"], "m1-real-" + case, "accepted-" + case) == request
    assert m1["spawn"]() == {"status": "NO_LEGAL_PENDING_JOB"}
    # New issuer/nonce/reader instance after process lifetime; bytes persist.
    again, t2, n2 = reader(m1, request)
    restored = again.read(t2, "tenant-test", request["job_id"], nonce=n2)
    assert (restored.source, restored.report, restored.html) == (
        report.source,
        report.report,
        report.html,
    )
    with pytest.raises(IdentityDenied):
        port.read(token, "tenant-test", request["job_id"], nonce=nonce)
    m1["results"][case] = receipt


@pytest.mark.parametrize("role", ["p2b1_test_a_peer", "p2b1_test_b_reviewer"])
def test_peer_and_cross_tenant_signed_session_cannot_read(m1, role):
    request = m1["results"]["404"]
    tenant = "tenant-beta" if "_b_" in role else "tenant-test"
    port, token, nonce = reader(m1, request, role, tenant)
    with pytest.raises(IdentityDenied):
        port.read(token, tenant, request["job_id"], nonce=nonce)


@pytest.mark.parametrize("role", ["ra4b_test_a_worker", "p2b1_test_a_reviewer"])
@pytest.mark.parametrize("table", ["m1_inputs", "m1_results", "m1_assignments"])
def test_no_runtime_raw_select_or_dml(m1, role, table):
    with support.connect(role) as c:
        for query in (
            "SELECT * FROM ra4b_p2." + table,
            "UPDATE ra4b_p2." + table + " SET tenant_id=tenant_id",
        ):
            with pytest.raises(psycopg.Error) as error:
                c.execute(query)
            assert error.value.sqlstate == "42501"


def test_bad_signature_nonce_version_hash_and_tenant_fail_closed(m1):
    request = m1["results"]["404"]
    port, token, nonce = reader(m1, request)
    with pytest.raises(IdentityDenied):
        port.read(token, "tenant-test", request["job_id"], nonce="wrong-server-held-nonce")
    with pytest.raises(IdentityDenied):
        port.read(token[:-5] + "ABCDE", "tenant-test", request["job_id"], nonce=nonce)
    with support.connect("p2b1_test_a_reviewer") as c:
        with pytest.raises(psycopg.Error) as error:
            with c.transaction():
                c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                c.execute(
                    "SELECT * FROM ra4b_p2.m1_read_assigned(%s,%s)",
                    ("tenant-test", request["job_id"]),
                )
        assert error.value.sqlstate == "42501"
    with support.connect("p2b1_test_a_reviewer") as c:
        for tenant, version, hash_value in [
            ("tenant-beta", 1, request["report_sha256"]),
            ("tenant-test", 2, request["report_sha256"]),
            ("tenant-test", 1, "0" * 64),
        ]:
            with pytest.raises(psycopg.Error) as error:
                c.execute(
                    "SELECT * FROM ra4b_p2.m1_read(%s,%s,%s,%s)",
                    (tenant, request["job_id"], version, hash_value),
                )
            assert error.value.sqlstate == "42501"


def test_actual_eligible_for_share_but_origin_dml_still_denied(m1):
    with support.connect() as c:
        c.execute(
            "CREATE FUNCTION ra4b_p2.m1_lock_probe() RETURNS bigint LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT count(*) FROM (SELECT epoch FROM ra4b_test.origin_epochs FOR SHARE) x $$; ALTER FUNCTION ra4b_p2.m1_lock_probe() OWNER TO ra4a_owner; REVOKE ALL ON FUNCTION ra4b_p2.m1_lock_probe() FROM PUBLIC; GRANT EXECUTE ON FUNCTION ra4b_p2.m1_lock_probe() TO p2b1_review"
        )
    with support.connect("p2b1_test_a_reviewer") as c:
        assert c.execute("SELECT ra4b_p2.m1_lock_probe()").fetchone() == (1,)
    for table in ("origin_epochs", "request_origins"):
        for operation in ("UPDATE", "DELETE", "INSERT"):
            name = "m1_dml_" + table + "_" + operation.lower()
            sql = (
                "UPDATE ra4b_test." + table + " SET epoch=epoch"
                if operation == "UPDATE"
                else "DELETE FROM ra4b_test." + table
                if operation == "DELETE"
                else "INSERT INTO ra4b_test." + table + " SELECT * FROM ra4b_test." + table
            )
            with support.connect() as c:
                before = c.execute("SELECT * FROM ra4b_test." + table + " ORDER BY 1,2").fetchall()
                c.execute(
                    "CREATE FUNCTION ra4b_p2."
                    + name
                    + "() RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ DECLARE n bigint; BEGIN "
                    + sql
                    + "; GET DIAGNOSTICS n=ROW_COUNT; RETURN n; END $$; ALTER FUNCTION ra4b_p2."
                    + name
                    + "() OWNER TO ra4a_owner; REVOKE ALL ON FUNCTION ra4b_p2."
                    + name
                    + "() FROM PUBLIC; GRANT EXECUTE ON FUNCTION ra4b_p2."
                    + name
                    + "() TO p2b1_review"
                )
            with support.connect("p2b1_test_a_reviewer") as c:
                if operation == "DELETE" or (operation == "UPDATE" and table == "request_origins"):
                    assert c.execute("SELECT ra4b_p2." + name + "()").fetchone() == (0,)
                else:
                    with pytest.raises(psycopg.Error) as error:
                        c.execute("SELECT ra4b_p2." + name + "()")
                    assert error.value.sqlstate in ("42501", "55000")
            with support.connect() as c:
                assert (
                    c.execute("SELECT * FROM ra4b_test." + table + " ORDER BY 1,2").fetchall()
                    == before
                )
                c.execute("DROP FUNCTION ra4b_p2." + name + "()")


def test_real_transaction_rollback_idempotent_commit_and_hash_negative(m1):
    request = admit(m1["runtime"], "m1-atomic-0003", "accepted-200")
    cfg = bootstrap.config("WORKER")
    with store.connect(cfg) as c:
        lease = store.claim(c, cfg, 30)
        assert str(lease[0]) == request["job_id"]
        m1["runtime"]["held"]["extra_secret_values"].append(str(lease[2]))
        output = build(load(c, "tenant-test", lease), lease)
        with pytest.raises(psycopg.Error) as error:
            c.execute(
                "SELECT ra4b_p2.m1_commit(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    "tenant-test",
                    lease[0],
                    lease[2],
                    lease[3],
                    output.source,
                    output.report,
                    output.html + b"bad",
                    output.binding,
                ),
            )
        assert error.value.sqlstate == "22023"
        with pytest.raises(RuntimeError, match="ROLLBACK_WITNESS"):
            with c.transaction():
                c.execute(
                    "SELECT ra4b_p2.m1_commit(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        "tenant-test",
                        lease[0],
                        lease[2],
                        lease[3],
                        output.source,
                        output.report,
                        output.html,
                        output.binding,
                    ),
                )
                raise RuntimeError("ROLLBACK_WITNESS")
        with support.connect() as observer:
            assert observer.execute(
                "SELECT count(*) FROM ra4b_p2.m1_results WHERE job_id=%s", (lease[0],)
            ).fetchone() == (0,)
            assert observer.execute(
                "SELECT state FROM ra4a.jobs WHERE job_id=%s", (lease[0],)
            ).fetchone() == ("LEASED",)
        first = commit(c, "tenant-test", lease, output)
        assert commit(c, "tenant-test", lease, output) == first
    m1["results"]["atomic"] = first


def test_foreign_expired_reclaimed_lease_and_output_pins(m1):
    request = admit(m1["runtime"], "m1-expired-lease", "accepted-200")
    cfg = bootstrap.config("WORKER")
    with store.connect(cfg) as c:
        lease = store.claim(c, cfg, 1)
        assert str(lease[0]) == request["job_id"]
        m1["runtime"]["held"]["extra_secret_values"].append(str(lease[2]))
        for tenant, bad in [
            ("tenant-beta", lease),
            ("tenant-test", (uuid4(), *lease[1:])),
            ("tenant-test", (lease[0], lease[1], uuid4(), lease[3], lease[4])),
            ("tenant-test", (*lease[:3], lease[3] + 1, lease[4])),
        ]:
            with pytest.raises(psycopg.Error) as error:
                load(c, tenant, bad)
            assert error.value.sqlstate == "42501"
        c.execute("SELECT pg_sleep(1.1)")
        with pytest.raises(psycopg.Error) as error:
            load(c, "tenant-test", lease)
        assert error.value.sqlstate == "42501"
        current = store.claim(c, cfg, 30)
        assert current[0] == lease[0] and current[3] == lease[3] + 1
        m1["runtime"]["held"]["extra_secret_values"].append(str(current[2]))
        output = build(load(c, "tenant-test", current), current)
        for mutation in (
            "guard_version",
            "guard_ref",
            "policy_hash",
            "report_id",
            "actor",
            "source_bytes",
        ):
            report = json.loads(output.report)
            source = json.loads(output.source)
            binding = json.loads(output.binding)
            if mutation == "guard_version":
                report["pins"]["expected_guard_version"] = "ra3b-1.0.0"
            elif mutation == "guard_ref":
                report["pins"]["expected_guard_refs"][0] = "gr-" + "0" * 64
            elif mutation == "policy_hash":
                binding["policy_sha256"] = "0" * 64
            elif mutation == "report_id":
                report["metadata"]["report_id"] = "other-job"
            elif mutation == "actor":
                binding["worker"] = "ra4b_test_b_worker"
            else:
                key = next(iter(source["objects_base64"]))
                source["objects_base64"][key] = "dGFtcGVyZWQ="
            with pytest.raises(psycopg.Error) as error:
                c.execute(
                    "SELECT ra4b_p2.m1_commit(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        "tenant-test",
                        current[0],
                        current[2],
                        current[3],
                        encode(source),
                        encode(report),
                        output.html,
                        encode(binding),
                    ),
                )
            assert error.value.sqlstate == "22023"
        commit(c, "tenant-test", current, output)


def test_uid_sigkill_rolls_back_finish_and_result_then_reclaims(m1):
    request = admit(m1["runtime"], "m1-real-sigkill", "accepted-200")
    assert m1["spawn"](crash=True) == {"worker_uid": 10002, "actual_sigkill": True}
    with support.connect() as c:
        assert c.execute(
            "SELECT count(*) FROM ra4b_p2.m1_results WHERE job_id=%s", (request["job_id"],)
        ).fetchone() == (0,)
        state = c.execute(
            "SELECT state,lease_seq,EXTRACT(EPOCH FROM lease_until-clock_timestamp()) FROM ra4a.jobs WHERE job_id=%s",
            (request["job_id"],),
        ).fetchone()
        assert state[:2] == ("LEASED", 1)
        remaining = max(0, float(state[2]))
        assert remaining <= 30
    time.sleep(remaining + 0.05)
    result = m1["spawn"]()
    assert result["job_id"] == request["job_id"]
    with support.connect() as c:
        assert c.execute(
            "SELECT lease_seq FROM ra4b_p2.m1_results WHERE job_id=%s", (request["job_id"],)
        ).fetchone() == (2,)
        assert c.execute(
            "SELECT count(*) FROM ra4a.outbox WHERE run_id=%s AND kind='TEST_ONLY_CONSUMED'",
            (request["run_id"],),
        ).fetchone() == (1,)


def test_assignment_revoke_waits_for_authorized_read_then_denies(m1):
    request = m1["results"]["404"]
    blocked = []
    errors = []

    def revoke():
        try:
            with support.connect() as c:
                blocked.append(c.info.backend_pid)
                c.execute(
                    "UPDATE ra4b_p2.m1_assignments SET active=false WHERE job_id=%s",
                    (request["job_id"],),
                )
        except BaseException as e:
            errors.append(type(e).__name__)

    with support.connect("p2b1_test_a_reviewer") as c:
        with c.transaction():
            c.execute(
                "SELECT * FROM ra4b_p2.m1_read_assigned(%s,%s)", ("tenant-test", request["job_id"])
            ).fetchone()
            thread = threading.Thread(target=revoke)
            thread.start()
            end = time.monotonic() + 1
            observed = False
            while time.monotonic() < end:
                if blocked:
                    with support.connect() as observer:
                        observed = (
                            c.info.backend_pid
                            in observer.execute(
                                "SELECT pg_blocking_pids(%s)", (blocked[0],)
                            ).fetchone()[0]
                        )
                    if observed:
                        break
                time.sleep(0.01)
            assert observed
        thread.join(timeout=3)
    assert not thread.is_alive() and not errors
    port, token, nonce = reader(m1, request)
    with pytest.raises(IdentityDenied):
        port.read(token, "tenant-test", request["job_id"], nonce=nonce)


def test_policy_revoke_then_epoch_rollover_do_not_resurrect_result(m1):
    request = m1["results"]["200"]
    with support.connect() as c:
        c.execute("UPDATE ra4a.policies SET status='REVOKED' WHERE tenant_id='tenant-test'")
    port, token, nonce = reader(m1, request)
    with pytest.raises(IdentityDenied):
        port.read(token, "tenant-test", request["job_id"], nonce=nonce)
    with support.connect() as c:
        c.execute("UPDATE ra4a.policies SET status='ALLOWED' WHERE tenant_id='tenant-test'")
    port, token, nonce = reader(m1, request)
    assert (
        port.read(token, "tenant-test", request["job_id"], nonce=nonce).locator["job_id"]
        == request["job_id"]
    )
    with support.connect() as c:
        before = c.execute(
            "SELECT epoch FROM ra4b_test.origin_epochs WHERE tenant_id='tenant-test'"
        ).fetchone()[0]
        c.execute(
            "UPDATE ra4a_private.principals SET enabled=false WHERE db_role='ra4b_test_a_app'"
        )
        c.execute("UPDATE ra4a_private.principals SET enabled=true WHERE db_role='ra4b_test_a_app'")
        after = c.execute(
            "SELECT epoch FROM ra4b_test.origin_epochs WHERE tenant_id='tenant-test'"
        ).fetchone()[0]
        assert after == before + 2
    port, token, nonce = reader(m1, request)
    with pytest.raises(IdentityDenied):
        port.read(token, "tenant-test", request["job_id"], nonce=nonce)
    # A genuinely new request at the new epoch, never repair an old binding.
    fresh = admit(m1["runtime"], "m1-restart-current-epoch", "accepted-200")
    receipt = m1["spawn"]()
    assert receipt["job_id"] == fresh["job_id"]
    port, token, nonce = reader(m1, fresh)
    assert port.read(token, "tenant-test", fresh["job_id"], nonce=nonce).locator == receipt
    m1["results"]["restart"] = receipt
