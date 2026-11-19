"""HARNESS_SELFTEST_ONLY. Fake connections do not satisfy any G1 HTTP gate."""

from copy import deepcopy
import json
from pathlib import Path
import socket

import pytest

from integration.l2_launch.consumer.client import (
    BASE,
    PROFILE,
    RULES,
    CheckError,
    Consumer,
    WireClient,
    encode,
    owned_endpoint,
    parse,
    redacted,
    report,
    sha,
)
from tests.l2_launch.vf_b_fixtures import free_publication_fixture

ROOT = Path(__file__).resolve().parents[2]
SERVER = "1" * 40
ENV = {
    "G1_C2_SERVICE_TOKEN": "PRIVATE-SERVER-SECRET",
    "G1_C2_OTHER_TENANT_TOKEN": "PRIVATE-OTHER-SECRET",
}


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    calls = []

    def denied(*args, **kwargs):
        calls.append(True)
        raise AssertionError("HARNESS_SELFTEST_NETWORK_FORBIDDEN")

    for name in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, denied)
    yield
    assert not calls


def sample(name):
    return json.loads(
        (ROOT / "contracts/l2_launch/examples" / (name + ".json")).read_text(encoding="utf-8")
    )["body"]


def manifest():
    return {
        "scope": "C3_OWNED_OFFLINE_SYNTHETIC_G1",
        "server_sha": SERVER,
        "owned_run_id": "unit-fixture-only",
        "base_url": "http://127.0.0.1:54321",
        "profile": PROFILE,
        "bindings": {},
    }


class FakeWire:
    def __init__(self, body=None, status=200, headers=None):
        self.body, self.status = body or {}, status
        self.headers = (
            {"cache-control": ["private, no-store"], "x-vrae-source-sha": [SERVER]}
            if headers is None
            else headers
        )
        self.calls = []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if kwargs.get("disconnect"):
            return None
        return self.status, self.headers, deepcopy(self.body), sha(encode(self.body))


def client(wire=None):
    return Consumer(manifest(), wire=wire or FakeWire(), env=ENV)


def binding(body=None, **kwargs):
    return {"method": "POST", "path": "/c3-unit-fixture-only", "body": body, **kwargs}


def artifact(tmp_path, body):
    path = tmp_path / "private-fixture.json"
    raw = encode(body)
    path.write_bytes(raw)
    return {"path": str(path), "sha256": sha(raw)}


def test_no_C3_input_is_pending_not_pass_and_never_dials():
    result = report()
    assert result["state"] == "G1_HTTP_PENDING" and result["baseline_sha"] == BASE
    assert len(result["cases"]) == len(RULES) and {c["status"] for c in result["cases"]} == {
        "BLOCKED"
    }
    wire = FakeWire()
    result = report(manifest(), consumer=client(wire))
    assert result["state"] == "G1_HTTP_PENDING" and not wire.calls


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:1234",
        "http://127.0.0.2:1234",
        "https://127.0.0.1:1234",
        "http://169.254.169.254:1234",
        "http://127.0.0.1",
        "http://user:secret@127.0.0.1:1234",
        "http://127.0.0.1:1234/x",
        "http://127.0.0.1:1234?x=secret",
        "http://127.0.0.1:80",
    ],
)
def test_only_explicit_literal_owned_loopback(url):
    with pytest.raises(CheckError):
        owned_endpoint(url)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'])
def test_strict_json(raw):
    with pytest.raises(CheckError):
        parse(raw)


def test_actual_wire_uses_http_client_without_redirect_or_proxy_or_response_secret_log():
    calls = []

    class Response:
        status = 200

        def read(self, limit):
            return b'{"restored":true}'

        def getheaders(self):
            return [("Cache-Control", "no-store")]

    class Connection:
        def __init__(self, host, port, **kwargs):
            calls.append((host, port, kwargs))

        def request(self, *args):
            calls.append(args)

        def getresponse(self):
            return Response()

        def close(self):
            calls.append("closed")

    wire = WireClient("http://127.0.0.1:54321", factory=Connection)
    assert wire.request("POST", "/fixture", {"Authorization": "secret"}, {"x": 1})[0] == 200
    assert calls[0] == ("127.0.0.1", 54321, {"timeout": 10}) and calls[-1] == "closed"
    calls.clear()
    assert wire.request("POST", "/fixture", {}, {}, disconnect=True) is None
    assert calls[-1] == "closed"


@pytest.mark.parametrize(
    "target", ["https://other.invalid/", "//other.invalid", "/x\r\ny", "/x#token"]
)
def test_wire_rejects_nonrelative_targets(target):
    with pytest.raises(CheckError):
        WireClient("http://127.0.0.1:54321").request("GET", target, {}, None)


