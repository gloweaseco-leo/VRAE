"""Actual PG16, actual SESSION_USER, separate connections, no mocked persistence."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import time
import uuid

import psycopg
from psycopg import sql
import pytest

from integration.ra4a.p2a_support import add_reference
from integration.ra4a.p2b1_support import proposal
from vrae.b3_p0.contracts import Command, Denied, Receipt
from vrae.b3_p0.service import args
from vrae.reviewing.canonical import canonical

from .support import BUSINESS, TABLES, counts, protected, snapshot
from .evidence import record


def changed(cmd, mutate):
    d = cmd.proposal().document
    mutate(d)
    return Command(canonical(d, limit=131072))


def empty(case):
    assert counts(case.admin) == dict.fromkeys(BUSINESS, 0)


def one(case, which="404"):
    target = (
        __import__("vrae.reviewing", fromlist=["ReviewTarget"])
        .ReviewTarget(case.graphs[which].target)
        .document
    )
    assert counts(case.admin) == {
        "states": 1,
        "intents": 1,
        "claims": len(target["claims"]),
        "sections": len(target["required_sections"]),
        "audit": 1,
        "outbox": 1,
    }
    return target


@pytest.mark.parametrize(
    "which,action",
    [
        ("404", "APPROVE_CANDIDATE"),
        ("404", "REQUEST_CHANGES"),
        ("404", "REJECT"),
        ("200", "APPROVE_CANDIDATE"),
    ],
)
def test_original_native_claims_sections_durable_no_approval(case, which, action):
    before = protected(case.admin)
    w = case.witness(which)
    cmd = Command(proposal(case.graphs[which], action).payload)
    r = case.submit(w, cmd).document
    t = one(case, which)
    assert len(t["claims"]) == (6 if which == "404" else 3)
    assert r["status"] == (
        "REVIEW_INTENT_TEST_ONLY" if which == "404" else "COVERAGE_ACK_TEST_ONLY"
    )
    assert not r["effective_approval"] and not r["external_visibility"]
    assert r["person_id"] is r["native_decision"] is r["share_grant"] is None
    assert case.admin.execute(
        "SELECT disposition FROM b3_p0.claims ORDER BY ordinal"
    ).fetchall() == [(d,) for d in cmd.proposal().document["dispositions"]]
    assert protected(case.admin) == before
    record(
        "native-" + which + "-" + action.lower().replace("_", "-"),
        {
            "claims": len(t["claims"]),
            "sections": len(t["required_sections"]),
            "counts": counts(case.admin),
            "status": r["status"],
            "source_catalog_unchanged": True,
            "effective_approval": r["effective_approval"],
            "external_visibility": r["external_visibility"],
        },
    )


def test_fresh_witness_retry_returns_exact_immutable_receipt(case):
    first = case.submit().payload
    w = case.witness()
    fp = snapshot(case.admin)
    assert case.submit(w).payload == first
    with case.service(w) as api:
        assert api.get_receipt(w, "review-key-0001").payload == first
    assert snapshot(case.admin) == fp
    one(case)


@pytest.mark.parametrize("conflict", ["payload", "subject", "actor", "new_key", "version"])
def test_committed_idempotency_conflicts(case, conflict):
    case.submit()
    role = "p2b1_test_a_peer" if conflict == "actor" else "p2b1_test_a_reviewer"
    w = case.witness(
        role=role, subject="TEST_ONLY_other" if conflict == "subject" else "TEST_ONLY_reviewer"
    )
    cmd = Command(proposal(case.graphs["404"]).payload)
    graph = None
    if conflict == "payload":
        cmd = changed(cmd, lambda d: d.update(reason="Changed request"))
    if conflict == "new_key":
        cmd = changed(cmd, lambda d: d.update(idempotency_key="another-key-0001"))
    if conflict == "version":
        graph = add_reference(case.admin, version=2)
        from integration.ra4a.p2a_support import raw_args

        with case.connect("p2a_test_a_writer") as c:
            c.execute("SELECT ra4a_bytes.register(%s,%s,%s,%s,%s,%s,%s)", raw_args(graph))
        w = case.witness(graph=graph)
        cmd = Command(proposal(graph).payload)
    before = snapshot(case.admin)
    with pytest.raises(Denied):
        case.submit(w, cmd, role=role, graph=graph)
    assert snapshot(case.admin) == before


@pytest.mark.parametrize("same_key", [False, True])
def test_two_real_connections_compete_for_cas(case, same_key):
    w = case.witness()

    def attempt(i):
        with case.connect() as c:
            pid = c.execute("SELECT pg_backend_pid()").fetchone()[0]
            cmd = Command(
                proposal(
                    case.graphs["404"], key="concurrent-key-" + ("same" if same_key else str(i))
                ).payload
            )
            try:
                with c.transaction():
                    result = case.raw(c, w, cmd)
                return pid, result, None
            except psycopg.Error as exc:
                return pid, None, exc.sqlstate

    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(attempt, range(2)))
    assert rows[0][0] != rows[1][0]
    if same_key:
        assert rows[0][1] == rows[1][1] and all(r[2] is None for r in rows)
    else:
        assert sum(r[1] is not None for r in rows) == 1
        assert [r[2] for r in rows if r[2]] == ["40001"]
    one(case)
    record(
        "concurrent-" + ("duplicate" if same_key else "different-key"),
        {
            "distinct_backends": rows[0][0] != rows[1][0],
            "successes": sum(r[1] is not None for r in rows),
            "sqlstates": [r[2] for r in rows],
            "same_receipt": rows[0][1] == rows[1][1],
            "counts": counts(case.admin),
        },
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "sections_missing",
        "sections_digest",
        "guard",
        "claim_missing",
        "html_target",
        "revision",
        "stale_seq",
        "bool_seq",
        "extra_authority",
    ],
)
def test_actual_sql_rejects_malformed_canonical_command(case, mutation):
    w = case.witness()

    def mutate(d):
        if mutation == "sections_missing":
            d["sections"].pop()
        elif mutation == "sections_digest":
            d["sections"][0]["target_digest"] = "0" * 64
        elif mutation == "guard":
            d["dispositions"][0]["guard_ref"] = "fake-guard"
        elif mutation == "claim_missing":
            d["dispositions"].pop()
        elif mutation == "html_target":
            d["target_digest"] = "0" * 64
        elif mutation == "revision":
            d["report_version"] = 2
        elif mutation == "stale_seq":
            d["expected_review_seq"] = 1
        elif mutation == "bool_seq":
            d["expected_review_seq"] = True
        else:
            d["authority"] = "APPROVED"

    cmd = changed(Command(proposal(case.graphs["404"]).payload), mutate)
    with case.connect() as c, pytest.raises(psycopg.Error) as caught:
        with c.transaction():
            case.raw(c, w, cmd)
    assert caught.value.sqlstate in {"22023", "40001"}
    empty(case)


@pytest.mark.parametrize(
    "bad",
    [
        "missing",
        "wrong_role",
        "wrong_subject_witness",
        "expired",
        "revoked_epoch",
        "anchor_revoked",
        "anchor_expired",
        "assignment",
        "principal",
        "tenant",
        "ref",
        "source",
        "html_digest",
    ],
)
def test_real_authority_and_locator_negatives(case, bad):
    w = case.witness(ttl=-1 if bad == "expired" else 120)
    role = "p2b1_test_a_peer" if bad == "wrong_role" else "p2b1_test_a_reviewer"
    if bad in {"missing", "wrong_subject_witness"}:
        w = replace(w, token=uuid.uuid4())
    if bad == "revoked_epoch":
        case.admin.execute("UPDATE b3_p0.authority SET epoch=epoch+1")
    if bad == "anchor_revoked":
        case.admin.execute("UPDATE b3_p0.authority SET anchor_active=false")
    if bad == "anchor_expired":
        case.admin.execute(
            "UPDATE b3_p0.authority SET anchor_expires=clock_timestamp()-interval '1 second'"
        )
    if bad == "assignment":
        case.admin.execute(
            "UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'"
        )
    if bad == "principal":
        case.admin.execute(
            "UPDATE ra4a_private.principals SET enabled=false WHERE db_role='p2b1_test_a_reviewer'"
        )
    if bad in {"tenant", "ref", "source", "html_digest"}:
        field = {
            "tenant": "tenant",
            "ref": "ref_id",
            "source": "source_run",
            "html_digest": "target_digest",
        }[bad]
        w = replace(w, location=replace(w.location, **{field: "0" * 64}))
    with case.connect(role) as c, pytest.raises(psycopg.Error) as caught:
        with c.transaction():
            case.raw(c, w)
    assert caught.value.sqlstate == "42501"
    empty(case)


@pytest.mark.parametrize(
    "role",
    [
        "p2b1_test_b_reviewer",
        "ra4a_test_a_app",
        "ra4a_test_a_worker",
        "ra4a_test_unassigned",
        "p2a_test_a_writer",
    ],
)
def test_connected_wrong_role_42501(case, role):
    w = case.witness()
    with case.connect(role) as c, pytest.raises(psycopg.Error) as caught:
        c.execute(
            "SELECT b3_p0.submit_test(%s,%s,%s,%s,%s,%s,%s,%s)",
            (w.token, *args(w.location), Command(proposal(case.graphs["404"]).payload).payload),
        )
    assert caught.value.sqlstate == "42501"
    empty(case)


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("operation", ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"])
def test_no_raw_table_privileges_42501(case, table, operation):
    statement = {
        "SELECT": "SELECT * FROM b3_p0.{}",
        "INSERT": "INSERT INTO b3_p0.{} DEFAULT VALUES",
        "UPDATE": "UPDATE b3_p0.{} SET "
        + ("schema_sha256=schema_sha256" if table == "bootstrap" else "tenant_id=tenant_id"),
        "DELETE": "DELETE FROM b3_p0.{}",
        "TRUNCATE": "TRUNCATE b3_p0.{}",
    }[operation]
    with case.connect() as c, pytest.raises(psycopg.Error) as caught:
        c.execute(sql.SQL(statement).format(sql.Identifier(table)))
    assert caught.value.sqlstate == "42501"
    record(
        "raw-" + table + "-" + operation.lower(),
        {
            "table": "b3_p0." + table,
            "operation": operation,
            "actual_role": "p2b1_test_a_reviewer",
            "sqlstate": caught.value.sqlstate,
        },
    )


def test_rls_force_all_tables_public_has_no_functions(case):
    assert case.admin.execute(
        "SELECT count(*),bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class WHERE relnamespace='b3_p0'::regnamespace AND relkind='r'"
    ).fetchone() == (9, True)
    assert case.admin.execute(
        "SELECT count(*) FROM pg_proc p,aclexplode(coalesce(proacl,acldefault('f',proowner))) a WHERE pronamespace='b3_p0'::regnamespace AND a.grantee=0"
    ).fetchone() == (0,)
    with case.connect() as c, pytest.raises(psycopg.Error) as caught:
        c.execute("SELECT b3_p0.require_witness(NULL,'a','b','c','d',1,'e')")
    assert caught.value.sqlstate == "42501"


@pytest.mark.parametrize("table", BUSINESS)
def test_rollback_at_each_actual_write_stage(case, table):
    w = case.witness()
    case.admin.execute(
        "CREATE FUNCTION b3_p0.inject_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='B3_TEST_INJECTED_WRITE_FAILURE'; END $$"
    )
    case.admin.execute(
        sql.SQL(
            "CREATE TRIGGER fail_stage BEFORE INSERT ON b3_p0.{} FOR EACH ROW EXECUTE FUNCTION b3_p0.inject_failure()"
        ).format(sql.Identifier(table))
    )
    with case.connect() as c, pytest.raises(psycopg.Error) as caught:
        with c.transaction():
            case.raw(c, w)
    assert caught.value.sqlstate == "23514"
    empty(case)
    record(
        "rollback-" + table,
        {"stage": table, "sqlstate": caught.value.sqlstate, "counts": counts(case.admin)},
    )


def test_deferred_integrity_catches_omitted_children_at_actual_commit(case):
    w = case.witness()
    # Fixture-only injected failure: skip one INSERT, rather than weakening runtime checks.
    case.admin.execute(
        "CREATE FUNCTION b3_p0.skip_child() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NULL; END $$"
    )
    case.admin.execute(
        "CREATE TRIGGER skip_child BEFORE INSERT ON b3_p0.audit FOR EACH ROW EXECUTE FUNCTION b3_p0.skip_child()"
    )
    with case.connect() as c:
        with pytest.raises(psycopg.Error) as caught:
            with c.transaction():
                case.raw(c, w)
                assert c.execute("SELECT 1").fetchone() == (1,)
        assert caught.value.sqlstate == "23514"
    empty(case)


def test_expiry_at_deferred_commit_entry_rolls_back(case):
    w = case.witness(ttl=20)
    deadline = case.admin.execute(
        "SELECT expires FROM b3_p0.witnesses WHERE witness_id=%s", (w.token,)
    ).fetchone()[0]
    with case.connect() as c, pytest.raises(psycopg.Error) as caught:
        with c.transaction():
            raw = case.raw(c, w)
            assert Receipt(raw).document["durable"] is True
            c.execute(
                "SELECT pg_sleep(greatest(0,extract(epoch FROM (%s::timestamptz-clock_timestamp())))+0.1)",
                (deadline,),
            )
    assert caught.value.sqlstate == "42501"
    empty(case)
    record(
        "expired-commit-entry",
        {"sqlstate": caught.value.sqlstate, "actual_rollback": True, "counts": counts(case.admin)},
    )


def test_early_constraints_then_commit_after_expiry_keeps_history_and_denies_receipt(case):
    w = case.witness(ttl=20)
    deadline = case.admin.execute(
        "SELECT expires FROM b3_p0.witnesses WHERE witness_id=%s", (w.token,)
    ).fetchone()[0]
    with case.connect() as c:
        with c.transaction():
            raw = case.raw(c, w)
            c.execute("SET CONSTRAINTS ALL IMMEDIATE")
            c.execute(
                "SELECT pg_sleep(greatest(0,extract(epoch FROM (%s::timestamptz-clock_timestamp())))+0.1)",
                (deadline,),
            )
    # Actual COMMIT succeeded. This is NOT a rollback. Immutable test history exists.
    one(case)
    assert Receipt(raw).document["effective_approval"] is False
    with case.service(w) as api, pytest.raises(Denied, match="B3_AUTHORITY_DENIED"):
        api.get_receipt(w, "review-key-0001")
    one(case)
    record(
        "expiry-after-early-constraints-real-commit",
        {
            "actual_commit_succeeded": True,
            "receipt_read_denied": True,
            "actual_rollback": False,
            "counts": counts(case.admin),
            "effective_approval": False,
            "external_visibility": False,
        },
    )


@pytest.mark.parametrize("revoke", [False, True])
def test_expiry_or_revocation_while_waiting_on_authority_lock(case, revoke):
    w = case.witness(ttl=30 if revoke else 0.5)
    with case.lab.connect(dbname=case.dbname) as blocker:
        with ThreadPoolExecutor(1) as pool:
            with blocker.transaction():
                blocker.execute("SELECT 1 FROM b3_p0.authority FOR UPDATE")

                def waiting():
                    with case.connect() as c:
                        try:
                            with c.transaction():
                                case.raw(c, w)
                        except psycopg.Error as exc:
                            return exc.sqlstate
                    return "UNEXPECTED_SUCCESS"

                future = pool.submit(waiting)
                deadline = time.monotonic() + 5
                while not case.admin.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND usename='p2b1_test_a_reviewer' AND wait_event_type='Lock'"
                ).fetchone()[0]:
                    assert time.monotonic() < deadline
                    time.sleep(0.02)
                time.sleep(0.7)
                assert not future.done()
                if revoke:
                    blocker.execute("UPDATE b3_p0.authority SET epoch=epoch+1")
            assert future.result(timeout=10) == "42501"
    empty(case)
    record(
        "lock-wait-" + ("revoked" if revoke else "expired"),
        {"actual_pg_lock_wait_observed": True, "sqlstate": "42501", "counts": counts(case.admin)},
    )


def test_after_commit_revocation_denies_but_history_stays(case):
    w = case.witness()
    case.submit(w)
    case.admin.execute("UPDATE b3_p0.authority SET epoch=epoch+1")
    before = snapshot(case.admin)
    with case.service(w) as api, pytest.raises(Denied):
        api.get_receipt(w, "review-key-0001")
    assert snapshot(case.admin) == before
    one(case)


def test_source_policy_replacement_denies_original_locator(case):
    w = case.witness()
    case.admin.execute("UPDATE ra4a.policies SET status='REVOKED'")
    with case.connect() as c, pytest.raises(psycopg.Error) as caught:
        with c.transaction():
            case.raw(c, w)
    assert caught.value.sqlstate == "42501"
    empty(case)


def test_client_ambient_transaction_denied(case):
    w = case.witness()
    with (
        case.service(w) as api,
        api.connection.transaction(),
        pytest.raises(Denied, match="OWNED_TRANSACTION"),
    ):
        api.submit(w, Command(proposal(case.graphs["404"]).payload))
    empty(case)


def test_concurrent_same_key_conflicting_payload_exactly_one(case):
    w = case.witness()
    commands = [Command(proposal(case.graphs["404"]).payload)]
    commands.append(changed(commands[0], lambda d: d.update(reason="Other simultaneous payload")))

    def attempt(cmd):
        with case.connect() as c:
            try:
                with c.transaction():
                    return case.raw(c, w, cmd), None
            except psycopg.Error as exc:
                return None, exc.sqlstate

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, commands))
    assert sum(r[0] is not None for r in results) == 1
    assert [r[1] for r in results if r[1]] == ["23505"]
    one(case)


def test_new_source_policy_version_invalidates_old_locator(case):
    w = case.witness()
    case.admin.execute(
        "INSERT INTO ra4a.policies SELECT tenant_id,policy_id,version+1,status,expires_at,scope FROM ra4a.policies"
    )
    with case.connect() as c, pytest.raises(psycopg.Error) as caught:
        with c.transaction():
            case.raw(c, w)
    assert caught.value.sqlstate == "42501"
    empty(case)


def test_assignment_revocation_while_waiting_on_assignment_lock(case):
    w = case.witness()
    with case.lab.connect(dbname=case.dbname) as blocker, ThreadPoolExecutor(1) as pool:
        with blocker.transaction():
            blocker.execute(
                "SELECT 1 FROM ra4a_review_test.assignments WHERE db_role='p2b1_test_a_reviewer' FOR UPDATE"
            )

            def waiting():
                with case.connect() as c:
                    try:
                        with c.transaction():
                            case.raw(c, w)
                    except psycopg.Error as exc:
                        return exc.sqlstate
                return "UNEXPECTED_SUCCESS"

            future = pool.submit(waiting)
            time.sleep(0.3)
            assert not future.done()
            blocker.execute(
                "UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'"
            )
        assert future.result(timeout=10) == "42501"
    empty(case)


@pytest.mark.parametrize("kind", ["HTML", "SOURCE", "GUARD", "MANIFEST"])
def test_actual_original_read_rejects_mismatched_independent_byte_pins(case, kind):
    from vrae.persistence.contracts import PersistenceError
    from vrae.reviewing import ReviewError

    graph = case.graphs["404"]
    w = case.witness()
    before = protected(case.admin)
    if kind == "MANIFEST":
        forged = replace(graph, manifest=graph.manifest + b" ")
    else:
        forged = replace(
            graph,
            artifacts=tuple(
                replace(a, raw=a.raw + b" ") if a.kind == kind else a for a in graph.artifacts
            ),
        )
    # Exact current Locator and real Reviewer load_target still execute. Independent
    # provenance does NOT become trustworthy just because its Locator was correct.
    with case.service(w, graph=forged) as service:
        with pytest.raises((PersistenceError, ReviewError)) as caught:
            service.submit(w, Command(proposal(graph).payload))
    assert protected(case.admin) == before
    empty(case)
    record(
        "bytes-mismatch-" + kind.lower(),
        {
            "mismatched_kind": kind,
            "native_denial": str(caught.value),
            "original_source_catalog_unchanged": True,
            "counts": counts(case.admin),
        },
    )
