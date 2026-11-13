"""Numbered P2B1 actual PG cases; no mocks, skips or production identities."""

import hashlib
import json
import os
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from integration.ra4a.p2a_support import add_reference
from integration.ra4a.p2b1_support import (
    STATE,
    TABLES,
    connect,
    counts,
    fingerprint,
    graph,
    proposal,
    raw_submit,
    register_graph,
    submit,
    verify_migrations,
)
from vrae.persistence.contracts import PersistenceError
from vrae.persistence.private_bytes import locator
from vrae.persistence.review_cas import AUTHORITY, production_review_port
from vrae.reviewing import ReviewError, ReviewTarget, validate_proposal
from vrae.reviewing.canonical import canonical

ACTIONS = ("APPROVE_CANDIDATE", "REQUEST_CHANGES", "REJECT")


def changed(cmd, mutate):
    d = cmd.document
    mutate(d)
    return type(cmd)(canonical(d, limit=131072))


def empty(c):
    assert counts(c) == dict.fromkeys(TABLES, 0)


def one(c, g=None):
    t = ReviewTarget((g or graph()).target).document
    assert counts(c) == {
        "states": 1,
        "proposals": 1,
        "claims": len(t["claims"]),
        "sections": len(t["required_sections"]),
        "audit": 1,
        "outbox": 1,
    }


@pytest.mark.parametrize("action", ACTIONS)
def test_b01_native_claims_sections_and_no_native_approval(isolated, action):
    name, admin = isolated
    g = graph()
    before = admin.execute(
        "SELECT kind,object_key,raw FROM ra4a_bytes.objects ORDER BY kind,object_key"
    ).fetchall()
    cmd = proposal(g, action)
    r = submit(name, g, cmd).document
    expected = {
        "APPROVE_CANDIDATE": "SIMULATED_APPROVE_CANDIDATE",
        "REQUEST_CHANGES": "SIMULATED_CHANGES_REQUESTED",
        "REJECT": "SIMULATED_REJECTED",
    }[action]
    assert r["status"] == expected and r["authority"] == AUTHORITY
    assert r["native_decision"] is r["native_approval"] is r["share_grant"] is None
    assert r["external_visibility"] is False and r["durable"] is True
    assert r["command_digest"] == validate_proposal(cmd, ReviewTarget(g.target))
    assert r["db_actor"] == "p2b1_test_a_reviewer" and r["review_seq"] == r["report_event_seq"] == 1
    assert admin.execute(
        "SELECT issue_count FROM ra4a.references WHERE ref_id='accepted-404'"
    ).fetchone() == (1,)
    one(admin)
    rows = admin.execute(
        "SELECT guard_ref,binding_ref,pointer,disposition,machine_status,allowed_acceptance FROM ra4a_review_test.claims ORDER BY ordinal"
    ).fetchall()
    for row, disposition in zip(rows, cmd.document["dispositions"], strict=True):
        assert row[:4] == tuple(
            disposition[k] for k in ("guard_ref", "binding_ref", "pointer", "disposition")
        )
        original = next(
            c
            for c in ReviewTarget(g.target).document["claims"]
            if c["pointer"] == row[2] and c["binding_ref"] == row[1]
        )
        assert row[4:] == (original["machine_status"], original["allowed_acceptance"])
    assert (
        before
        == admin.execute(
            "SELECT kind,object_key,raw FROM ra4a_bytes.objects ORDER BY kind,object_key"
        ).fetchall()
    )
    assert admin.execute(
        "SELECT bool_and(visibility='PRIVATE_NOT_APPROVED') FROM ra4a.references"
    ).fetchone() == (True,)
    assert admin.execute(
        "SELECT bool_and(undelivered) FROM ra4a_review_test.outbox"
    ).fetchone() == (True,)
    out = Path(os.environ["RA4A_P2B1_EVIDENCE_DIR"])
    (out / (action + "-receipt.json")).write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8")


