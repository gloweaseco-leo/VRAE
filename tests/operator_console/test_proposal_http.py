"""Real loopback HTTP transport, no authentication or persistent submission."""

from contextlib import contextmanager
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlsplit, urlencode
import json
import os
import subprocess
import sys

import pytest

from apps.operator_console.fixtures import make_fixture
from apps.operator_console.preview import serve


@pytest.fixture(scope="module")
def http_fixture():
    root = Path(__file__).resolve().parents[2]
    process = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "-m",
            "apps.operator_console.preview",
            "--test-only",
            "--synthetic-fixtures",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(os.environ, PYTHONUTF8="1"),
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    try:
        url = json.loads(process.stdout.readline())["url"]
        yield urlsplit(url)
    finally:
        process.terminate()
        process.communicate(timeout=15)


def body(case="404"):
    s, c = make_fixture()
    task = s.detail(c, "task-" + case)
    _, d = s.review(c, task["task_id"], 1, task["report_pins"]["expected_draft_ref"])
    t = d["review_target"]["target"]
    digest = d["review_target"]["target_digest"]
    f = {
        "version": "1",
        "draft": t["draft_ref"],
        "target": digest,
        "reason": "",
        "action": "APPROVE_CANDIDATE" if case == "404" else "SIMULATED_INTERNAL_SCOPE_ACK",
    }
    for i, claim in enumerate(t["claims"]):
        f.update(
            {
                f"guard.{i}": claim["guard_ref"],
                f"binding.{i}": claim["binding_ref"],
                f"pointer.{i}": claim["pointer"],
                f"disposition.{i}": claim["allowed_acceptance"],
            }
        )
    f.update({"section." + section: digest for section in t["required_sections"]})
    return urlencode(f).encode()


@contextmanager
def connection(url):
    c = HTTPConnection(url.hostname, url.port, timeout=30)
    try:
        yield c
    finally:
        c.close()


@pytest.mark.parametrize("case", ["404", "200"])
def test_real_preview_http_and_fresh_unsubmitted_get(http_fixture, case):
    url = http_fixture
    raw = body(case)
    with connection(url) as c:
        c.request(
            "POST",
            url.path + "tasks/task-" + case + "/proposal-preview",
            raw,
            {"Origin": "http://" + url.netloc, "Content-Type": "application/x-www-form-urlencoded"},
        )
        r = c.getresponse()
        text = r.read().decode()
        assert r.status == 200 and "CONTRACT_VALID_ONLY" in text and "PRIVATE_NOT_APPROVED" in text
        assert r.getheader("Cache-Control") == "no-store"
        assert "connect-src 'none'" in r.getheader("Content-Security-Policy")
        assert not r.getheader("Set-Cookie")
        assert r.getheader("Referrer-Policy") == "same-origin"
    from urllib.parse import parse_qs

    f = parse_qs(raw.decode(), keep_blank_values=True)
    query = urlencode({k: f[k][0] for k in ("version", "draft", "target")})
    with connection(url) as c:
        c.request("GET", url.path + "tasks/task-" + case + "/proposal?" + query)
        r = c.getresponse()
        text = r.read().decode()
        assert r.status == 200 and "data-outcome=" not in text
        assert " checked" not in text and " selected" not in text


@pytest.mark.parametrize(
    "attack",
    [
        "origin",
        "null-origin",
        "missing-origin",
        "host",
        "cookie",
        "authorization",
        "content-type",
        "body-bound",
        "duplicate-length",
        "duplicate-origin",
        "duplicate-host",
        "transfer-encoding",
        "missing-length",
        "cross-site",
        "same-site",
        "duplicate-content-type",
    ],
)
def test_real_header_body_constraints(http_fixture, attack):
    url = http_fixture
    # Invalid requests must be rejected without needing to send or parse private data.
    headers = {
        "Host": url.netloc,
        "Origin": "http://" + url.netloc,
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": "0",
    }
    if attack == "origin":
        headers["Origin"] = "https://evil.example"
    if attack == "null-origin":
        headers["Origin"] = "null"
    if attack == "missing-origin":
        del headers["Origin"]
    if attack == "host":
        headers["Host"] = "evil.example"
    if attack == "cookie":
        headers["Cookie"] = "owner=verified"
    if attack == "authorization":
        headers["Authorization"] = "Bearer forged-owner"
    if attack == "content-type":
        headers["Content-Type"] = "application/json"
    if attack == "body-bound":
        headers["Content-Length"] = "24577"
    if attack == "transfer-encoding":
        headers["Transfer-Encoding"] = "chunked"
    if attack == "missing-length":
        del headers["Content-Length"]
    if attack in ("cross-site", "same-site"):
        headers["Sec-Fetch-Site"] = attack
    with connection(url) as c:
        c.putrequest("POST", url.path + "tasks/task-404/proposal-preview", skip_host=True)
        for key, value in headers.items():
            c.putheader(key, value)
        if attack.startswith("duplicate-"):
            key = {
                "duplicate-length": "Content-Length",
                "duplicate-origin": "Origin",
                "duplicate-host": "Host",
                "duplicate-content-type": "Content-Type",
            }[attack]
            c.putheader(key, headers[key])
        c.endheaders()
        r = c.getresponse()
        text = r.read()
        assert r.status == 403 and b"ev-" not in text and b"cb-" not in text


@pytest.mark.parametrize(
    "action", ["approve", "reject", "share", "export", "download", "mutate", "review"]
)
def test_prohibited_http_actions_remain_denied(http_fixture, action):
    url = http_fixture
    with connection(url) as c:
        c.request(
            "POST",
            url.path + "tasks/task-404/" + action,
            b"",
            {"Origin": "http://" + url.netloc, "Content-Type": "application/x-www-form-urlencoded"},
        )
        r = c.getresponse()
        text = r.read()
        assert r.status == 501 and b"cb-" not in text


@pytest.mark.parametrize(
    "path",
    [
        "tasks/not-assigned/proposal-preview",
        "tasks/task-404/proposal-preview?trusted=true",
        "tasks/task-404/proposal-preview?url=https://evil.example",
    ],
)
def test_unknown_and_query_posts_no_source_leak(http_fixture, path):
    url = http_fixture
    with connection(url) as c:
        c.request(
            "POST",
            url.path + path,
            b"",
            {"Origin": "http://" + url.netloc, "Content-Type": "application/x-www-form-urlencoded"},
        )
        r = c.getresponse()
        text = r.read()
        assert r.status in (400, 403) and b"cb-" not in text and b"ev-" not in text


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"test_only": True},
        {"synthetic_fixtures": True},
        {"test_only": True, "synthetic_fixtures": True, "host": "0.0.0.0"},
    ],
)
def test_external_or_production_mode_inert(kwargs):
    with pytest.raises(ValueError, match="TEST_ONLY_LOOPBACK_REQUIRED"):
        serve(**kwargs)
