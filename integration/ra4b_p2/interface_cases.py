"""Additive live ports; genuine generated sealing/positive Reviewer read is HOLD."""

from contextlib import closing
import base64
from datetime import datetime
import hashlib
import http.client
import json
from pathlib import Path
import time
import threading
import subprocess
import sys
from urllib.parse import urlsplit
from uuid import uuid4, UUID

import psycopg
from psycopg.types.json import Jsonb
import pytest

from integration.ra4a import support
from integration.ra4b import support as bootstrap
from integration.ra4b_p2.audit_cases import runtime as runtime
from tests.collection.test_security import fixture
from tests.reviewing.synthetic import inputs
from vrae.application.ra4b import store
from vrae.application.ra4b_p2.producer import GeneratedCandidate, encode
from vrae.application.ra4b_p2.source_adapter import load, stage

ROOT = Path("/work")
OUT = Path("/evidence")
NEW_POLICIES = {"s2_assigned_epoch_select", "s2_assigned_request_select", "s2_assigned_epoch_lock"}


def fingerprint(c):
    queries = [
        "SELECT n.nspname,p.proname,pg_get_functiondef(p.oid),p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test','ra4b_test') ORDER BY 1,2,3",
        "SELECT n.nspname,t.relname,t.relacl::text,t.relrowsecurity,t.relforcerowsecurity,pg_get_userbyid(t.relowner) FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test','ra4b_test') AND t.relkind='r' ORDER BY 1,2",
        "SELECT schemaname,tablename,policyname,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test','ra4b_test') AND policyname NOT IN ('s2_assigned_epoch_select','s2_assigned_request_select','s2_assigned_epoch_lock') ORDER BY 1,2,3",
        "SELECT member::regrole::text,roleid::regrole::text,admin_option,inherit_option,set_option FROM pg_auth_members ORDER BY 1,2",
        "SELECT version,sha256 FROM ra4a_private.migrations ORDER BY version",
    ]
    return hashlib.sha256(
        json.dumps([c.execute(q).fetchall() for q in queries], default=str, sort_keys=True).encode()
    ).hexdigest()


def admit(r, key, source="accepted-404"):
    cfg = r["held"]["APP"]
    with closing(http.client.HTTPConnection("127.0.0.1", 8765, timeout=5)) as c:
        c.request(
            "POST",
            "/v1/audit-requests",
            json.dumps({"source_ref": source}),
            {
                "Host": "127.0.0.1:8765",
                "Origin": "http://127.0.0.1:8765",
                "Authorization": "Bearer " + cfg["bearer"],
                "Content-Type": "application/json",
                "Idempotency-Key": key,
            },
        )
        response = c.getresponse()
        result = json.loads(response.read())
    assert response.status == 202
    return result


def private_worker_ipc(r):
    # Match the accepted same-UID helper pattern; the supervisor deliberately
    # has neither CAP_DAC_OVERRIDE nor CAP_DAC_READ_SEARCH.
    p = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; sys.stdout.buffer.write(Path(sys.argv[1]).read_bytes())",
            r["held"]["S2_WORKER_RECEIPT_PATH"],
        ],
        user=10002,
        group=10002,
        extra_groups=[],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return json.loads(p.stdout)


