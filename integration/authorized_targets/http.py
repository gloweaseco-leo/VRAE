"""Tenant/subject-bound BFF boundary. Draft status is separate from report release."""

import argparse
from datetime import datetime, UTC
import re
import secrets
import ssl
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


class Handler(StrictHandler):
    def dispatch(self, method):
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
        except OSError:
            self.close_connection = True
            self.send(503, safe_error(Refused("R0_STORAGE_UNAVAILABLE", 503, True)))

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
        if (
            self.headers.get("Host") != "127.0.0.1:8769"
            or self.headers.get("Origin") != "https://127.0.0.1:8769"
        ):
            raise Refused("FORBIDDEN_ROLE")
        if self.headers.get("Accept") != MEDIA:
            raise TransportError(406)
        if method == "POST" and self.headers.get("Content-Type") != MEDIA:
            raise TransportError(415)
        binding = service_binding(self.headers.get("Authorization"), cfg["bindings"])
        tenant = binding["tenant_id"]
        if "?" in self.path or "%" in self.path or len(self.path) > 256:
            raise Refused("FORBIDDEN_ROLE")
        if method == "POST" and self.path == "/v1/invitation-session":
            body = self.body()
            if set(body) != {"invitation_token"} or type(body["invitation_token"]) is not str:
                raise Refused("FORBIDDEN_ROLE")
            cookie, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            result = store.invoke(
                binding,
                "exchange",
                tenant,
                token_hash(body["invitation_token"]),
                token_hash(cookie),
                token_hash(csrf),
            )
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
                {"restored": True},
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
        if method == "POST" and self.path == "/v1/audit-requests":
            body = self.body()
            validate("VFSubmit", body)
            resolved = store.invoke(
                binding, "plan", tenant, cookie, csrf, body["command"]["request"]["site_url"]
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
                200, vf_status(match[1], run, datetime.now(UTC), publication="UNPUBLISHED")
            )
        raise TransportError(404)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = store.config(args.config, "APP")
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(cfg["certificate"], cfg["certificate_key"])
    server = BoundedServer(("127.0.0.1", 8769), Handler, tls)
    server.cfg = cfg
    server.source_sha = cfg["source_sha"]
    print('{"stage":"AUTHORIZED_TARGET_HTTPS_READY","port":8769}', flush=True)
    server.serve_forever(poll_interval=0.1)


if __name__ == "__main__":
    main()
