"""Actual PG16 / signed B2 / HTTP security regressions, no mock database."""

from dataclasses import replace
import hashlib
import json
import os
import socket
import time
from urllib.parse import urlencode
from urllib.parse import urlsplit

import psycopg
from psycopg import sql
import pytest

from apps.operator_console.b5a_http import PREFIX, FORM
from tests.identity.issuer import Issuer

from .lab import docker
from .support import Runtime, Forms


def snapshot(r):
    with r.lab.connect() as c:
        tables = c.execute(
            "SELECT n.nspname,t.relname FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname IN ('ra4a','ra4a_private','ra4a_bytes','ra4a_review_test') AND t.relkind='r' ORDER BY 1,2"
        ).fetchall()
        result = {}
        for schema, name in tables:
            rows = c.execute(
                sql.SQL(
                    "SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]') FROM {}.{} x"
                ).format(sql.Identifier(schema), sql.Identifier(name))
            ).fetchone()[0]
            result[schema + "." + name] = {
                "rows": len(rows),
                "sha256": hashlib.sha256(
                    json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode()
                ).hexdigest(),
            }
        return result


@pytest.fixture(scope="session")
def runtime():
    name = os.environ.get("B5A_RUN", "security-dev-311-01")
    r = Runtime(name)
    verified = False
    try:
        r.start()
        r.baseline = snapshot(r)
        yield r
        assert snapshot(r) == r.baseline
        verified = True
    finally:
        r.lab.private.joinpath("scan-credentials.json").write_text(
            json.dumps(
                [
                    r.lab.state["admin_password"],
                    *r.lab.state["runtime_passwords"].values(),
                    *r.secrets,
                ]
            ),
            encoding="utf-8",
        )
        r.stop()
        if hasattr(r, "baseline"):
            r.lab.private.joinpath("zero-business-writes.json").write_text(
                json.dumps(
                    {
                        "original_table_fingerprints": r.baseline,
                        "business_tables_unchanged": verified,
                        "no_native_decision": verified,
                        "no_share_grant": verified,
                    }
                ),
                encoding="utf-8",
            )


@pytest.fixture(autouse=True)
def clean_sessions(runtime):
    r = runtime
    anchor = r.store.boundary.anchor
    assignments = r.store.boundary.assignments
    pins = dict(r.reader.pins)
    caps = r.store.session_capacity, r.store.challenge_capacity, r.store.action_capacity
    try:
        r.store.rotate(
            replace(anchor, expires=int(time.time()) + 1800, available=True, revoked=frozenset()),
            list(r.bindings.values()),
        )
        r.events.clear()
        yield
    finally:
        r.store.clock = time.time
        r.store.boundary.clock = time.time
        r.store.last_time = 0
        r.store.session_capacity, r.store.challenge_capacity, r.store.action_capacity = caps
        r.reader.pins = pins
        r.store.rotate(anchor, assignments)
        assert snapshot(r) == r.baseline


def signed(r, case="404"):
    client = r.client()
    response, token, challenge = client.login(r.issuer, "task-" + case)
    assert response[0] == 303
    return client, token, challenge


def preview_fields(r, client, case="404", action=None):
    status, raw, _ = client.request("GET", r.review_path(case, "proposal"))
    assert status == 200
    path = PREFIX + "tasks/task-" + case + "/proposal-preview"
    fields = Forms(raw.decode()).forms[path + "#validation-result"]
    with r.app.service.request(client.cookies["b5a_session"]):
        _, dossier = r.app.preview.read(
            client.cookies["b5a_session"],
            "task-" + case,
            1,
            r.tasks[case]["report_pins"]["expected_draft_ref"],
            r.bindings["task-" + case].location.target_digest,
        )
    target = dossier["review_target"]["target"]
    for i, c in enumerate(target["claims"]):
        fields["disposition." + str(i)] = c["allowed_acceptance"]
    fields["action"] = action or (
        "APPROVE_CANDIDATE" if case == "404" else "SIMULATED_INTERNAL_SCOPE_ACK"
    )
    fields["reason"] = ""
    return path, fields