@pytest.fixture(scope="module")
def experiment(runtime):
    r = runtime
    with support.connect() as c:
        before = fingerprint(c)
        c.execute((ROOT / "db/ra4b_p2/001_isolated_interfaces.sql").read_text())
        # Input bytes only. No old report/graph is registered as this job's result.
        for case in ("404", "200"):
            original = inputs(case)
            raw = original.source
            src = json.loads(raw)
            ref = c.execute(
                "SELECT tenant_id,policy_id,policy_version,ref_sha256,metadata FROM ra4a.references WHERE ref_id=%s",
                ("accepted-" + case,),
            ).fetchone()
            assert hashlib.sha256(raw).hexdigest() == ref[4]["source_record_sha256"]
            audit, policy = fixture("AuditRequest"), fixture("SourcePolicy")
            audit.update(
                tenant_id=ref[0],
                source_policy_ref=ref[1],
                source_policy_version=ref[2],
                site_url=src["pack"]["sources"][0]["document"]["pages"][0]["snapshot"]["url"],
            )
            expiry = c.execute(
                "SELECT expires_at FROM ra4a.policies WHERE tenant_id=%s AND policy_id=%s AND version=%s",
                ref[:3],
            ).fetchone()[0]
            policy.update(
                tenant_id=ref[0],
                policy_id=ref[1],
                policy_version=ref[2],
                permitted_hosts=[urlsplit(audit["site_url"]).hostname],
                scope_paths=["/"],
                expires_at=expiry.isoformat(),
                revoked_at=None,
            )
            c.execute(
                "INSERT INTO ra4b_p2.raw_inputs(tenant_id,source_ref,reference_sha256,source_record,policy_document,audit_document) VALUES(%s,%s,%s,%s,%s,%s)",
                (ref[0], "accepted-" + case, ref[3], raw, Jsonb(policy), Jsonb(audit)),
            )
        pred = c.execute(
            "SELECT pg_get_functiondef('ra4b_p2.current_generated_binding(text,uuid,name,bigint)'::regprocedure),prosecdef FROM pg_proc WHERE oid='ra4b_p2.current_generated_binding(text,uuid,name,bigint)'::regprocedure"
        ).fetchone()
        assert not pred[1] and "origin_epochs" not in pred[0] and "request_origins" not in pred[0]
        c.execute((ROOT / "db/ra4b_p2/002_conditional_origin_policies.sql").read_text())
        assert fingerprint(c) == before
        actual = c.execute(
            "SELECT policyname FROM pg_policies WHERE schemaname='ra4b_test' AND policyname LIKE 's2_%'"
        ).fetchall()
        assert {x[0] for x in actual} == NEW_POLICIES
        r["protected_catalog_before_after"] = before
        # Competing read/DML probes are fixture-only, never the authoritative API.
        c.execute(
            "CREATE FUNCTION ra4b_p2.probe_epoch_lock() RETURNS bigint LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT count(*) FROM (SELECT epoch FROM ra4b_test.origin_epochs FOR SHARE) x $$; ALTER FUNCTION ra4b_p2.probe_epoch_lock() OWNER TO ra4a_owner; REVOKE ALL ON FUNCTION ra4b_p2.probe_epoch_lock() FROM PUBLIC; GRANT EXECUTE ON FUNCTION ra4b_p2.probe_epoch_lock() TO p2b1_review"
        )
        c.execute(
            "CREATE TABLE ra4b_p2.reference_format_probe(LIKE ra4a.references INCLUDING CONSTRAINTS)"
        )
    r["interface_denials"] = []
    try:
        yield r
    finally:
        with support.connect() as c:
            assert fingerprint(c) == before
            counts = c.execute(
                "SELECT (SELECT count(*) FROM ra4b_p2.candidate_bindings),(SELECT count(*) FROM ra4b_p2.sealed_bindings),(SELECT count(*) FROM ra4b_p2.result_audit),(SELECT count(*) FROM ra4b_p2.result_outbox)"
            ).fetchone()
        assert counts[1:] == (0, 0, 0)
        (OUT / "interface-proof.json").write_text(
            json.dumps(
                {
                    "kind": "UNSEALED_INTERFACE_EXPERIMENT_NOT_B3_PASS",
                    "protected_catalog_unchanged_except_three_policies": True,
                    "candidate_rows": counts[0],
                    "trusted_sealed_rows": 0,
                    "generated_finish_audit_outbox": 0,
                    "denials": r["interface_denials"],
                    "conditional_policies": sorted(NEW_POLICIES),
                    "positive_trusted_row_lock": "NOT_PERFORMED_REGISTRATION_HOLD",
                },
                indent=2,
            )
        )