def test_server_only_credentials_not_body_roles_or_header_overrides():
    c = client()
    assert c.headers(binding())["Authorization"] == "Bearer " + ENV["G1_C2_SERVICE_TOKEN"]
    with pytest.raises(CheckError):
        c.headers(binding(credential="APP_BEARER"))
    with pytest.raises(CheckError):
        c.headers(binding(headers={"Authorization": "browser-token"}))
    assert "Authorization" not in c.headers(binding(credential="none"))


def test_create_http202_without_PG_evidence_is_blocked(tmp_path):
    accepted = sample("vfb-accepted-202")
    wire = FakeWire(accepted, 202)
    c = client(wire)
    submission = sample("vfb-submit")
    result = c.run_case("create", binding(submission))
    assert result["status"] == "BLOCKED" and result["reason"] == "C3_PG_RECEIPT_PENDING"
    receipt = {
        "server_sha": SERVER,
        "owned_run_id": "unit-fixture-only",
        "audit_ref": accepted["audit_ref"],
        "run_id": accepted["run_id"],
        "committed": True,
        "job_count": 1,
    }
    result = c.run_case("create", binding(submission, pg_receipt=artifact(tmp_path, receipt)))
    assert result["status"] == "PASS"  # a unit predicate, never actual HTTP evidence
    assert ENV["G1_C2_SERVICE_TOKEN"] not in json.dumps(result)


def test_idempotency_and_disconnect_retry_require_same_intent():
    accepted = sample("vfb-accepted-202")
    wire = FakeWire(accepted, 202)
    c, submission = client(wire), sample("vfb-submit")
    c.run_case("create", binding(submission))
    assert c.run_case("replay", binding(submission))["status"] == "PASS"
    wire.calls.clear()
    assert c.run_case("disconnect_retry", binding(submission))["status"] == "PASS"
    assert wire.calls[0][1] == {"disconnect": True} and len(wire.calls) == 2
    changed = deepcopy(submission)
    changed["language"] = "en"
    assert c.run_case("replay", binding(changed))["reason"] == "IDEMPOTENCY_INTENT_PRECONDITION"
    wire.body["audit_ref"] = "another-reference"
    assert c.run_case("replay", binding(submission))["reason"] == "IDEMPOTENT_REFERENCE_CHANGED"


def test_network_errors_and_missing_credentials_never_become_pass():
    c = Consumer(manifest(), wire=FakeWire(), env={})
    assert c.run_case("status_axes", binding())["status"] == "BLOCKED"

    class Offline(FakeWire):
        def request(self, *args, **kwargs):
            raise OSError("PRIVATE-SECRET")

    result = client(Offline()).run_case("status_axes", binding())
    assert result["status"] == "BLOCKED" and "PRIVATE-SECRET" not in json.dumps(result)


def test_unknown_server_source_is_not_exact_SHA_evidence():
    result = client(FakeWire(headers={"cache-control": ["no-store"]})).run_case(
        "status_axes", binding()
    )
    assert result["reason"] == "C3_HTTP_SOURCE_BINDING_PENDING"
    result = client(FakeWire(headers={"x-vrae-source-sha": ["2" * 40]})).run_case(
        "status_axes", binding()
    )
    assert result["reason"] == "C3_HTTP_SOURCE_SHA_MISMATCH"


@pytest.mark.parametrize("attribute", ["Secure", "HttpOnly", "SameSite=Strict", "Path=/"])
def test_cookie_policy_is_an_actual_header_assertion(attribute):
    raw = "__Host-session=PRIVATE-COOKIE; Secure; HttpOnly; SameSite=Strict; Path=/"
    raw = raw.replace("; " + attribute, "")
    headers = {
        "cache-control": ["no-store"],
        "set-cookie": [raw],
        "x-csrf-token": ["PRIVATE-CSRF"],
        "x-vrae-source-sha": [SERVER],
    }
    c = client(FakeWire({"restored": True}, headers=headers))
    result = c.run_case("return_exchange", binding())
    assert result["status"] == "FAIL" and "PRIVATE-COOKIE" not in json.dumps(result)


def test_csrf_cases_cannot_pass_by_omitting_session():
    c = client(FakeWire(sample("vfb-safe-error-403"), 403))
    assert c.run_case("csrf_missing", binding())["reason"] == "VALID_SESSION_PRECONDITION_PENDING"