@pytest.mark.parametrize("case", ["404", "200"])
def test_signed_login_exact_current_reviewer_original_and_native_claims(runtime, case):
    r = runtime
    client, token, _ = signed(r, case)
    for endpoint in ["review", "target", "proposal", "evidence/0", "evidence/capture"]:
        status, raw, headers = client.request("GET", r.review_path(case, endpoint))
        assert status == 200
        assert "Reviewer 原文只读".encode() in raw and b"NOT APPROVED" in raw
        assert token.encode() not in raw and token[7:].encode() not in raw
        assert dict(headers)["Cross-Origin-Resource-Policy"] == "same-origin"
    verified = [e for e in r.events if e["event"] == "native_original_verified"]
    assert verified and all(e["case"] == case for e in verified)
    assert any(
        e["event"] == "actual_reviewer_identity" and e["role"] == "p2b1_test_a_reviewer"
        for e in r.events
    )


@pytest.mark.parametrize("case", ["404", "200"])
def test_actual_existing_ssr_per_claim_contract_preview_is_never_approval(runtime, case):
    r = runtime
    client, _, _ = signed(r, case)
    path, fields = preview_fields(r, client, case)
    status, raw, _ = client.request(
        "POST", path, urlencode(fields).encode(), {"Content-Type": FORM}
    )
    assert status == 200 and b"CONTRACT_VALID_ONLY" in raw
    assert "未产生决定".encode() in raw and b"PRIVATE_NOT_APPROVED" in raw
    if case == "200":
        assert b"COVERAGE_ACK_PROPOSAL" in raw and "0 条问题".encode() in raw
    assert snapshot(r) == r.baseline


@pytest.mark.parametrize(
    "mutation",
    [
        "issuer",
        "audience",
        "nonce",
        "signature",
        "expired",
        "future",
        "unknown-subject",
        "role",
        "algorithm",
    ],
)
def test_bad_signed_tokens_deny_before_any_original_row(runtime, mutation):
    r = runtime
    client = r.client()
    changes, header, alter = {}, None, None
    now = int(time.time())
    if mutation == "issuer":
        changes = {"iss": "https://other.test.invalid"}
    if mutation == "audience":
        changes = {"aud": "unapproved-api"}
    if mutation == "nonce":
        changes = {"nonce": "browser-chosen-not-server-nonce"}
    if mutation == "expired":
        changes = {"iat": now - 120, "nbf": now - 120, "exp": now - 1}
    if mutation == "future":
        changes = {"iat": now + 60, "nbf": now + 60, "exp": now + 120}
    if mutation == "unknown-subject":
        changes = {"sub": "unassigned-synthetic-subject"}
    if mutation == "role":
        changes = {"role": "postgres"}
    if mutation == "algorithm":
        header = {"alg": "none", "kid": "old", "typ": "vrae-test-identity+jwt"}
    if mutation == "signature":

        def alter(value):
            h, p, s = value.split(".")
            return h + "." + p + "." + ("A" if s[0] != "A" else "B") + s[1:]

    before = r.original_reads()
    response, _, _ = client.login(r.issuer, changes=changes, header=header, alter=alter)
    assert response[0] == 403 and r.original_reads() == before
    assert "b5a_session" not in client.cookies


def test_foreign_signer_replay_and_restarted_session_store_fail_closed(runtime):
    r = runtime
    client = r.client()
    before = r.original_reads()
    response, _, _ = client.login(Issuer())
    assert response[0] == 403 and r.original_reads() == before
    client, token, ch = signed(r)
    before = r.original_reads()
    status, _, _ = client.request(
        "POST",
        PREFIX + "session",
        b"{}",
        {"Content-Type": "application/json", "Authorization": token, "X-B5A-CSRF": ch["csrf"]},
    )
    assert status == 403 and r.original_reads() == before
    old = client.cookies["b5a_session"]
    r.store.rotate(r.store.boundary.anchor, r.store.boundary.assignments)
    assert client.request("GET", r.review_path())[0] == 403 and r.original_reads() == before
    assert old not in repr(r.store.sessions)
    new_ch = client.challenge()
    assert (
        client.request(
            "POST",
            PREFIX + "session",
            b"{}",
            {
                "Content-Type": "application/json",
                "Authorization": token,
                "X-B5A-CSRF": new_ch["csrf"],
            },
        )[0]
        == 403
    )