def test_00_real_low_uid_worker_generates_unsealed_same_job_candidate(experiment):
    r = experiment
    request = admit(r, "s2-interfaces-actual-0001")
    p = r["spawn"]("S2_WORKER")
    p.wait(timeout=90)  # New fixture process startup/import budget, NOT DB lease or Chromium.
    assert p.returncode == 0
    with support.connect() as c:
        row = c.execute(
            "SELECT request_id,run_id,job_id,worker_role,stage,candidate,source_record,html,lease_seq FROM ra4b_p2.candidate_bindings"
        ).fetchone()
        assert tuple(str(v) for v in row[:4]) == (
            request["request_id"],
            request["run_id"],
            request["job_id"],
            "ra4b_test_a_worker",
        )
        assert row[4] == "UNSEALED_CANDIDATE" and row[8] == 1
        stored = (bytes(row[5]), bytes(row[7]), bytes(row[6]))
    # Private same-UID IPC from the actual producer, never an admin-supplied
    # lease/source/output. No token or bytes reach browser or console.
    ipc = private_worker_ipc(r)
    candidate = GeneratedCandidate(
        base64.b64decode(ipc["candidate"]),
        base64.b64decode(ipc["html"]),
        base64.b64decode(ipc["source"]),
    )
    assert stored == (candidate._payload, candidate._html, candidate._source)
    j = tuple(
        [UUID(v) for v in ipc["lease"][:3]]
        + [ipc["lease"][3], datetime.fromisoformat(ipc["lease"][4])]
    )
    r["held"].setdefault("extra_secret_values", []).append(str(j[2]))
    doc = candidate.private_document
    assert (
        doc["scope"]["run_id"] == request["run_id"]
        and doc["report"]["metadata"]["report_id"] == "job-" + request["job_id"]
    )
    assert doc["versions"]["guard"] == "ra3b-disc-1.0.0" and not doc["committed"]
    assert (
        doc["report"]["issues"]
        and doc["report"]["issues"][0]["fact_claim"]["fact"]["rule_id"] == "CTA-02"
    )
    r["request"] = request
    r["lease"] = j
    r["candidate"] = candidate
    with store.connect(bootstrap.config("WORKER")) as c:
        assert stage(c, "tenant-test", j, candidate)["status"] == "S2_REGISTRATION_HOLD"


@pytest.mark.parametrize("mutation", ["tenant", "job", "token", "sequence"])
def test_wrong_lease_identity_or_tenant_denied(experiment, mutation):
    lease = list(experiment["lease"])
    tenant = "tenant-test"
    if mutation == "tenant":
        tenant = "tenant-beta"
    elif mutation == "job":
        lease[0] = uuid4()
    elif mutation == "token":
        lease[2] = uuid4()
    else:
        lease[3] += 1
    with store.connect(bootstrap.config("WORKER")) as c:
        with pytest.raises(psycopg.Error) as error:
            load(c, tenant, lease)
    assert error.value.sqlstate == "42501"


@pytest.mark.parametrize(
    "mutation", ["source", "guard", "report_sha", "html", "actor", "committed"]
)
def test_mutated_candidate_never_becomes_trusted(experiment, mutation):
    old = experiment["candidate"]
    d = old.private_document
    html = old._html
    if mutation == "source":
        d["binding"]["source_ref"] = "foreign-source"
    elif mutation == "guard":
        d["versions"]["guard"] = "ra3b-1.0.0"
    elif mutation == "report_sha":
        d["report_sha256"] = "0" * 64
    elif mutation == "html":
        html += b"bad"
    elif mutation == "actor":
        d["binding"]["worker"] = "ra4b_test_b_worker"
    else:
        d["committed"] = True
    candidate = GeneratedCandidate(encode(d), html, old._source)
    with store.connect(bootstrap.config("WORKER")) as c:
        with pytest.raises(psycopg.Error) as error:
            stage(c, "tenant-test", experiment["lease"], candidate)
    assert error.value.sqlstate == "22023"


