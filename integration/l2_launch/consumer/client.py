"""Actual loopback HTTP consumer. No server, worker, mock fallback or CRM.

Runtime requires an explicit C3-owned endpoint/commit/bindings manifest. Absent
that input every acceptance case is BLOCKED and the process exits 2. Unit tests
exercise this client with fake connections; those are never G1 HTTP evidence.
"""

import argparse
from copy import deepcopy
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

BASE = "7fdeeed0f427ce3b94677ab2a480eae1556e85ca"
PROFILE = "vf-vrae-r0.1-vfb.1"
MEDIA = 'application/vnd.vrae.launch+json; profile="' + PROFILE + '"'
ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "integration/l2_launch/consumer/.runtime"
LIMIT = 512 * 1024
RULES = {
    "create": (202, "VFAccepted"),
    "replay": (202, "VFAccepted"),
    "changed_intent": (409, "VFSafeError"),
    "disconnect_retry": (202, "VFAccepted"),
    "return_exchange": (200, None),
    "status_axes": (200, "VFStatus"),
    "draft_not_completed": (200, "VFStatus"),
    "unapproved_report": (403, "VFSafeError"),
    "preview": (200, "FreePreDiagnosticView"),
    "stale_report": ((403, 409), "VFSafeError"),
    "bare_ref": (403, "VFSafeError"),
    "wrong_tenant": (403, "VFSafeError"),
    "expired_session": (403, "VFSafeError"),
    "withdrawn_session": (403, "VFSafeError"),
    "csrf_missing": (403, "VFSafeError"),
    "csrf_invalid": (403, "VFSafeError"),
    "rate_limited": (429, "VFSafeError"),
    "dependency_unavailable": (503, "VFSafeError"),
    "inquiry_waiting_ack": (202, "HandoffStatus"),
    "after_restart": (202, "VFAccepted"),
    "bad_accept": (406, None),
    "bad_content_type": (415, None),
    "missing_service_auth": (403, "VFSafeError"),
}
ENV_KEYS = {
    "service": "G1_C2_SERVICE_TOKEN",
    "wrong_tenant": "G1_C2_OTHER_TENANT_TOKEN",
    "owner_fixture": "G1_C2_OWNER_FIXTURE_TOKEN",
    "return_token": "G1_C2_RETURN_TOKEN",
}


class CheckError(ValueError):
    """Only fixed predicate IDs may leave the private client context."""


class Pending(CheckError):
    pass


def require(condition, code):
    if not condition:
        raise CheckError(code)


def encode(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    def non_json(_):
        raise CheckError("NON_JSON_NUMBER")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique, parse_constant=non_json)


def owned_endpoint(url):
    p = urlsplit(url)
    require(
        p.scheme == "http"
        and p.hostname == "127.0.0.1"
        and p.port is not None
        and 1024 <= p.port <= 65535
        and not p.username
        and not p.password
        and p.path in {"", "/"}
        and not p.query
        and not p.fragment,
        "OWNED_LITERAL_LOOPBACK_REQUIRED",
    )
    return p.port


def redacted(value):
    # Preserve structure and scalar types, never raw strings/URLs/credentials.
    if isinstance(value, dict):
        public = {
            "contract_version",
            "audit_ref",
            "run_id",
            "run_status",
            "diagnosis_complete",
            "poll_after_seconds",
            "task",
            "publication",
            "access",
            "status",
            "state",
            "display_state",
            "progress_percent",
            "code",
            "retryable",
            "http_status",
            "retry_after_seconds",
            "restored",
            "results",
            "DISCOVER",
            "UNDERSTAND",
            "TRUST",
            "INQUIRE",
            "SEARCH_TECHNICAL",
            "coverage",
            "priority",
            "kind",
            "fact_id",
            "original_fact_ref",
            "citation_ids",
            "view_type",
            "report_version_id",
            "summary",
            "A",
            "B",
            "en",
            "zh",
            "citations",
            "limitations",
            "handoff",
            "delivery_state",
            "counts_as_e2",
            "counts_as_e3",
            "customer_approval",
            "quote_allowed",
        }
        return {
            (str(k) if k in public else "[PRIVATE_FIELD_" + str(i) + "]"): redacted(v)
            for i, (k, v) in enumerate(value.items())
        }
    if isinstance(value, list):
        return [redacted(v) for v in value]
    return (
        "[REDACTED]"
        if isinstance(value, (str, int, float)) and not isinstance(value, bool)
        else value
    )