@pytest.mark.parametrize(
    "kind",
    [
        "anchor-unavailable",
        "anchor-revoked",
        "binding-revoked",
        "session-expired",
        "clock-backwards",
    ],
)
def test_current_server_policy_expiry_and_invalidation_before_pg_read(runtime, kind):
    r = runtime
    client, _, _ = signed(r)
    before = r.original_reads()
    a = r.store.boundary.anchor
    if kind == "anchor-unavailable":
        r.store.boundary.anchor = replace(a, available=False)
    if kind == "anchor-revoked":
        r.store.boundary.anchor = replace(a, revoked=frozenset(["old"]))
    if kind == "binding-revoked":
        r.store.boundary.assignments = tuple(
            replace(b, active=False) for b in r.store.boundary.assignments
        )
    if kind == "session-expired":
        r.store.clock = lambda: time.time() + 121
    if kind == "clock-backwards":
        r.store.clock = lambda: 1
    assert client.request("GET", r.review_path())[0] == 403 and r.original_reads() == before


@pytest.mark.parametrize(
    "table,column",
    [
        ("ra4a_private.principals", "enabled"),
        ("ra4a_private.assignments", "active"),
        ("ra4a_review_test.assignments", "active"),
    ],
)
def test_committed_pg_revoke_mid_page_refuses_next_source_and_no_fallback(runtime, table, column):
    r = runtime
    client, _, _ = signed(r)
    assert client.request("GET", r.review_path())[0] == 200
    before = r.original_reads()
    with r.lab.connect() as c:
        q = sql.SQL("UPDATE {}.{} SET {}=%s WHERE db_role=%s").format(
            *[sql.Identifier(p) for p in table.split(".")], sql.Identifier(column)
        )
        c.execute(q, (False, r.reader.settings.user))
        try:
            status, raw, _ = client.request("GET", r.review_path(endpoint="evidence/0"))
            assert status == 403 and r.original_reads() == before
            assert b"password" not in raw.lower() and b"load_target" not in raw
            assert any(e["event"] == "read_denied" and e["sqlstate"] == "42501" for e in r.events)
        finally:
            c.execute(q, (True, r.reader.settings.user))


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "evil.test.invalid"},
        {"Origin": "https://evil.test.invalid"},
        {"Sec-Fetch-Site": "cross-site"},
        {"X-Role": "postgres"},
        {"Cookie": "b5a_session=forged"},
        {"Cookie": "b5a_session=" + "A" * 43 + "; b5a_session=" + "B" * 43},
    ],
)
def test_forged_http_authority_boundaries_do_not_read_originals(runtime, headers):
    r = runtime
    client, _, _ = signed(r)
    before = r.original_reads()
    assert client.request("GET", r.review_path(), headers=headers)[0] in (400, 403)
    assert r.original_reads() == before


@pytest.mark.parametrize(
    "suffix",
    [
        "tasks/task-200",
        "tasks/task-404/review?version=2&draft=rd-" + 64 * "0",
        "tasks/task-404/target?version=1&draft=rd-" + 64 * "0" + "&target=" + 64 * "0",
        "tasks/task-404/review?role=postgres",
        "tasks/task-404/review?tenant=tenant-beta",
    ],
)
def test_wrong_task_locator_version_or_authority_query_denied_before_originals(runtime, suffix):
    r = runtime
    client, _, _ = signed(r)
    before = r.original_reads()
    assert client.request("GET", PREFIX + suffix)[0] in (400, 403, 409)
    assert r.original_reads() == before


@pytest.mark.parametrize(
    "route", ["approve", "decision", "share", "cancel", "api/tasks", "tasks/task-404/submit"]
)
def test_effective_decision_and_share_mutation_routes_always_deny(runtime, route):
    r = runtime
    client, _, _ = signed(r)
    before = r.original_reads()
    status, _, _ = client.request(
        "POST", PREFIX + route, b"{}", {"Content-Type": "application/json"}
    )
    assert status == 501 and r.original_reads() == before
    assert snapshot(r) == r.baseline


def test_preview_csrf_cross_origin_duplicate_submit_and_logout(runtime):
    r = runtime
    client, _, _ = signed(r)
    path, fields = preview_fields(r, client)
    raw = urlencode(fields).encode()
    before = r.original_reads()
    assert (
        client.request(
            "POST", path, raw, {"Content-Type": FORM, "Origin": "https://evil.test.invalid"}
        )[0]
        == 403
    )
    assert r.original_reads() == before
    missing = dict(fields)
    missing.pop("_csrf")
    assert (
        client.request("POST", path, urlencode(missing).encode(), {"Content-Type": FORM})[0] == 403
    )
    assert r.original_reads() == before
    assert client.request("POST", path, raw, {"Content-Type": FORM})[0] == 200
    before = r.original_reads()
    assert client.request("POST", path, raw, {"Content-Type": FORM})[0] == 403
    assert r.original_reads() == before
    status, html, _ = client.request("GET", PREFIX)
    assert status == 200
    logout = Forms(html.decode()).forms[PREFIX + "logout"]
    assert client.request("GET", PREFIX + "logout")[0] in (403, 501)
    assert (
        client.request(
            "POST", PREFIX + "logout", urlencode(logout).encode(), {"Content-Type": FORM}
        )[0]
        == 303
    )
    before = r.original_reads()
    assert client.request("GET", r.review_path())[0] == 403 and r.original_reads() == before