def test_policy_revoke_waits_for_actual_worker_transaction_then_denies(experiment):
    cfg = bootstrap.config("WORKER")
    observed = []
    errors = []

    def revoke():
        try:
            with support.connect() as c:
                observed.append(c.info.backend_pid)
                c.execute("UPDATE ra4a.policies SET status='REVOKED' WHERE tenant_id='tenant-test'")
        except BaseException as e:
            errors.append(type(e).__name__)

    with store.connect(cfg) as c:
        with c.transaction():
            load(c, "tenant-test", experiment["lease"])
            pid = c.info.backend_pid
            thread = threading.Thread(target=revoke)
            thread.start()
            deadline = time.monotonic() + 1
            blocked = False
            while time.monotonic() < deadline:
                if observed:
                    with support.connect() as observer:
                        blocked = (
                            pid
                            in observer.execute(
                                "SELECT pg_blocking_pids(%s)", (observed[0],)
                            ).fetchone()[0]
                        )
                    if blocked:
                        break
                time.sleep(0.01)
            assert blocked
        thread.join(timeout=3)
        assert not thread.is_alive() and not errors
        with pytest.raises(psycopg.Error) as error:
            load(c, "tenant-test", experiment["lease"])
        assert error.value.sqlstate == "42501"
    with support.connect() as c:
        c.execute("UPDATE ra4a.policies SET status='ALLOWED' WHERE tenant_id='tenant-test'")
    experiment["interface_denials"].append(
        {
            "stage": "POLICY_REVOKE_REAL_LOCK_ORDER",
            "worker_blocker_observed": True,
            "sqlstate": "42501",
        }
    )


def test_old_done_and_staged_bytes_still_do_not_make_a_generated_result(experiment):
    cfg = bootstrap.config("WORKER")
    with store.connect(cfg) as c:
        store.finish(c, cfg, experiment["lease"])
        with pytest.raises(psycopg.Error) as error:
            stage(c, "tenant-test", experiment["lease"], experiment["candidate"])
        assert error.value.sqlstate == "42501"
    with support.connect("p2b1_test_a_reviewer") as c:
        with pytest.raises(psycopg.Error) as error:
            c.execute(
                "SELECT * FROM ra4b_p2.read_assigned_generated_result(%s,%s,%s,1,%s)",
                (
                    "tenant-test",
                    experiment["request"]["job_id"],
                    "job-" + experiment["request"]["job_id"],
                    "0" * 64,
                ),
            )
        assert error.value.sqlstate == "42501"


@pytest.mark.parametrize(
    "role",
    ["ra4b_test_a_worker", "p2b1_test_a_reviewer", "p2b1_test_a_peer", "p2b1_test_b_reviewer"],
)
@pytest.mark.parametrize("table", ["candidate_bindings", "sealed_bindings", "raw_inputs"])
def test_raw_new_tables_still_42501(experiment, role, table):
    with support.connect(role) as c:
        for command in ("SELECT * FROM ", "UPDATE "):
            query = (
                command
                + "ra4b_p2."
                + table
                + (" SET tenant_id=tenant_id" if command == "UPDATE " else "")
            )
            with pytest.raises(psycopg.Error) as error:
                c.execute(query)
            assert error.value.sqlstate == "42501"


@pytest.mark.parametrize(
    "role", ["p2b1_test_a_reviewer", "p2b1_test_a_peer", "p2b1_test_b_reviewer"]
)
def test_no_boolean_or_done_substitute_for_reviewer_read(experiment, role):
    request = experiment["request"]
    report = "job-" + request["job_id"]
    if role == "p2b1_test_a_reviewer":
        with support.connect() as c:
            c.execute(
                "INSERT INTO ra4a_review_test.assignments VALUES('tenant-test',%s,%s,true,'TEST_ONLY')",
                (report, role),
            )
    with support.connect(role) as c:
        assert c.execute("SELECT ra4b_p2.probe_epoch_lock()").fetchone() == (0,)
        with pytest.raises(psycopg.Error) as error:
            c.execute(
                "SELECT * FROM ra4b_p2.read_assigned_generated_result(%s,%s,%s,%s,%s)",
                ("tenant-test", request["job_id"], report, 1, "0" * 64),
            )
        assert error.value.sqlstate == "42501"