def test_b02_zero_is_only_internal_scope_ack(isolated):
    name, admin = isolated
    g = graph("200")
    r = submit(name, g).document
    assert r["status"] == "SIMULATED_INTERNAL_SCOPE_ACK" and r["native_decision"] is None
    target = ReviewTarget(g.target).document
    assert target["kind"] == "COVERAGE_ONLY"
    # Zero findings still has literal scope/limitation Claims to acknowledge.
    # Do not drop those accepted native Claims or invent an empty claim set.
    assert all(c["allowed_acceptance"].startswith("ACK_") for c in target["claims"])
    one(admin, g)
    assert admin.execute(
        "SELECT issue_count,native_h0,native_id FROM ra4a.references WHERE ref_id='accepted-200'"
    ).fetchone() == (0, None, None)


def test_b03_retry_exact_durable_bytes_without_double_event(isolated):
    name, admin = isolated
    first = submit(name).payload
    fp = fingerprint(admin)
    assert submit(name).payload == first and fingerprint(admin) == fp
    one(admin)


@pytest.mark.parametrize("collision", ("payload", "actor", "source"))
def test_b04_key_conflicts(isolated, collision):
    name, admin = isolated
    submit(name)
    g = graph()
    cmd = proposal(g)
    role = "p2b1_test_a_reviewer"
    if collision == "payload":
        cmd = changed(cmd, lambda d: d.update(reason="Different actual payload"))
    if collision == "actor":
        role = "p2b1_test_a_peer"
    if collision == "source":
        g = add_reference(admin, version=2)
        register_graph(name, g)
        cmd = proposal(g)
    before = fingerprint(admin)
    with pytest.raises(psycopg.Error):
        submit(name, g, cmd, role)
    assert fingerprint(admin) == before


@pytest.mark.parametrize("action", ACTIONS)
def test_b05_closed_round_and_new_version(isolated, action):
    name, admin = isolated
    old = proposal(action=action)
    submit(name, cmd=old)
    with pytest.raises(psycopg.Error):
        submit(name, cmd=proposal(key="new-command-key"))
    newer = add_reference(admin, version=2)
    register_graph(name, newer)
    r = submit(name, newer, proposal(newer, key="new-version-key")).document
    assert r["report_version"] == 2 and r["review_seq"] == 1 and r["report_event_seq"] == 2
    with pytest.raises(psycopg.Error):
        submit(name, cmd=old)
    assert admin.execute(
        "SELECT last_closed_version,report_event_seq FROM ra4a_review_test.states"
    ).fetchone() == (2, 2)


