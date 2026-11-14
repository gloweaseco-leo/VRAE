"""New homepage composition tests; original 55 cases/browser oracles unchanged."""
from dataclasses import replace
import time

import pytest

from apps.operator_console.b5p0_binding import Binding, mapping_subject


@pytest.mark.parametrize("case", ["404", "200"])
def test_home_uses_one_current_original_context_and_real_b3_probe(runtime, case):
    c = runtime.client()
    assert c.login(runtime.issuer, "task-" + case)[0][0] == 303
    before = len(runtime.events)
    start = time.perf_counter()
    status, body, _ = c.request("GET", "/b5a/")
    elapsed = time.perf_counter() - start
    assert status == 200 and b'data-key="b5p0-entry"' in body
    events = runtime.events[before:]
    # Original entry + exit verification, not B5 capture + another whole read.
    assert sum(e["event"] == "native_original_verified" for e in events) == 2
    assert sum(e["event"] == "response_current" for e in events) == 1
    assert [e["sqlstate"] for e in events if e["event"] == "sql_state"] == ["P0002"]
    assert all(v == 0 for v in runtime.data().values())
    runtime.event({"event": "focused_home_timing", "case": case, "seconds": elapsed})


@pytest.mark.parametrize("bad", [
    "witness-revoked", "witness-expired", "epoch", "b3-anchor",
    "assignment", "principal", "issuer", "role", "tenant", "source",
])
def test_home_denies_current_revocations_without_protected_metadata(runtime, bad):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    b = runtime.app.bindings["task-404"]
    if bad in ("witness-revoked", "witness-expired", "epoch", "b3-anchor", "assignment", "principal"):
        with runtime.lab.connect() as admin:
            if bad == "witness-revoked":
                admin.execute("DELETE FROM b3_p0.witnesses WHERE witness_id=%s", (b.witness.token,))
            elif bad == "witness-expired":
                admin.execute("UPDATE b3_p0.witnesses SET expires=clock_timestamp()-interval '1 second'")
            elif bad == "epoch":
                admin.execute("UPDATE b3_p0.authority SET epoch=epoch+1")
            elif bad == "b3-anchor":
                admin.execute("UPDATE b3_p0.authority SET anchor_active=false")
            elif bad == "assignment":
                admin.execute("UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'")
            else:
                admin.execute("UPDATE ra4a_private.principals SET enabled=false WHERE db_role='p2b1_test_a_reviewer'")
    elif bad == "source":
        from integration.ra4a.p2a_support import add_reference, raw_args
        with runtime.lab.connect() as admin:
            graph = add_reference(admin, version=2)
        with runtime.lab.connect("p2a_test_a_writer") as writer:
            writer.execute("SELECT ra4a_bytes.register(%s,%s,%s,%s,%s,%s,%s)", raw_args(graph))
    else:
        issuer = "other" if bad == "issuer" else b.issuer
        role = "p2b1_test_a_peer" if bad == "role" else b.role
        witness = replace(b.witness, location=replace(b.witness.location, tenant="tenant-beta")) if bad == "tenant" else b.witness
        runtime.app.bindings["task-404"] = Binding(issuer, b.subject, role, witness,
            mapping_subject(issuer, b.subject, role, witness.location))
    status, body, _ = c.request("GET", "/b5a/")
    assert status in (403, 409)
    assert b'data-key="b5p0-entry"' not in body
    assert runtime.tasks["404"]["title"].encode() not in body
    assert b'id="rehearsal-receipt"' not in body
    assert all(v == 0 for v in runtime.data().values())


def test_home_witness_revoked_after_original_exit_is_denied(runtime):
    c = runtime.client()
    assert c.login(runtime.issuer)[0][0] == 303
    seen = []
    def revoke(event):
        if event["event"] == "response_current":
            runtime.hook = None
            with runtime.lab.connect() as admin:
                admin.execute("DELETE FROM b3_p0.witnesses")
            seen.append("revoked_after_original_read_recheck")
    runtime.hook = revoke
    status, body, _ = c.request("GET", "/b5a/")
    assert seen and status in (403, 409)
    assert b'data-key="b5p0-entry"' not in body
    assert runtime.tasks["404"]["title"].encode() not in body
    assert all(v == 0 for v in runtime.data().values())