def test_original_register_remains_fixture_writer_only(experiment):
    # A fixture-owned definer changes CURRENT_USER, never genuine SESSION_USER.
    with support.connect() as c:
        c.execute(
            "CREATE FUNCTION ra4b_p2.probe_original_registration() RETURNS text LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT ra4a_bytes.register('tenant-test','held-new-output',NULL,NULL,NULL,NULL,NULL) $$; ALTER FUNCTION ra4b_p2.probe_original_registration() OWNER TO ra4a_owner; REVOKE ALL ON FUNCTION ra4b_p2.probe_original_registration() FROM PUBLIC; GRANT EXECUTE ON FUNCTION ra4b_p2.probe_original_registration() TO ra4b_worker"
        )
    with store.connect(bootstrap.config("WORKER")) as c:
        with pytest.raises(psycopg.Error) as error:
            c.execute("SELECT ra4b_p2.probe_original_registration()")
        assert (
            error.value.sqlstate == "42501"
            and error.value.diag.message_primary == "P2A_FIXTURE_WRITER_ONLY"
        )
    experiment["interface_denials"].append(
        {"stage": "ORIGINAL_REGISTER", "sqlstate": "42501", "reason": "P2A_FIXTURE_WRITER_ONLY"}
    )


def test_new_authority_rejected_by_exact_original_reference_check_copy(experiment):
    # Only new ra4b_p2 table is written. No protected reference INSERT is tried.
    with support.connect() as c:
        columns = c.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='ra4a' AND table_name='references' ORDER BY ordinal_position"
        ).fetchall()
        names = [v[0] for v in columns]
        row = list(
            c.execute("SELECT * FROM ra4a.references WHERE ref_id='accepted-404'").fetchone()
        )
        i = names.index("metadata")
        metadata = dict(row[i])
        metadata["authority"] = "TEST_ONLY_WORKER_GENERATED_SOURCE"
        row[i] = Jsonb(metadata)
        with pytest.raises(psycopg.Error) as error:
            c.execute(
                "INSERT INTO ra4b_p2.reference_format_probe VALUES("
                + ",".join(["%s"] * len(row))
                + ")",
                row,
            )
        assert error.value.sqlstate == "23514"
        name = error.value.diag.constraint_name
    experiment["interface_denials"].append(
        {"stage": "EXACT_LEGACY_CHECK_COPY_ONLY", "sqlstate": "23514", "constraint": name}
    )


def test_private_predicate_and_admin_boolean_seeding_are_denied(experiment):
    request = experiment["request"]
    with support.connect() as c:
        for role in ("ra4b_test_a_worker", "p2b1_test_a_reviewer"):
            assert c.execute(
                "SELECT has_function_privilege(%s,'ra4b_p2.current_generated_binding(text,uuid,name,bigint)','EXECUTE')",
                (role,),
            ).fetchone() == (False,)
        with pytest.raises(psycopg.Error) as error:
            c.execute(
                "INSERT INTO ra4b_p2.sealed_bindings(tenant_id,job_id,lease_seq,generated_ref,report_id,report_version,target_digest,manifest_sha256,finish_event,transaction_id) VALUES('tenant-test',%s,1,'forged-result',%s,1,repeat('0',64),repeat('0',64),gen_random_uuid(),txid_current())",
                (request["job_id"], "job-" + request["job_id"]),
            )
        assert error.value.sqlstate == "42501"