def test_draft_status_never_becomes_completed():
    body = sample("vfb-draft-ready-not-completed")
    c = client(FakeWire(body))
    c.variables.update(audit_ref=body["audit_ref"], run_id=body["task"]["run_id"])
    assert c.run_case("draft_not_completed", binding())["status"] == "PASS"
    c.wire.body["display_state"] = "completed"
    assert c.run_case("draft_not_completed", binding())["reason"] == "UNPUBLISHED_COMPLETION"


@pytest.mark.parametrize(
    "mutation", ["translation", "counter", "hash", "version", "released", "priority", "private"]
)
def test_projection_uses_original_facts_and_exact_view_hash(tmp_path, mutation):
    accepted = sample("vfb-accepted-202")
    original = free_publication_fixture(accepted["audit_ref"], accepted["run_id"])
    view = deepcopy(original["free_view"])
    c = client(FakeWire(view))
    c.variables["audit_ref"], c.cookies = accepted["audit_ref"], "session=PRIVATE-COOKIE"
    c.variables["run_id"] = accepted["run_id"]
    c.creation_command = deepcopy(original["bundle"]["source_command"])
    b = binding(
        original_bundle=artifact(tmp_path, original["bundle"]), view_sha256=sha(encode(view))
    )
    assert c.run_case("preview", b)["status"] == "PASS"
    if mutation == "translation":
        c.wire.body["summary"]["A"]["zh"] = "changed translation"
    elif mutation == "counter":
        c.wire.body["results"]["UNDERSTAND"].pop(1)
    elif mutation == "hash":
        c.wire.body["report_version_id"] = "report-other.v1"
    elif mutation == "version":
        original["bundle"]["latest_version"] = 2
        b["original_bundle"] = artifact(tmp_path, original["bundle"])
    elif mutation == "released":
        c.wire.body["kind"] = "released"
    elif mutation == "priority":
        c.wire.body["priority"] = ["one", "two", "three", "four"]
    elif mutation == "private":
        c.wire.body["evidence_pack"] = {"raw": "PRIVATE-EVIDENCE"}
    result = c.run_case("preview", b)
    assert result["status"] == "FAIL" and "PRIVATE-EVIDENCE" not in json.dumps(result)


def test_redaction_masks_values_and_unknown_field_names():
    raw = {"PRIVATE-TOKEN-AS-KEY": "PRIVATE-VALUE", "summary": {"en": "PRIVATE-TEXT"}}
    result = json.dumps(redacted(raw))
    assert all(
        value not in result for value in ("PRIVATE-TOKEN-AS-KEY", "PRIVATE-VALUE", "PRIVATE-TEXT")
    )


def test_successful_cookie_exchange_stays_private_in_result():
    headers = {
        "cache-control": ["no-store"],
        "set-cookie": ["__Host-session=PRIVATE-COOKIE; Secure; HttpOnly; SameSite=Strict; Path=/"],
        "x-csrf-token": ["PRIVATE-CSRF"],
        "x-vrae-source-sha": [SERVER],
    }
    c = client(FakeWire({"restored": True}, headers=headers))
    result = c.run_case("return_exchange", binding())
    assert result["status"] == "PASS" and result["cookie_policy"]["secure"]
    assert c.cookies == "__Host-session=PRIVATE-COOKIE" and c.variables["csrf"] == "PRIVATE-CSRF"
    assert "PRIVATE-COOKIE" not in json.dumps(result) and "PRIVATE-CSRF" not in json.dumps(result)


def test_expiry_without_prior_authorized_response_is_blocked():
    c = client(FakeWire(sample("vfb-safe-error-403"), 403))
    c.cookies = "session=private-cookie"
    assert (
        c.run_case("expired_session", binding())["reason"] == "AUTHORIZED_PREVIEW_BASELINE_PENDING"
    )


def test_pending_case_and_failure_are_distinct():
    c = client(FakeWire({}, status=500))
    result = c.run_case("status_axes", binding())
    assert result["status"] == "FAIL" and result["reason"] == "HTTP_STATUS_MISMATCH"


def test_durable202_receipt_cannot_claim_two_jobs(tmp_path):
    accepted = sample("vfb-accepted-202")
    c = client(FakeWire(accepted, 202))
    receipt = {
        "server_sha": SERVER,
        "owned_run_id": "unit-fixture-only",
        "audit_ref": accepted["audit_ref"],
        "run_id": accepted["run_id"],
        "committed": True,
        "job_count": 2,
    }
    result = c.run_case(
        "create", binding(sample("vfb-submit"), pg_receipt=artifact(tmp_path, receipt))
    )
    assert result["reason"] == "PG_ACCEPTANCE_EVIDENCE_MISMATCH"
