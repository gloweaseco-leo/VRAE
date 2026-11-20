"""Tenant/subject-bound trusted service boundary. Draft status is separate from report release."""

import argparse
from datetime import datetime, UTC
import re
import secrets
import ssl
import json
from time import monotonic
from http.cookies import SimpleCookie
import psycopg
from contracts.l2_launch.contract import canonical, Refused, validate
from contracts.l2_launch.vf_b import VERSION, safe_error, vf_status
from integration.l2_launch.g1.http_server import (
    Handler as StrictHandler,
    BoundedServer,
    TransportError,
    MEDIA,
)
from integration.authorized_targets.authority import service_binding, check_submission, token_hash
from integration.authorized_targets import store

COOKIE = "__Host-vrae-targets"
REF = r"aref-[0-9a-f]{32}"


def automatic_session_allowed(cfg, binding, transport):
    return (cfg.get('target_intake_enabled') is True and transport.get('mtls') is True
        and binding.get('kind') == 'APP' and binding.get('port') is None
        and binding.get('health_probe') is None)


class Handler(StrictHandler):
    def dispatch(self, method):
        started = monotonic()
        self.request_ref = secrets.token_hex(8)
        self.response_status = None
        self.response_code = None
        try:
            self.route_target(method)
        except TransportError as e:
            self.close_connection = True
            self.send(e.status, {"transport_error": str(e.status)})
        except Refused as e:
            self.close_connection = True
            b = safe_error(e)
            self.send(b["http_status"], b)
        except psycopg.Error as e:
            self.close_connection = True
            code = "FORBIDDEN_ROLE"
            status = 403
            if e.sqlstate == "22023" and "IDEMPOTENCY" in str(e):
                code = "IDEMPOTENCY_CONFLICT"
                status = 409
            elif e.sqlstate == "53000":
                code = "QUOTA_EXCEEDED"
                status = 429
            elif isinstance(e, psycopg.OperationalError):
                code = "R0_STORAGE_UNAVAILABLE"
                status = 503
            b = safe_error(Refused(code, status, status in (429, 503)))
            self.send(status, b)
        except (ValueError, KeyError, TypeError):
            self.close_connection = True
            self.send(403, safe_error(Refused("FORBIDDEN_ROLE")))
        except PermissionError:
            self.close_connection = True
            self.send(403, safe_error(Refused("FORBIDDEN_ROLE")))
        except OSError:
            self.close_connection = True
            self.send(503, safe_error(Refused("R0_STORAGE_UNAVAILABLE", 503, True)))
        finally:
            # No raw path, cookie, URL, task/customer identity or exception text.
            print(json.dumps({'phase': 'API_REQUEST', 'request_ref': self.request_ref,
                'method': method if method in ('GET', 'POST') else 'OTHER',
                'route': 'AUTOMATIC_RESULT' if re.fullmatch(
                    '/v1/audits/(' + REF + ')/diagnosis', self.path) else 'OTHER',
                'http_status': self.response_status, 'code': self.response_code,
                'duration_ms': round((monotonic() - started) * 1000),
                'recorded_at': datetime.now(UTC).isoformat()}), flush=True)

    def send(self, status, body, extra=()):
        self.response_status = status
        code = body.get('code') if isinstance(body, dict) else None
        self.response_code = code if code in ('ACCESS_DENIED', 'CONFLICT', 'RATE_LIMITED', 'UNAVAILABLE') else None
        headers = [*extra, ("X-VRAE-API-Version", "vrae.diagnosis-api.v1")]
        if getattr(self, 'request_ref', None):
            headers.append(('X-VRAE-Request-Ref', self.request_ref))
        return super().send(status, body, headers)

    def send_api(self, status, body):
        self.response_status = status
        raw = canonical(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-VRAE-API-Version", "vrae.diagnosis-api.v1")
        self.send_header("X-VRAE-Source-SHA", self.server.source_sha)
        self.send_header("X-Content-Type-Options", "nosniff")
        if getattr(self, 'request_ref', None):
            self.send_header('X-VRAE-Request-Ref', self.request_ref)
        self.end_headers()
        self.wfile.write(raw)

    def route_target(self, method):
        cfg = self.server.cfg
        for name in (
            "Host",
            "Origin",
            "Authorization",
            "Accept",
            "Content-Type",
            "Cookie",
            "X-CSRF-Token",
        ):
            if len(self.headers.get_all(name, [])) > 1:
                raise Refused("FORBIDDEN_ROLE")
        from integration.authorized_targets.transport import check_headers, bind_peer

        transport = check_headers(self, cfg)
        if method == "GET" and self.path == "/health/live":
            return self.send_api(
                200,
                {
                    "api_version": "vrae.diagnosis-api.v1",
                    "status": "LIVE",
                    "source_sha": self.server.source_sha,
                },
            )
        api_json = self.path in ("/health/ready", "/v1/errors", "/v1/openapi.json", "/v1/target-intake-contract")
        if self.headers.get("Accept") != ("application/json" if api_json else MEDIA):
            raise TransportError(406)
        if method == "POST" and self.headers.get("Content-Type") != MEDIA:
            raise TransportError(415)
        binding = service_binding(self.headers.get("Authorization"), cfg["bindings"])
        bind_peer(self, binding, transport)
        tenant = binding["tenant_id"]
        if method == "GET" and api_json:
            from integration.authorized_targets.api_contract import (
                VERSION as API,
                ERRORS,
                error,
                openapi,
            )

            if self.path == "/health/ready":
                try:
                    ready = store.invoke(binding, "readiness", tenant)
                except (psycopg.Error, Refused, OSError):
                    return self.send_api(503, error("UNAVAILABLE"))
                return self.send_api(
                    200,
                    {
                        "api_version": API,
                        "status": "READY" if ready else "UNAVAILABLE",
                        "source_sha": self.server.source_sha,
                    },
                )
            if self.path == "/v1/errors":
                return self.send_api(
                    200, {"api_version": API, "errors": [error(code)["error"] for code in ERRORS]}
                )
            if self.path == "/v1/target-intake-contract":
                if cfg.get("target_intake_enabled") is not True:
                    raise Refused("SOURCE_NOT_ALLOWED")
                from infra.windows_service.intake import contract
                return self.send_api(200, contract())
            document = openapi()
            if cfg.get("target_intake_enabled"):
                from infra.windows_service.intake import contract
                intake = contract()
                document["servers"] = [{"url":"https://" + cfg["transport"]["hosts"][0]}]
                document["x-vrae-target-intake"] = intake
                for item in ("application", "authorization", "diagnosis"):
                    operation = intake[item]
                    document["paths"][operation["path"]] = {"post":{
                        "summary":item,"requestBody":{"required":True,"description":str(operation["body"])},
                        "responses":{"201":{"description":"Scoped target context"},"202":{"description":"Original queue committed"},
                                     "403":{"description":"Denied"},"409":{"description":"Changed intent"},
                                     "429":{"description":"Bounded capacity or active capture"},"503":{"description":"Unavailable"}}}}
            return self.send_api(200, document)
        if "?" in self.path or "%" in self.path or len(self.path) > 256:
            raise Refused("FORBIDDEN_ROLE")
        if method == "POST" and self.path == "/v1/internal/committed-input":
            if binding.get("port") != "REVIEW":
                raise Refused("FORBIDDEN_ROLE")
            body = self.body()
            if set(body) != {"job_id"}:
                raise Refused("FORBIDDEN_ROLE")
            from uuid import UUID
            from integration.authorized_targets.delivery import committed_input

            job = str(UUID(body["job_id"]))
            with committed_input(binding, job, purpose="HUMAN_REVIEW_INPUT") as current:
                return self.send(200, current)
        if method == "POST" and self.path in ("/v1/invitation-session", "/v1/return-sessions", "/v1/diagnosis-sessions"):
            body = self.body()
            cookie, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            automatic = self.path == '/v1/diagnosis-sessions'
            if automatic:
                if not automatic_session_allowed(cfg, binding, transport) or body != {}:
                    raise Refused('FORBIDDEN_ROLE')
                result = store.invoke(binding, 'automatic_session', tenant, token_hash(cookie), token_hash(csrf))
            else:
                key = "invitation_token" if self.path == "/v1/invitation-session" else "return_token"
                if set(body) != {key} or type(body[key]) is not str:
                    raise Refused("FORBIDDEN_ROLE")
                result = store.invoke(binding, "exchange" if key == "invitation_token" else "exchange_return",
                    tenant, token_hash(body[key]), token_hash(cookie), token_hash(csrf))
            age = max(
                1,
                int(
                    (
                        datetime.fromisoformat(result["expires_at"]) - datetime.now(UTC)
                    ).total_seconds()
                ),
            )
            return self.send(
                200,
                {"created": True} if automatic else {"restored": True},
                [
                    (
                        "Set-Cookie",
                        COOKIE
                        + "="
                        + cookie
                        + "; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age="
                        + str(age),
                    ),
                    ("X-CSRF-Token", csrf),
                ],
            )
        cookies = SimpleCookie()
        cookies.load(self.headers.get("Cookie", ""))
        if COOKIE not in cookies or not self.headers.get("X-CSRF-Token"):
            raise Refused("FORBIDDEN_ROLE")
        cookie, csrf = token_hash(cookies[COOKIE].value), token_hash(self.headers["X-CSRF-Token"])
        if method == "POST" and self.path in ("/v1/target-applications", "/v1/target-applications/authorize"):
            if cfg.get("target_intake_enabled") is not True:
                raise Refused("SOURCE_NOT_ALLOWED")
            from infra.windows_service.intake import rpc
            result = rpc("authorize" if self.path.endswith("/authorize") else "challenge",
                         binding["role"], cookie, csrf, self.body())
            return self.send(result["status"], result["data"])
        source = re.fullmatch("/v1/source-plans/([A-Za-z0-9][A-Za-z0-9_.-]{2,127})", self.path)
        if method == "GET" and source:
            resolved = store.invoke(binding, "source_context", tenant, cookie, csrf, source[1])
            plan = resolved["plan"]
            if plan.get("execution_profile") == "ADMIN_TARGET_V2":
                from integration.authorized_targets.source_authority import authorization

                authorization(
                    resolved["source_authorization"], plan, plan_sha256=resolved["plan_sha256"]
                )
            return self.send(
                200,
                {
                    "contract": "vrae.authorized-source-context.v1",
                    "tenant_id": tenant,
                    "subject_ref": resolved["actor"]["subject_ref"],
                    "invitation_ref": resolved["actor"]["invitation_ref"],
                    "target_id": source[1],
                    "site_url": plan["origin"] + "/",
                    "source_policy": plan["policy"],
                    "audit_modes": ["L0", "L1"],
                    "diagnostic_depth": "L2",
                },
            )
        recovery = re.fullmatch("/v1/audits/(" + REF + ")/return-tokens", self.path)
        if method == "POST" and recovery:
            body = self.body()
            if not set(body) <= {"ttl_seconds"}:
                raise Refused("FORBIDDEN_ROLE")
            ttl = body.get("ttl_seconds", 300)
            if type(ttl) is not int or not 1 <= ttl <= 900:
                raise Refused("FORBIDDEN_ROLE")
            token = secrets.token_urlsafe(32)
            result = store.invoke(
                binding, "make_return", tenant, cookie, csrf, recovery[1], token_hash(token), ttl
            )
            return self.send(
                201, {"contract": "vrae.task-return-token.v1", **result, "return_token": token}
            )
        if method == "POST" and self.path in ("/v1/audit-requests", "/v1/diagnoses"):
            body = self.body()
            if self.path == "/v1/diagnoses":
                if cfg.get("target_intake_enabled") is not True:
                    raise Refused("SOURCE_NOT_ALLOWED")
                from infra.windows_service.intake import rpc
                result = rpc("automatic_submission" if "authorized" in body else "submission",
                             binding["role"], cookie, csrf, body)
                if result["status"] != 200:
                    return self.send(result["status"], result["data"])
                body = result["data"]
            validate("VFSubmit", body)
            resolved = store.invoke(
                binding, "submission_plan", tenant, cookie, csrf, body["command"]["request"]["site_url"],
                body["command"]["request"]["source_policy_ref"]
            )
            if resolved["plan"].get("execution_profile") == "ADMIN_TARGET_V2":
                from integration.authorized_targets.source_authority import authorization

                authorization(
                    resolved["source_authorization"],
                    resolved["plan"],
                    plan_sha256=resolved["plan_sha256"],
                )
            actor = {**resolved["actor"], "tenant_id": tenant}
            inv = actor["invitation"]
            plan = resolved["plan"]
            intent = check_submission(body, plan, inv, actor, binding["verification_keys"])
            receipt = store.invoke(
                binding, "admit", tenant, cookie, csrf, intent, canonical(body).decode()
            )
            accepted = {
                "contract_version": VERSION,
                "audit_ref": receipt["audit_ref"],
                "run_id": receipt["run_id"],
                "run_status": "CREATED",
                "diagnosis_complete": False,
                "poll_after_seconds": 10,
            }
            validate("VFAccepted", accepted)
            return self.send(202, accepted)
        diagnosis = re.fullmatch('/v1/audits/(' + REF + ')/diagnosis', self.path)
        if method == 'GET' and diagnosis:
            from integration.authorized_targets.automatic_result import current
            with current(binding, cookie, csrf, diagnosis[1]) as (code, document):
                return self.send(code, document)
        match = re.fullmatch(
            "/v1/audits/(" + REF + ")(?:/(report|review-decisions|sales-handoffs))?", self.path
        )
        if match:
            native = store.invoke(binding, "status", tenant, cookie, csrf, match[1])
            if method != "GET" or match[2] is not None:
                raise Refused("REPORT_NOT_APPROVED")
            status = {
                "PENDING": "QUEUED",
                "LEASED": "FETCHING",
                "DRAFT_READY": "DRAFT_READY",
                "DEAD_LETTER": "FAILED",
            }[native["state"]]
            run = {
                "schema_version": "1.0",
                "tenant_id": tenant,
                "run_id": native["run_id"],
                "audit_id": native["request_id"],
                "request_id": native["request_id"],
                "status": status,
                "attempt": native["attempts"],
                "input_hash": native["input_hash"],
                "rule_version": "ra2b6-1.0.0",
                "started_at": None,
                "finished_at": None,
                "error_code": None,
            }
            return self.send(
                200,
                vf_status(
                    match[1],
                    run,
                    datetime.now(UTC),
                    publication="UNPUBLISHED",
                    access=native.get("access_state", "ACTIVE"),
                ),
            )
        raise TransportError(404)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = store.config(args.config, "APP")
    from integration.authorized_targets.transport import endpoint

    ep = endpoint(cfg)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(cfg["certificate"], cfg["certificate_key"])
    if ep["mtls"]:
        tls.load_verify_locations(cafile=ep["client_ca"])
        tls.verify_mode = ssl.CERT_REQUIRED
    server = BoundedServer((ep["bind"], ep["port"]), Handler, tls)
    server.cfg = cfg
    server.source_sha = cfg["source_sha"]
    print('{"stage":"AUTHORIZED_TARGET_HTTPS_READY","port":8769}', flush=True)
    server.serve_forever(poll_interval=0.1)


if __name__ == "__main__":
    main()