@pytest.mark.parametrize("table", ["origin_epochs", "request_origins"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "INSERT"])
def test_original_origin_dml_denied_even_inside_competing_owner_definer(
    experiment, table, operation
):
    name = "probe_" + table + "_" + operation.lower()
    if operation == "UPDATE":
        statement = "UPDATE ra4b_test." + table + " SET epoch=epoch"
    elif operation == "DELETE":
        statement = "DELETE FROM ra4b_test." + table
    elif table == "origin_epochs":
        statement = "INSERT INTO ra4b_test.origin_epochs VALUES('tenant-test','ra4b_test_a_app',1)"
    else:
        statement = (
            "INSERT INTO ra4b_test.request_origins VALUES('tenant-test','"
            + experiment["request"]["request_id"]
            + "','ra4b_test_a_app',1)"
        )
    with support.connect() as c:
        c.execute(
            "CREATE FUNCTION ra4b_p2."
            + name
            + "() RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ DECLARE n bigint; BEGIN "
            + statement
            + "; GET DIAGNOSTICS n=ROW_COUNT; RETURN n; END $$"
        )
        c.execute("ALTER FUNCTION ra4b_p2." + name + "() OWNER TO ra4a_owner")
        c.execute("REVOKE ALL ON FUNCTION ra4b_p2." + name + "() FROM PUBLIC")
        c.execute("GRANT EXECUTE ON FUNCTION ra4b_p2." + name + "() TO p2b1_review")
        before = c.execute("SELECT * FROM ra4b_test." + table + " ORDER BY 1,2").fetchall()
    with support.connect("p2b1_test_a_reviewer") as c:
        if operation == "INSERT":
            with pytest.raises(psycopg.Error) as error:
                c.execute("SELECT ra4b_p2." + name + "()")
            assert error.value.sqlstate == "42501"
        else:
            assert c.execute("SELECT ra4b_p2." + name + "()").fetchone() == (0,)
    with support.connect() as c:
        assert c.execute("SELECT * FROM ra4b_test." + table + " ORDER BY 1,2").fetchall() == before
        c.execute("DROP FUNCTION ra4b_p2." + name + "()")


def test_new_200_worker_candidate_is_coverage_not_an_old_report_copy(experiment):
    request = admit(experiment, "s2-interfaces-actual-0002", "accepted-200")
    p = experiment["spawn"]("S2_WORKER")
    p.wait(timeout=90)
    assert p.returncode == 0
    ipc = private_worker_ipc(experiment)
    doc = json.loads(base64.b64decode(ipc["candidate"]))
    assert doc["scope"]["run_id"] == request["run_id"] and doc["report"]["issues"] == []
    assert (
        doc["report"]["metadata"]["report_id"] == "job-" + request["job_id"]
        and not doc["committed"]
    )
    lease = tuple(
        [UUID(v) for v in ipc["lease"][:3]]
        + [ipc["lease"][3], datetime.fromisoformat(ipc["lease"][4])]
    )
    experiment["held"]["extra_secret_values"].append(str(lease[2]))
    cfg = bootstrap.config("WORKER")
    with store.connect(cfg) as c:
        store.finish(c, cfg, lease)


def test_expired_replayed_lease_then_actual_reclaim_remains_untrusted(experiment):
    request = admit(experiment, "s2-interfaces-expiry-0003")
    cfg = bootstrap.config("WORKER")
    with store.connect(cfg) as c:
        lease = store.claim(c, cfg, 1)
        assert str(lease[0]) == request["job_id"]
        c.execute("SELECT pg_sleep(1.1)")
        with pytest.raises(psycopg.Error) as error:
            load(c, "tenant-test", lease)
        assert error.value.sqlstate == "42501"
        new = store.claim(c, cfg, 30)
        assert new[0] == lease[0] and new[3] == lease[3] + 1
        with pytest.raises(psycopg.Error) as error:
            load(c, "tenant-test", lease)
        assert error.value.sqlstate == "42501"
        store.finish(c, cfg, new)


def test_z_origin_epoch_rollover_denies_old_request_without_reseeding(experiment):
    with support.connect() as c:
        before = c.execute(
            "SELECT epoch FROM ra4b_test.origin_epochs WHERE tenant_id='tenant-test'"
        ).fetchone()[0]
        c.execute(
            "UPDATE ra4a_private.principals SET enabled=false WHERE db_role='ra4b_test_a_app'"
        )
        after = c.execute(
            "SELECT epoch FROM ra4b_test.origin_epochs WHERE tenant_id='tenant-test'"
        ).fetchone()[0]
    assert after == before + 1
    with store.connect(bootstrap.config("WORKER")) as c:
        with pytest.raises(psycopg.Error) as error:
            load(c, "tenant-test", experiment["lease"])
        assert error.value.sqlstate == "42501"
    experiment["interface_denials"].append(
        {"stage": "ORIGIN_ROLLOVER", "before": before, "after": after, "sqlstate": "42501"}
    )