def checked_file(binding, key):
    item = binding.get(key)
    if not item:
        raise Pending("C3_" + key.upper() + "_PENDING")
    raw = Path(item["path"]).read_bytes()
    require(len(raw) <= 4 * LIMIT and sha(raw) == item["sha256"], "C3_EVIDENCE_HASH_MISMATCH")
    return parse(raw)


class WireClient:
    def __init__(self, url, *, factory=None):
        self.port = owned_endpoint(url)
        self.factory = factory or http.client.HTTPConnection

    def request(self, method, path, headers, body, *, disconnect=False):
        require(
            method in {"GET", "POST"}
            and path.startswith("/")
            and not path.startswith("//")
            and not any(c in path for c in ("\r", "\n", "#"))
            and not urlsplit(path).scheme
            and not urlsplit(path).netloc,
            "RELATIVE_REQUEST_TARGET_REQUIRED",
        )
        connection = self.factory("127.0.0.1", self.port, timeout=10)
        raw = encode(body) if body is not None else None
        try:
            connection.request(method, path, raw, headers)
            if disconnect:
                return None  # send once, close before consuming the acknowledgement
            response = connection.getresponse()
            data = response.read(LIMIT + 1)
            require(len(data) <= LIMIT, "RESPONSE_TOO_LARGE")
            require(not 300 <= response.status < 400, "REDIRECT_FORBIDDEN")
            pairs = response.getheaders()
            lower = {}
            for key, value in pairs:
                lower.setdefault(key.lower(), []).append(value)
            require(
                lower.get("content-encoding", ["identity"]) == ["identity"],
                "ENCODED_RESPONSE_UNSUPPORTED",
            )
            body = parse(data)
            require(isinstance(body, dict), "OBJECT_RESPONSE_REQUIRED")
            return response.status, lower, body, sha(data)
        finally:
            connection.close()