@pytest.mark.parametrize(
    "body,content_type",
    [
        (b"x=%zz", FORM),
        (b"x=1&x=2", FORM),
        (b"\xff", FORM),
        (b"x" * 24577, FORM),
        (b"{}", "application/json"),
    ],
)
def test_malformed_oversize_or_wrong_type_never_leaks_source(runtime, body, content_type):
    r = runtime
    client, _, _ = signed(r)
    before = r.original_reads()
    status, raw, _ = client.request(
        "POST", PREFIX + "tasks/task-404/proposal-preview", body, {"Content-Type": content_type}
    )
    assert status in (400, 403, 413) and r.original_reads() == before
    assert b"load_target" not in raw


@pytest.mark.parametrize("which", ["manifest", "target", "HTML", "DRAFT"])
def test_wrong_independent_content_and_html_pins_against_actual_pg_never_render(runtime, which):
    r = runtime
    client, _, _ = signed(r)
    p = r.bindings["task-404"].location
    pin = r.reader.pins[p]
    if which == "manifest":
        r.reader.pins[p] = replace(pin, manifest_sha256="0" * 64)
    elif which == "target":
        r.reader.pins[p] = replace(pin, target_sha256="0" * 64)
    else:
        ds = tuple(dict(d, sha256="0" * 64) if d["kind"] == which else d for d in pin.descriptors)
        r.reader.pins[p] = replace(pin, descriptors=ds)
    status, raw, _ = client.request("GET", r.review_path())
    assert status == 409 and b"SOURCE_INTEGRITY" in raw
    assert "采购商能否".encode() not in raw and b"password" not in raw.lower()


def test_missing_source_and_db_down_have_no_fixture_fallback(runtime):
    r = runtime
    client, _, _ = signed(r)
    p = r.bindings["task-404"].location
    pin = r.reader.pins[p]
    r.reader.pins[p] = replace(
        pin, descriptors=tuple(d for d in pin.descriptors if d["kind"] != "SOURCE")
    )
    assert client.request("GET", r.review_path())[0] == 409
    r.reader.pins[p] = pin
    docker("stop", r.lab.name)
    try:
        before = r.original_reads()
        status, raw, _ = client.request("GET", r.review_path())
        assert status == 503 and r.original_reads() == before and b"password" not in raw.lower()
    finally:
        docker("start", r.lab.name)
        port = r.lab.refresh_port()
        r.reader.settings = replace(r.reader.settings, port=port)
        end = time.monotonic() + 45
        while True:
            try:
                with r.lab.connect() as c:
                    c.execute("SELECT 1")
                break
            except psycopg.OperationalError:
                if time.monotonic() > end:
                    raise
                time.sleep(0.2)