@pytest.mark.parametrize("seq", (1, 9999, True, -1))
def test_b06_bad_expected_sequence(isolated, seq):
    name, admin = isolated
    cmd = changed(proposal(), lambda d: d.update(expected_review_seq=seq))
    with pytest.raises((ReviewError, psycopg.Error)):
        submit(name, cmd=cmd)
    with connect("p2b1_test_a_reviewer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_submit(c, graph(), cmd)
    empty(admin)


@pytest.mark.parametrize("table", ("assignments", *TABLES))
@pytest.mark.parametrize("role", ("p2b1_test_a_reviewer", "p2b1_test_b_reviewer"))
def test_b07_direct_table_capabilities_denied(isolated, table, role):
    name, admin = isolated
    with connect(role, dbname=name) as c:
        for query in (
            "SELECT * FROM {}",
            "INSERT INTO {} DEFAULT VALUES",
            "UPDATE {} SET tenant_id='tenant-beta'",
            "DELETE FROM {}",
            "TRUNCATE {} CASCADE",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(sql.SQL(query).format(sql.Identifier("ra4a_review_test", table)))
    empty(admin)


@pytest.mark.parametrize(
    "role", ("p2b1_test_b_reviewer", "ra4a_test_a_app", "p2a_test_a_writer", "ra4a_test_unassigned")
)
def test_b08_cross_tenant_and_nonreviewer_denied(isolated, role):
    name, admin = isolated
    with connect(role, dbname=name) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        raw_submit(c, graph(), proposal())
    empty(admin)


@pytest.mark.parametrize(
    "attack",
    ("SET ROLE ra4a_owner", "SET ROLE p2b1_test_a_peer", "SET SESSION AUTHORIZATION postgres"),
)
def test_b09_role_impersonation_denied(isolated, attack):
    name, admin = isolated
    with connect("p2b1_test_b_reviewer", dbname=name) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute(attack)
        c.execute(
            "SELECT set_config('app.tenant_id','tenant-test',false),set_config('app.actor','p2b1_test_a_reviewer',false)"
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            raw_submit(c, graph(), proposal())
    empty(admin)


REVOKES = (
    "UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'",
    "UPDATE ra4a_private.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'",
    "UPDATE ra4a_private.principals SET enabled=false WHERE db_role='p2b1_test_a_reviewer'",
    "UPDATE ra4a.policies SET status='REVOKED'",
    "UPDATE ra4a.policies SET status='UNKNOWN'",
    "UPDATE ra4a.policies SET expires_at=clock_timestamp()-interval '1 second'",
)


@pytest.mark.parametrize(
    "revoke",
    REVOKES,
    ids=("report-assignment", "tenant-assignment", "principal", "revoked", "unknown", "expired"),
)
def test_b10_revocation_rechecked_even_on_exact_retry(isolated, revoke):
    name, admin = isolated
    submit(name)
    before = fingerprint(admin)
    admin.execute(revoke)
    with pytest.raises(psycopg.Error):
        submit(name)
    assert fingerprint(admin) == before


MUTATIONS = {
    "missing-claim": lambda d: d["dispositions"].pop(),
    "duplicate-claim": lambda d: d["dispositions"].__setitem__(1, d["dispositions"][0].copy()),
    "foreign-guard": lambda d: d["dispositions"][0].update(guard_ref="forged"),
    "foreign-binding": lambda d: d["dispositions"][0].update(binding_ref="forged"),
    "altered-source-range": lambda d: d["dispositions"][0].update(pointer="/source/999:1000"),
    "hypothesis-to-fact": lambda d: next(
        x for x in d["dispositions"] if x["disposition"] == "ACCEPT_AS_HYPOTHESIS"
    ).update(disposition="ACCEPT_AS_FACT"),
    "missing-section": lambda d: d["sections"].pop(),
    "duplicate-section": lambda d: d["sections"].__setitem__(1, d["sections"][0].copy()),
    "false-ack": lambda d: d["sections"][0].update(acknowledged=False),
    "foreign-section-digest": lambda d: d["sections"][0].update(target_digest="0" * 64),
    "native-approval": lambda d: d.update(native_approval="APPROVED"),
    "fake-actor": lambda d: d.update(actor={"role": "REVIEWER", "verified": True}),
    "boolean-version": lambda d: d.update(report_version=True),
    "wrong-target": lambda d: d.update(target_digest="0" * 64),
    "wrong-tenant": lambda d: d.update(tenant_id="tenant-beta"),
    "reason-long": lambda d: d.update(reason="a" * 2001),
    "reason-blank": lambda d: d.update(reason="  "),
    "reason-bidi": lambda d: d.update(reason="review\u202eforged"),
    "reason-control": lambda d: d.update(reason="review\x01forged"),
    "reason-not-string": lambda d: d.update(reason={"approval": True}),
}


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_b11_native_and_raw_sql_refuse_mutated_claim_command(isolated, mutation):
    name, admin = isolated
    cmd = changed(proposal(), MUTATIONS[mutation])
    with pytest.raises(ReviewError):
        submit(name, cmd=cmd)
    with connect("p2b1_test_a_reviewer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_submit(c, graph(), cmd)
    empty(admin)


@pytest.mark.parametrize("case", ("404", "200"))
def test_b12_coverage_and_review_substitution(isolated, case):
    name, admin = isolated
    other = graph("200" if case == "404" else "404")
    with pytest.raises(ReviewError):
        submit(name, graph(case), proposal(other))
    with connect("p2b1_test_a_reviewer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_submit(c, graph(case), proposal(other))
    empty(admin)


@pytest.mark.parametrize("kind", ("HTML", "GUARD", "SOURCE_OBJECT", "TARGET"))
def test_b13_recomputed_hash_corruption_refused_by_both_paths(isolated, kind):
    name, admin = isolated
    # Explicit privileged clone-only fault. Runtime cannot modify these tables.
    admin.execute("ALTER TABLE ra4a_bytes.objects DISABLE TRIGGER immutable_bytes")
    admin.execute(
        "UPDATE ra4a_bytes.objects SET raw=raw||decode('20','hex') WHERE kind=%s", (kind,)
    )
    admin.execute("ALTER TABLE ra4a_bytes.objects ENABLE TRIGGER immutable_bytes")
    with pytest.raises((PersistenceError, ReviewError)):
        submit(name)
    with connect("p2b1_test_a_reviewer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_submit(c, graph(), proposal())
    empty(admin)


def fault(admin, table, body):
    admin.execute(
        "CREATE FUNCTION public.p2b1_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        + body
        + "; RETURN NEW; END $$"
    )
    admin.execute(
        sql.SQL(
            "CREATE TRIGGER fault BEFORE INSERT ON {} FOR EACH ROW EXECUTE FUNCTION public.p2b1_fault()"
        ).format(sql.Identifier("ra4a_review_test", table))
    )


@pytest.mark.parametrize("table", ("claims", "sections", "outbox"))
def test_b14_failure_rolls_back_every_record(isolated, table):
    name, admin = isolated
    fault(admin, table, "RAISE EXCEPTION 'P2B1_INJECTED_FAILURE'")
    with pytest.raises(psycopg.errors.RaiseException):
        submit(name)
    empty(admin)


def test_b15_explicit_rollback_and_uncommitted_visibility(isolated):
    name, admin = isolated
    with connect("p2b1_test_a_reviewer", dbname=name) as c:
        c.execute("BEGIN")
        raw_submit(c, graph(), proposal())
        empty(admin)
        c.execute("ROLLBACK")
    empty(admin)
    submit(name)
    one(admin)


def wait_for(admin, pid, event):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        row = admin.execute(
            "SELECT wait_event FROM pg_stat_activity WHERE pid=%s", (pid,)
        ).fetchone()
        if row and row[0] == event:
            return
        time.sleep(0.025)
    raise AssertionError("Actual DB session did not reach " + event)


@pytest.mark.parametrize("table", ("claims", "sections", "outbox"))
def test_b16_backend_kill_before_commit_is_atomic(isolated, table):
    name, admin = isolated
    fault(admin, table, "PERFORM pg_sleep(20)")
    c = connect("p2b1_test_a_reviewer", dbname=name)
    try:
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(raw_submit, c, graph(), proposal())
            wait_for(admin, c.info.backend_pid, "PgSleep")
            assert admin.execute(
                "SELECT pg_terminate_backend(%s)", (c.info.backend_pid,)
            ).fetchone() == (True,)
            with pytest.raises(psycopg.OperationalError):
                future.result(timeout=10)
    finally:
        c.close()
    empty(admin)
    admin.execute(
        sql.SQL("DROP TRIGGER fault ON {}").format(sql.Identifier("ra4a_review_test", table))
    )
    submit(name)
    one(admin)


def test_b17_committed_response_lost_retry_is_exact(isolated):
    name, admin = isolated
    c = connect("p2b1_test_a_reviewer", dbname=name)
    first = raw_submit(c, graph(), proposal())
    assert admin.execute("SELECT pg_terminate_backend(%s)", (c.info.backend_pid,)).fetchone() == (
        True,
    )
    c.close()
    fp = fingerprint(admin)
    assert submit(name).payload == first and fingerprint(admin) == fp
    one(admin)


@pytest.mark.parametrize("opponent", ("REQUEST_CHANGES", "REJECT", "SAME"))
def test_b18_real_simultaneous_connections(isolated, opponent):
    name, admin = isolated
    barrier = threading.Barrier(2)

    def run(second):
        cmd = proposal(
            action=opponent if second and opponent != "SAME" else "APPROVE_CANDIDATE",
            key="other-race-key" if second and opponent != "SAME" else "same-race-key",
        )
        barrier.wait(timeout=10)
        try:
            return ("commit", submit(name, cmd=cmd).payload)
        except psycopg.Error as e:
            return ("refused", e.sqlstate)

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(run, i) for i in (False, True)]
        results = [f.result(timeout=25) for f in futures]
    assert sorted(r[0] for r in results) == (
        ["commit", "commit"] if opponent == "SAME" else ["commit", "refused"]
    )
    if opponent == "SAME":
        assert results[0][1] == results[1][1]
    one(admin)


@pytest.mark.parametrize("winner", ACTIONS)
def test_b19_adversarial_commit_order(isolated, winner):
    name, admin = isolated
    admin.execute("SELECT pg_advisory_lock(717001)")
    fault(
        admin,
        "proposals",
        "IF SESSION_USER='p2b1_test_a_reviewer' THEN PERFORM pg_advisory_xact_lock(717001); END IF",
    )
    c = connect("p2b1_test_a_reviewer", dbname=name)
    from vrae.persistence.review_cas import TestOnlyReviewCAS

    api = TestOnlyReviewCAS(c, mode="TEST_ONLY_P2B1_REVIEW_CAS")
    with c, ThreadPoolExecutor(2) as pool:
        first = pool.submit(
            api.submit, locator(graph()), proposal(action=winner), provenance=graph()
        )
        wait_for(admin, c.info.backend_pid, "advisory")
        second = pool.submit(
            submit,
            name,
            graph(),
            proposal(
                action="REJECT" if winner != "REJECT" else "APPROVE_CANDIDATE",
                key="peer-ordered-key",
            ),
            "p2b1_test_a_peer",
        )
        admin.execute("SELECT pg_advisory_unlock(717001)")
        assert (
            first.result(timeout=15).document["status"]
            == {
                "APPROVE_CANDIDATE": "SIMULATED_APPROVE_CANDIDATE",
                "REQUEST_CHANGES": "SIMULATED_CHANGES_REQUESTED",
                "REJECT": "SIMULATED_REJECTED",
            }[winner]
        )
        with pytest.raises(psycopg.Error):
            second.result(timeout=15)
    one(admin)


@pytest.mark.parametrize("revoke", (REVOKES[0], REVOKES[3]), ids=("assignment", "policy"))
def test_b20_review_lock_serializes_revoke_then_retry_denies(isolated, revoke):
    name, admin = isolated
    admin.execute("SELECT pg_advisory_lock(717002)")
    fault(admin, "proposals", "PERFORM pg_advisory_xact_lock(717002)")
    c = connect("p2b1_test_a_reviewer", dbname=name)
    try:
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(raw_submit, c, graph(), proposal())
            wait_for(admin, c.info.backend_pid, "advisory")
            admin.execute("SET lock_timeout='150ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                admin.execute(revoke)
            admin.execute("SET lock_timeout='5s'")
            admin.execute("SELECT pg_advisory_unlock(717002)")
            future.result(timeout=10)
    finally:
        c.close()
    admin.execute(revoke)
    with pytest.raises(psycopg.Error):
        submit(name)
    one(admin)


@pytest.mark.parametrize("drift", ("migration", "function"))
def test_b21_schema_and_ledger_drift_stop(isolated, drift):
    _, admin = isolated
    verify_migrations(admin)
    if drift == "migration":
        admin.execute("UPDATE ra4a_private.migrations SET sha256=repeat('0',64) WHERE version=3")
    else:
        admin.execute(
            "ALTER FUNCTION ra4a_review_test.require_reviewer(text,text) SET search_path=public"
        )
    with pytest.raises(AssertionError):
        verify_migrations(admin)


@pytest.mark.parametrize("table", TABLES)
def test_b22_append_only_even_fixture_admin(isolated, table):
    name, admin = isolated
    submit(name)
    before = fingerprint(admin)
    for query in ("UPDATE {} SET tenant_id=tenant_id", "DELETE FROM {}", "TRUNCATE {} CASCADE"):
        with pytest.raises(psycopg.Error):
            admin.execute(sql.SQL(query).format(sql.Identifier("ra4a_review_test", table)))
    assert fingerprint(admin) == before


def test_b23_no_append_after_seal_and_no_generated_hash_override(isolated):
    name, admin = isolated
    submit(name)
    for table in ("claims", "sections"):
        with pytest.raises(psycopg.Error):
            admin.execute(
                sql.SQL("INSERT INTO {} SELECT * FROM {} LIMIT 1").format(
                    *[sql.Identifier("ra4a_review_test", table)] * 2
                )
            )
    for column in ("command_digest", "receipt_sha256"):
        with pytest.raises(psycopg.errors.GeneratedAlways):
            admin.execute(
                sql.SQL("UPDATE ra4a_review_test.proposals SET {}='forged'").format(
                    sql.Identifier(column)
                )
            )
    one(admin)


@pytest.mark.parametrize(
    "fake", ({"actor": "owner", "verified": True}, {"cookie": "approved"}, {"oidc": "unsigned"})
)
def test_b24_production_always_denies_fake_authority(isolated, fake):
    name, admin = isolated
    with pytest.raises(PersistenceError, match="P2B1_REAL_IDENTITY_NATIVE_REVIEW_SHARE_DENIED"):
        production_review_port(**fake)
    cmd = changed(proposal(), lambda d: d.update(fake))
    with pytest.raises(ReviewError):
        submit(name, cmd=cmd)
    with connect("p2b1_test_a_reviewer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_submit(c, graph(), cmd)
    empty(admin)


def test_b26_policy_expires_during_open_transaction_no_commit(isolated):
    name, admin = isolated
    g, cmd = graph(), proposal()
    fault(admin, "outbox", "PERFORM pg_sleep(1)")
    with connect("p2b1_test_a_reviewer", dbname=name) as c:
        admin.execute(
            "UPDATE ra4a.policies SET expires_at=clock_timestamp()+interval '750 milliseconds'"
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege) as error:
            raw_submit(c, g, cmd)
        assert "complete_proposal" in error.value.diag.context
    empty(admin)


def test_b25_real_dump_restore_restart_receipts_state_audit_outbox(isolated):
    name, admin = isolated
    submit(name, cmd=proposal(action="REQUEST_CHANGES"))
    newer = add_reference(admin, version=2)
    register_graph(name, newer)
    commands = [
        (newer, proposal(newer, key="durable-version-key")),
        (graph("200"), proposal(graph("200"), key="durable-zero-key")),
    ]
    receipts = [submit(name, g, cmd).payload for g, cmd in commands]
    before = fingerprint(admin)
    state = json.loads(STATE.read_text())
    dump = subprocess.run(
        ["docker", "exec", state["container"], "pg_dump", "-U", "postgres", "-d", name, "-Fc"],
        capture_output=True,
        check=True,
    ).stdout
    out = Path(os.environ["RA4A_P2B1_EVIDENCE_DIR"])
    (out / "test-review-ledger.dump").write_bytes(dump)
    restored = "vrae_p2b1_" + uuid.uuid4().hex[:12]
    with connect(dbname="postgres") as c:
        c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(restored)))
    try:
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                state["container"],
                "pg_restore",
                "-U",
                "postgres",
                "-d",
                restored,
                "--exit-on-error",
            ],
            input=dump,
            capture_output=True,
            check=True,
        )
        with connect(dbname=restored) as c:
            c.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(restored))
            )
            c.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO p2b1_review").format(
                    sql.Identifier(restored)
                )
            )

        def check():
            for database in (name, restored):
                with connect(dbname=database) as c:
                    assert fingerprint(c) == before
                    assert c.execute(
                        "SELECT current_setting('fsync'),current_setting('synchronous_commit'),current_setting('full_page_writes')"
                    ).fetchone() == ("on", "on", "on")
                for (g, cmd), receipt in zip(commands, receipts, strict=True):
                    assert submit(database, g, cmd).payload == receipt
                with pytest.raises(psycopg.Error):
                    submit(database)
                with pytest.raises(psycopg.Error):
                    submit(database, newer, commands[0][1], "p2b1_test_b_reviewer")
                with connect(dbname=database) as c:
                    assert fingerprint(c) == before

        check()
        admin.close()
        subprocess.run(
            ["docker", "restart", "--time", "1", state["container"]],
            capture_output=True,
            check=True,
        )
        binding = (
            subprocess.check_output(["docker", "port", state["container"], "5432/tcp"])
            .decode()
            .strip()
        )
        assert binding.startswith("127.0.0.1:") and "\n" not in binding
        state["port"] = int(binding.rsplit(":", 1)[1])
        STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                with connect(dbname=name) as c:
                    c.execute("SELECT 1")
                break
            except psycopg.OperationalError:
                time.sleep(0.25)
        else:
            raise AssertionError("P2B1 restart readiness expired")
        check()
        (out / "p2b1-recovery.json").write_text(
            json.dumps(
                {
                    "dump_sha256": hashlib.sha256(dump).hexdigest(),
                    "dump_bytes": len(dump),
                    "before_and_after_state_audit_outbox_sha256": before,
                    "receipt_sha256": [hashlib.sha256(r).hexdigest() for r in receipts],
                    "actual_container_volume_restart": True,
                    "restore_exact": True,
                    "old_version_and_foreign_tenant_denied": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    finally:
        with connect(dbname="postgres") as c:
            c.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(restored)))