class Consumer:
    def __init__(self, manifest, *, wire=None, env=None):
        require(manifest["scope"] == "C3_OWNED_OFFLINE_SYNTHETIC_G1", "C3_OWNERSHIP_REQUIRED")
        require(
            re.fullmatch("[0-9a-f]{40}", manifest["server_sha"]) is not None,
            "EXACT_C3_SHA_REQUIRED",
        )
        require(manifest["profile"] == PROFILE, "FROZEN_PROFILE_REQUIRED")
        require(
            re.fullmatch(r"[A-Za-z0-9_-]{8,100}", manifest["owned_run_id"]) is not None,
            "OWNED_RUN_ID_REQUIRED",
        )
        self.manifest = manifest
        self.wire = wire or WireClient(manifest["base_url"])
        owned_endpoint(manifest["base_url"])
        self.env = os.environ if env is None else env
        self.variables, self.cookies, self.uniform = {}, "", None
        self.creation_hash, self.creation_key = None, None
        self.creation_command = None
        self.preview_baseline = None

    def expand(self, value):
        if isinstance(value, dict):
            return {k: self.expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.expand(v) for v in value]
        if isinstance(value, str):
            for name in re.findall(r"\$\{([a-z_]+)\}", value):
                actual = self.variables.get(name)
                if actual is None and name == "return_token":
                    actual = self.env.get(ENV_KEYS[name])
                if actual is None:
                    raise Pending("C3_BINDING_VALUE_PENDING")
                value = value.replace("${" + name + "}", actual)
        return value

    def headers(self, binding):
        headers = {"Accept": MEDIA, "Accept-Encoding": "identity"}
        if binding["method"] == "POST":
            headers["Content-Type"] = MEDIA
        auth = binding.get("credential", "service")
        require(
            auth in (set(ENV_KEYS) - {"return_token"}) | {"none", "invalid"},
            "SERVER_ONLY_CREDENTIAL_ALIAS_REQUIRED",
        )
        if auth != "none":
            token = (
                "invalid-synthetic-credential"
                if auth == "invalid"
                else self.env.get(ENV_KEYS[auth])
            )
            if not token:
                raise Pending("C3_SERVER_ONLY_CREDENTIAL_PENDING")
            headers["Authorization"] = "Bearer " + token
        for key, value in binding.get("headers", {}).items():
            require(
                key in {"Accept", "Content-Type", "Origin", "X-CSRF-Token"},
                "HEADER_OVERRIDE_FORBIDDEN",
            )
            if value is None:
                headers.pop(key, None)
            else:
                headers[key] = self.expand(value)
        if binding.get("cookie", "current") == "current" and self.cookies:
            headers["Cookie"] = self.cookies
        return headers

    def validate(self, name, body, headers, binding):
        from contracts.l2_launch.contract import validate
        from contracts.l2_launch.vf_b import validate_free_view

        require(
            "no-store"
            in {v.strip() for v in ",".join(headers.get("cache-control", [])).lower().split(",")},
            "NO_STORE_REQUIRED",
        )
        schema = RULES[name][1]
        if schema:
            try:
                validate(schema, body)
            except ValueError:
                raise CheckError("FROZEN_RESPONSE_SCHEMA_MISMATCH") from None
        if schema == "VFAccepted":
            if name == "create":
                self.variables.update(audit_ref=body["audit_ref"], run_id=body["run_id"])
            else:
                if "audit_ref" not in self.variables:
                    raise Pending("CREATE_REFERENCE_PENDING")
                require(
                    all(body[k] == self.variables[k] for k in ("audit_ref", "run_id")),
                    "IDEMPOTENT_REFERENCE_CHANGED",
                )
            require(
                not any(k in body for k in ("audit_id", "tenant_id", "request_id", "job_id")),
                "INTERNAL_IDENTIFIER_LEAK",
            )
            if name in {"create", "after_restart"}:
                evidence = checked_file(binding, "pg_receipt")
                require(
                    evidence["server_sha"] == self.manifest["server_sha"]
                    and evidence["owned_run_id"] == self.manifest["owned_run_id"]
                    and evidence["audit_ref"] == body["audit_ref"]
                    and evidence["run_id"] == body["run_id"]
                    and evidence["committed"] is True
                    and evidence["job_count"] == 1,
                    "PG_ACCEPTANCE_EVIDENCE_MISMATCH",
                )
                if name == "after_restart":
                    require(
                        evidence["server_restarted"] is True and evidence["pg_restarted"] is True,
                        "RESTART_EVIDENCE_REQUIRED",
                    )
        if schema == "VFStatus":
            require(
                body["audit_ref"] == self.variables.get("audit_ref")
                and body["task"]["run_id"] == self.variables.get("run_id"),
                "SAME_TASK_STATUS_BINDING_REQUIRED",
            )
            require(body["task"]["progress_percent"] is None, "FAKE_PROGRESS")
            if body["publication"]["state"] == "UNPUBLISHED":
                require(
                    body["display_state"] not in {"completed", "partial"}, "UNPUBLISHED_COMPLETION"
                )
            if name == "draft_not_completed":
                require(
                    body["task"]["status"] == "DRAFT_READY"
                    and body["publication"]["state"] == "UNPUBLISHED",
                    "ACTUAL_DRAFT_STAGE_REQUIRED",
                )
        if name == "return_exchange":
            require(body.get("restored") is True, "RESTORED_SESSION_REQUIRED")
            cookies = SimpleCookie()
            for raw in headers.get("set-cookie", []):
                cookies.load(raw)
            require(len(cookies) == 1, "EXACTLY_ONE_PRIVATE_SESSION_REQUIRED")
            morsel = next(iter(cookies.values()))
            require(
                morsel["secure"]
                and morsel["httponly"]
                and morsel["samesite"].lower() == "strict"
                and not morsel["domain"]
                and morsel["path"] == "/",
                "PRIVATE_COOKIE_POLICY_REQUIRED",
            )
            self.cookies = morsel.key + "=" + morsel.value
            csrf = headers.get("x-csrf-token", [])
            require(len(csrf) == 1 and bool(csrf[0]), "SERVER_CSRF_TOKEN_REQUIRED")
            self.variables["csrf"] = csrf[0]
        if name == "preview":
            bundle = checked_file(binding, "original_bundle")
            from vrae.domain.contracts import validate_contract
            from vrae.domain.reviews import report_content_hash

            validate_contract("ReportVersion", bundle["report"])
            require(
                bundle["report"]["status"] == "APPROVED"
                and bundle["latest_version"] == bundle["report"]["version"]
                and report_content_hash(bundle["report"], bundle["findings"])
                == bundle["report"]["content_hash"],
                "ORIGINAL_FACT_VERSION_HASH_MISMATCH",
            )
            require(
                bundle["report"]["run_id"] == self.variables.get("run_id")
                and bundle["source_command"] == self.creation_command,
                "SAME_TASK_ORIGINAL_FACTS_REQUIRED",
            )
            validate_free_view(body, bundle)
            require(
                sha(encode(body)) == binding.get("view_sha256")
                and body["kind"] == "synthetic"
                and body["audit_ref"] == self.variables.get("audit_ref"),
                "EXACT_SYNTHETIC_VIEW_BINDING_REQUIRED",
            )
        if name in {"bare_ref", "wrong_tenant", "expired_session", "withdrawn_session"}:
            if self.uniform is None:
                self.uniform = body
            require(body == self.uniform, "UNAUTHORIZED_EXISTENCE_DISCLOSURE")
        if name == "inquiry_waiting_ack":
            require(
                body["delivery_state"] == "WAITING_ACK"
                and body["handoff"]["stage"] == "HANDOFF_REQUESTED"
                and body["handoff"]["vf_receipt_ref"] is None
                and not any(
                    body[k]
                    for k in ("counts_as_e2", "counts_as_e3", "quote_allowed", "customer_approval")
                ),
                "UNVERIFIED_BUSINESS_UPGRADE",
            )

    def run_case(self, name, binding):
        record = {"case": name, "status": "BLOCKED", "reason": "C3_HTTP_BINDING_PENDING"}
        if not binding:
            return record
        try:
            body = self.expand(deepcopy(binding.get("body")))
            path, headers = self.expand(binding["path"]), self.headers(binding)
            self.preconditions(name, body, headers, path)
            record["request"] = {
                "method": binding["method"],
                "path": "[PRIVATE_C3_PATH]",
                "body": redacted(body),
            }
            if name == "disconnect_retry":
                self.wire.request(binding["method"], path, headers, body, disconnect=True)
            status, reply_headers, reply, raw_hash = self.wire.request(
                binding["method"], path, headers, body
            )
            record.update(http_status=status, response_sha256=raw_hash, response=redacted(reply))
            record["response_headers"] = {
                "no_store": "no-store"
                in {
                    v.strip()
                    for v in ",".join(reply_headers.get("cache-control", [])).lower().split(",")
                },
                "set_cookie_present": bool(reply_headers.get("set-cookie")),
                "csrf_header_present": bool(reply_headers.get("x-csrf-token")),
            }
            source = reply_headers.get(
                self.manifest.get("source_header", "X-VRAE-Source-SHA").lower(), []
            )
            if not source:
                raise Pending("C3_HTTP_SOURCE_BINDING_PENDING")
            require(source == [self.manifest["server_sha"]], "C3_HTTP_SOURCE_SHA_MISMATCH")
            expected_status = RULES[name][0]
            require(
                status in expected_status
                if isinstance(expected_status, tuple)
                else status == expected_status,
                "HTTP_STATUS_MISMATCH",
            )
            if RULES[name][1] == "VFSafeError":
                require(reply.get("http_status") == status, "HTTP_ERROR_ENVELOPE_STATUS_MISMATCH")
            self.validate(name, reply, reply_headers, binding)
            if name == "preview":
                self.preview_baseline = {
                    "path": path,
                    "session_sha256": sha(self.cookies.encode()),
                    "response_sha256": raw_hash,
                }
            if name in {"expired_session", "withdrawn_session"}:
                evidence = checked_file(binding, "access_receipt")
                require(
                    evidence["server_sha"] == self.manifest["server_sha"]
                    and evidence["owned_run_id"] == self.manifest["owned_run_id"]
                    and evidence["audit_ref"] == self.variables["audit_ref"]
                    and evidence["state"]
                    == ("EXPIRED" if name == "expired_session" else "WITHDRAWN")
                    and evidence["session_sha256"] == self.preview_baseline["session_sha256"]
                    and evidence["baseline_response_sha256"]
                    == self.preview_baseline["response_sha256"],
                    "ACCESS_TRANSITION_EVIDENCE_MISMATCH",
                )
            if name == "return_exchange":
                record["cookie_policy"] = {
                    "secure": True,
                    "httponly": True,
                    "same_site": "Strict",
                    "path": "/",
                    "domain_absent": True,
                }
            record.update(status="PASS", reason="HTTP_CONTRACT_ASSERTIONS_PASSED")
        except Pending as error:
            record["reason"] = error.args[0]
        except CheckError as error:
            record.update(status="FAIL", reason=error.args[0])
        except (OSError, http.client.HTTPException):
            record.update(status="BLOCKED", reason="C3_HTTP_OR_EVIDENCE_UNAVAILABLE")
        except Exception:
            record.update(status="FAIL", reason="MALFORMED_C3_INPUT_OR_RESPONSE")
        return record

    def preconditions(self, name, body, headers, path):
        # Prevent a wrong credential or missing session from falsely satisfying
        # a more specific CSRF/expiry/publication denial assertion.
        if name in {
            "csrf_missing",
            "csrf_invalid",
            "unapproved_report",
            "preview",
            "expired_session",
            "withdrawn_session",
            "wrong_tenant",
            "stale_report",
        }:
            if not self.cookies or headers.get("Cookie") != self.cookies:
                raise Pending("VALID_SESSION_PRECONDITION_PENDING")
        if name == "csrf_missing":
            require("X-CSRF-Token" not in headers, "MISSING_CSRF_CASE_PRECONDITION")
        if name == "csrf_invalid":
            require(
                bool(headers.get("X-CSRF-Token"))
                and headers["X-CSRF-Token"] != self.variables.get("csrf"),
                "INVALID_CSRF_CASE_PRECONDITION",
            )
        if name == "missing_service_auth":
            require("Authorization" not in headers, "NO_SERVICE_AUTH_CASE_PRECONDITION")
        if name == "bare_ref":
            require(
                "Authorization" in headers and "Cookie" not in headers,
                "BARE_REFERENCE_CASE_PRECONDITION",
            )
        if name == "wrong_tenant":
            require(
                headers.get("Authorization")
                == "Bearer " + self.env.get(ENV_KEYS["wrong_tenant"], ""),
                "WRONG_TENANT_CASE_PRECONDITION",
            )
        if name in {"expired_session", "withdrawn_session"}:
            if self.preview_baseline is None:
                raise Pending("AUTHORIZED_PREVIEW_BASELINE_PENDING")
            require(
                sha(self.cookies.encode()) == self.preview_baseline["session_sha256"],
                "SAME_SESSION_TRANSITION_REQUIRED",
            )
            require(path == self.preview_baseline["path"], "SAME_RESOURCE_TRANSITION_REQUIRED")
        if name == "bad_accept":
            require(headers.get("Accept") != MEDIA, "BAD_ACCEPT_CASE_PRECONDITION")
        if name == "bad_content_type":
            require(headers.get("Content-Type") != MEDIA, "BAD_CONTENT_TYPE_CASE_PRECONDITION")
        if name in {"create", "replay", "changed_intent", "disconnect_retry", "after_restart"}:
            from contracts.l2_launch.contract import validate

            try:
                validate("VFSubmit", body)
            except ValueError:
                raise CheckError("FROZEN_REQUEST_SCHEMA_MISMATCH") from None
            body_hash, key = sha(encode(body)), body["command"]["request"]["idempotency_key"]
            if name == "create":
                self.creation_hash, self.creation_key = body_hash, key
                self.creation_command = deepcopy(body["command"])
            else:
                if self.creation_hash is None:
                    raise Pending("CREATE_REQUEST_PRECONDITION_PENDING")
                require(key == self.creation_key, "IDEMPOTENCY_KEY_PRECONDITION")
                require(
                    (body_hash != self.creation_hash)
                    if name == "changed_intent"
                    else (body_hash == self.creation_hash),
                    "IDEMPOTENCY_INTENT_PRECONDITION",
                )

        def targets(value):
            if isinstance(value, dict):
                for v in value.values():
                    targets(v)
            elif isinstance(value, list):
                for v in value:
                    targets(v)
            elif isinstance(value, str) and value.startswith(("http://", "https://")):
                host = urlsplit(value).hostname or ""
                require(
                    host.endswith((".example", ".test", ".invalid"))
                    or host in {"example.com", "example.net", "example.org"},
                    "SYNTHETIC_TARGET_ONLY",
                )

        targets(body)