def test_actual_reviewer_direct_private_sql_and_mutations_denied(runtime):
    r = runtime
    from integration.ra4e.security import TABLE_ACL_SCOPE

    outcomes = []
    with r.reader.settings.connect() as c:
        for schema, table in sorted(TABLE_ACL_SCOPE):
            name = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
            first = c.execute(
                "SELECT a.attname FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class t ON t.oid=a.attrelid JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=%s AND t.relname=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum LIMIT 1",
                (schema, table),
            ).fetchone()[0]
            for operation, statement in [
                ("SELECT", sql.SQL("SELECT * FROM {} LIMIT 0").format(name)),
                ("INSERT", sql.SQL("INSERT INTO {} DEFAULT VALUES").format(name)),
                (
                    "UPDATE",
                    sql.SQL("UPDATE {} SET {}={} WHERE false").format(
                        name, sql.Identifier(first), sql.Identifier(first)
                    ),
                ),
                ("DELETE", sql.SQL("DELETE FROM {} WHERE false").format(name)),
                ("TRUNCATE", sql.SQL("TRUNCATE {}").format(name)),
            ]:
                with pytest.raises(psycopg.Error) as error:
                    with c.transaction():
                        c.execute(statement)
                assert error.value.sqlstate == "42501"
                outcomes.append(
                    {"table": schema + "." + table, "operation": operation, "sqlstate": "42501"}
                )
    r.lab.private.joinpath("reviewer-sqlstate.json").write_text(
        json.dumps(outcomes), encoding="utf-8"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant", "tenant-beta"),
        ("report", "missing-report"),
        ("source_run", "missing-source-run"),
        ("version", 999),
    ],
)
def test_wrong_trusted_locator_is_denied_by_actual_reviewer_sql(runtime, field, value):
    r = runtime
    bindings = dict(r.store.bindings)
    try:
        binding = bindings["task-404"]
        wrong = replace(binding.location, **{field: value})
        r.reader.pins[wrong] = replace(r.reader.pins[binding.location], location=wrong)
        r.store.bindings["task-404"] = replace(binding, location=wrong)
        r.store.rotate(r.store.boundary.anchor, list(r.store.bindings.values()))
        before = r.original_reads()
        response, _, _ = r.client().login(r.issuer)
        assert response[0] == 403 and r.original_reads() == before
        # Authorization must actually reach the accepted SQL boundary, not a
        # browser-scope rejection or a simulated empty graph.
        assert any(e["event"] == "actual_sql_denial" and e["sqlstate"] == "42501" for e in r.events)
    finally:
        r.store.bindings = bindings


def test_wire_parser_errors_never_reflect_credentials_or_read_originals(runtime):
    r = runtime
    token = r.issuer.token()
    r.secrets.append(token)
    host = urlsplit(r.origin).netloc.encode()
    before = r.original_reads()
    messages = [
        b"GET /b5a/login " + token.encode() + b"\r\n\r\n",
        b"UNSUPPORTED /b5a/login HTTP/1.1\r\nHost: "
        + host
        + b"\r\nAuthorization: "
        + token.encode()
        + b"\r\n\r\n",
        b"GET /b5a/login HTTP/1.1\r\nHost: " + host + b"\r\nHost: other\r\n\r\n",
        b"POST /b5a/session HTTP/1.1\r\nHost: "
        + host
        + b"\r\nContent-Length: 0\r\nContent-Length: 1\r\n\r\nz",
    ]
    for message in messages:
        with socket.create_connection(("127.0.0.1", urlsplit(r.origin).port), timeout=5) as sock:
            sock.sendall(message)
            parts = []
            while True:
                data = sock.recv(8192)
                if not data:
                    break
                parts.append(data)
        response = b"".join(parts)
        assert b"Cache-Control: no-store" in response
        assert response.split(b" ", 2)[1] in (b"400", b"501")
        assert token.encode() not in response and token[7:].encode() not in response
        assert b"B5A_REQUEST_DENIED" in response
    assert r.original_reads() == before


def test_finite_challenge_session_action_caps_and_cookie_attributes(runtime):
    r = runtime
    r.store.challenge_capacity = 1
    client = r.client()
    client.challenge()
    status, raw, _ = client.request("GET", PREFIX + "login")
    csrf = __import__("re").search(
        r'name="_bootstrap_csrf" value="([A-Za-z0-9_-]+)"', raw.decode()
    )[1]
    before = r.original_reads()
    assert (
        client.request(
            "POST",
            PREFIX + "challenge",
            urlencode({"task": "task-404", "_csrf": csrf}).encode(),
            {"Content-Type": FORM},
        )[0]
        == 403
    )
    assert r.original_reads() == before
    r.store.challenges.clear()
    r.store.session_capacity = 1
    response, token, _ = client.login(r.issuer)
    assert response[0] == 303
    headers = [
        v for k, v in response[2] if k.lower() == "set-cookie" and v.startswith("b5a_session=")
    ]
    assert len(headers) == 1 and all(
        s in headers[0] for s in ["HttpOnly", "SameSite=Strict", "Path=/b5a/"]
    )
    assert token not in headers[0] and token[7:] not in headers[0]
    other = r.client()
    before = r.original_reads()
    assert other.login(r.issuer)[0][0] == 403 and r.original_reads() == before
    r.store.action_capacity = 1
    r.store.actions.clear()
    assert client.request("GET", PREFIX)[0] == 200
    before = r.original_reads()
    assert client.request("GET", PREFIX)[0] == 403
    # Authorized read occurred before the bounded form-nonce allocation failed;
    # no response source escaped and no DB business state was changed.
    assert snapshot(r) == r.baseline