def report(manifest=None, *, consumer=None):
    cases = [{"case": name, "status": "BLOCKED", "reason": "G1_HTTP_PENDING"} for name in RULES]
    result = {
        "scope": "C2_HTTP_CONSUMER_NOT_G1_OWNER_SIGNOFF",
        "baseline_sha": BASE,
        "server_sha": None,
        "state": "G1_HTTP_PENDING",
        "cases": cases,
        "backend_evidence": "C3_RECEIPTS_NOT_INDEPENDENT_C2_PG_READ",
        "real_release": False,
        "real_vf_inquiry": False,
    }
    if manifest is not None:
        consumer = consumer or Consumer(manifest)
        require(set(manifest.get("bindings", {})) <= RULES.keys(), "UNKNOWN_ACCEPTANCE_CASE")
        result["server_sha"] = manifest["server_sha"]
        result["manifest_sha256"] = sha(encode(manifest))
        result["cases"] = [
            consumer.run_case(name, manifest.get("bindings", {}).get(name)) for name in RULES
        ]
        statuses = {c["status"] for c in result["cases"]}
        result["state"] = (
            "G1_HTTP_CONSUMER_FAIL"
            if "FAIL" in statuses
            else "G1_HTTP_PENDING"
            if "BLOCKED" in statuses
            else "G1_HTTP_CONSUMER_PASS_OWNER_REVIEW_PENDING"
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(RUNTIME.resolve()), "OWNED_RUNTIME_OUTPUT_REQUIRED")
    try:
        result = report(parse(args.manifest.read_bytes()) if args.manifest else None)
    except CheckError as error:
        result = report()
        result.update(state="G1_HTTP_CONSUMER_FAIL", preflight=error.args[0])
    except OSError:
        result = report()
        result["preflight"] = "C3_MANIFEST_UNAVAILABLE"
    except Exception:
        result = report()
        result.update(state="G1_HTTP_CONSUMER_FAIL", preflight="INVALID_C3_MANIFEST")
    result["consumer_sha"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    result["consumer_clean"] = not subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT
    ).strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(
        json.dumps(
            {
                "state": result["state"],
                "cases": {
                    s: sum(c["status"] == s for c in result["cases"])
                    for s in ("PASS", "FAIL", "BLOCKED")
                },
            }
        )
    )
    return (
        1
        if result["state"] == "G1_HTTP_CONSUMER_FAIL"
        else 2
        if result["state"] == "G1_HTTP_PENDING"
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
