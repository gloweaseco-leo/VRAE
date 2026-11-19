"""Versioned trusted report/review API over the existing PG source and L2 ledger.

NativeSource remains CONTROLLED-only. An authenticated service is neither a
responsible person nor a report recipient. No customer/formal release is added.
"""

import argparse
import hashlib
import re
import sqlite3
import ssl
from pathlib import Path
from threading import BoundedSemaphore
from uuid import UUID

import psycopg
from contracts.l2_launch.contract import Refused, canonical
from contracts.l2_launch.vf_b import HEADERS, safe_error
from integration.authorized_targets.authority import service_binding
from integration.authorized_targets.review import current_committed_review
from integration.authorized_targets import store
from integration.l2_launch.g1.http_server import (
    Handler as StrictHandler,
    BoundedServer,
    TransportError,
)
from vrae.l2.identity import Directory, Person
from vrae.l2.report import L2Denied
from vrae.l2.verified import PROFILE as VERIFIED_PROFILE
from integration.authorized_targets.transport import endpoint, check_headers, bind_peer

PROFILE = "vrae.report-authority.v1"
MEDIA = 'application/vnd.vrae.report+json; profile="' + PROFILE + '"'
BASE = "/v1/report-authority"
OPERATIONS = {"decisions", "revisions", "grants", "revocations"}


class Application:
    def __init__(self, cfg):
        self.cfg = cfg
        self.origin = "https://127.0.0.1:8770"
        self.profile = cfg.get("report_profile", "CONTROLLED_NATIVE_REPORT_ONLY")
        if self.profile not in ("CONTROLLED_NATIVE_REPORT_ONLY", VERIFIED_PROFILE):
            raise ValueError("REPORT_PROFILE_REQUIRED")
        self.verified = self.profile == VERIFIED_PROFILE
        self.authority = None
        self.transport = None
        capacity = cfg.get("max_inflight", 4)
        if type(capacity) is not int or not 1 <= capacity <= 8:
            raise ValueError("REPORT_CAPACITY_REQUIRED")
        self.slots = BoundedSemaphore(capacity)
        if self.verified:
            from integration.authorized_targets.report_authority import Authority

            self.authority = Authority()
            self.transport = endpoint(cfg)
            if not self.transport["mtls"]:
                raise ValueError("VERIFIED_REPORT_MTLS_REQUIRED")
            d = self.authority.document["directory"]
        else:
            d = cfg["report_directory"]
        if not self.verified and d["mode"] != "CONTROLLED":
            raise ValueError("NATIVE_CONTROLLED_PROFILE_REQUIRED")
        people = [Person(**{**p, "report_ids": tuple(p["report_ids"])}) for p in d["people"]]
        self.directory = Directory(
            **{k: d[k] for k in ("issuer", "audience", "jwks", "expires", "mode")},
            people=people,
            report_authorizer=self.authority.permits if self.verified else None,
        )
        self.root = Path(cfg["ledger_root"])
        if not self.root.is_absolute() or self.root.is_symlink():
            raise ValueError("PRIVATE_LEDGER_ROOT_REQUIRED")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        s = self.root.stat()
        import os

        if s.st_uid != os.geteuid() or s.st_mode & 0o077:
            raise ValueError("PRIVATE_LEDGER_ROOT_REQUIRED")

    def binding(self, headers):
        b = service_binding(headers.get("Authorization"), self.cfg["bindings"])
        if b.get("port") != "REVIEW":
            raise Refused("FORBIDDEN_ROLE")
        return b

    def person(self, sid, binding, report=None):
        p = self.directory.require(sid, report).person
        if p.tenant_id != binding["tenant_id"]:
            raise Refused("FORBIDDEN_ROLE")
        return p

    def operate(self, binding, sid, job, operation, body, headers):
        # Lock spans the original ledger call AND the caller's actual HTTP send.
        # Serialize Directory revocation against a response currently being sent.
        from contextlib import contextmanager

        @contextmanager
        def held():
            with self.directory.lock:
                self.person(sid, binding)
                path = self.root / (binding["tenant_id"] + "-" + job + ".sqlite")
                current = self.authority.current if self.verified else current_committed_review
                with current(binding, job, path, self.directory) as (ledger, rid):
                    person = self.person(sid, binding, rid)
                    if operation == "report" and person.role == "READER":
                        token = headers.get("X-Report-Token", "")
                        if not 32 <= len(token) <= 128:
                            raise Refused("FORBIDDEN_ROLE")
                        view = ledger.access(
                            sid,
                            rid,
                            headers.get("X-Report-Grant", ""),
                            hashlib.sha256(token.encode()).hexdigest(),
                        )
                    else:
                        # Establish role/scope before action tokens or history.
                        view = ledger.read(sid, rid)
                    if headers.get("If-Match") not in (None, '"' + view.display_hash + '"'):
                        raise Refused("REPORT_VERSION_STALE", 409)
                    if operation == "report":
                        released = self.verified and person.role == "READER"
                        approved = view.version
                        review = None
                        if released:
                            with ledger.connection() as c:
                                receipt, approved = ledger._decision(c, person, rid, view)
                            review = receipt["decision"]
                        result = {
                            "contract": PROFILE,
                            "report": view.document,
                            "report_version": approved,
                            "display_hash": view.display_hash,
                            "formal_human_review": released,
                            "external_release": released,
                            "scope": self.profile,
                        }
                        if released:
                            result["review_decision"] = review
                    elif operation == "history":
                        versions, decisions, grants = ledger.history(sid, rid)
                        result = {
                            "contract": PROFILE,
                            "versions": versions,
                            "decisions": decisions,
                            "grants": grants,
                        }
                    elif operation == "actions":
                        if (
                            type(body) is not dict
                            or set(body) != {"operation"}
                            or body["operation"] not in OPERATIONS
                        ):
                            raise Refused("FORBIDDEN_ROLE")
                        target = BASE + "/jobs/" + job + "/" + body["operation"]
                        result = {
                            "contract": PROFILE,
                            "action_token": self.directory.action(sid, target),
                        }
                    else:
                        if headers.get("If-Match") is None:
                            raise Refused("REPORT_VERSION_STALE", 409)
                        if type(body) is not dict:
                            raise Refused("FORBIDDEN_ROLE")
                        self.directory.consume(
                            sid,
                            BASE + "/jobs/" + job + "/" + operation,
                            headers.get("X-Report-Action"),
                        )
                        pins = {
                            "version": view.version["version"],
                            "content_hash": view.version["content_hash"],
                            "display_hash": view.display_hash,
                        }
                        if operation == "decisions" and set(body) == {
                            "action",
                            "reason",
                            "items",
                            "attest",
                        }:
                            result = {
                                "contract": PROFILE,
                                "receipt": ledger.review(sid, rid, **pins, **body),
                            }
                        elif operation == "revisions" and set(body) == {"changes"}:
                            revised = ledger.revise(sid, rid, **pins, changes=body["changes"])
                            result = {
                                "contract": PROFILE,
                                "report_version": revised.version,
                                "display_hash": revised.display_hash,
                                "review_required": True,
                                "external_release": False,
                            }
                        elif operation == "grants" and set(body) == {"recipient_id", "ttl"}:
                            grant, token = ledger.issue(sid, rid, **pins, **body)
                            result = {
                                "contract": PROFILE,
                                "grant": grant,
                                "access_token": token,
                                "external_release": self.verified,
                            }
                        elif operation == "revocations" and set(body) == {"grant_id"}:
                            result = {
                                "contract": PROFILE,
                                "grant": ledger.revoke(sid, rid, body["grant_id"]),
                            }
                        else:
                            raise Refused("FORBIDDEN_ROLE")
                    self.person(sid, binding, rid)
                    yield result
                    self.person(sid, binding, rid)

        return held()


class Handler(StrictHandler):
    @property
    def app(self):
        return self.server.report_app

    def send(self, status, body, extra=()):
        raw = canonical(body)
        self.send_response_only(status)
        self.send_header("Content-Type", MEDIA)
        self.send_header("Content-Length", str(len(raw)))
        for key, value in HEADERS.items():
            self.send_header(key, value)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-VRAE-Source-SHA", self.server.source_sha)
        self.send_header("X-VRAE-Scope", self.app.profile)
        for key, value in extra:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()

    def dispatch(self, method):
        if not self.app.slots.acquire(blocking=False):
            return self.send(429, safe_error(Refused("QUOTA_EXCEEDED", 429, True)))
        try:
            self.route_report(method)
        except TransportError as e:
            self.close_connection = True
            self.send(e.status, {"contract": PROFILE, "transport_error": e.status})
        except Refused as e:
            self.close_connection = True
            self.send(e.status, safe_error(e))
        except L2Denied as e:
            self.close_connection = True
            stale = str(e) in ("L2_STALE_VERSION", "L2_STALE_GRANT")
            self.send(
                409 if stale else 403,
                safe_error(
                    Refused("REPORT_VERSION_STALE", 409) if stale else Refused("FORBIDDEN_ROLE")
                ),
            )
        except PermissionError:
            self.close_connection = True
            self.send(403, safe_error(Refused("FORBIDDEN_ROLE")))
        except (
            psycopg.OperationalError,
            psycopg.errors.LockNotAvailable,
            psycopg.errors.QueryCanceled,
            sqlite3.Error,
            OSError,
        ):
            self.close_connection = True
            self.send(503, safe_error(Refused("R0_STORAGE_UNAVAILABLE", 503, True)))
        except (psycopg.Error, ValueError, TypeError, KeyError):
            self.close_connection = True
            self.send(403, safe_error(Refused("FORBIDDEN_ROLE")))
        finally:
            self.app.slots.release()

    def route_report(self, method):
        for name in (
            "Host",
            "Origin",
            "Authorization",
            "Accept",
            "Content-Type",
            "Cookie",
            "X-Report-Session",
            "If-Match",
            "X-Report-Action",
            "X-Report-Grant",
            "X-Report-Token",
            "X-Report-Profile",
        ):
            if len(self.headers.get_all(name, [])) > 1:
                raise Refused("FORBIDDEN_ROLE")
        requested_profile = self.headers.get("X-Report-Profile")
        if (
            self.app.verified or requested_profile is not None
        ) and requested_profile != self.app.profile:
            raise TransportError(406)
        if self.app.verified:
            if self.headers.get("Cookie"):
                raise Refused("FORBIDDEN_ROLE")
            self.app.authority.check()
            check_headers(self, self.app.cfg)
        elif (
            self.headers.get("Host") != "127.0.0.1:8770"
            or self.headers.get("Origin") != self.app.origin
            or self.headers.get("Cookie")
        ):
            raise Refused("FORBIDDEN_ROLE")
        if self.headers.get("Accept") != MEDIA:
            raise TransportError(406)
        if method == "POST" and self.headers.get("Content-Type") != MEDIA:
            raise TransportError(415)
        binding = self.app.binding(self.headers)
        if self.app.verified:
            bind_peer(self, binding, self.app.transport)
        if method == "GET" and self.path == BASE + "/health":
            with store.connect(binding) as c:
                c.execute("SELECT 1").fetchone()
                if (
                    self.app.verified
                    and not c.execute(
                        "SELECT to_regprocedure('target_v1.report_context(text,uuid)') IS NOT NULL"
                    ).fetchone()[0]
                ):
                    raise Refused("R0_STORAGE_UNAVAILABLE", 503, True)
            return self.send(
                200, {"contract": PROFILE, "ready": True, "customer_release": self.app.verified}
            )
        if method == "POST" and self.path == BASE + "/challenge":
            if self.body() != {}:
                raise Refused("FORBIDDEN_ROLE")
            nonce, csrf = self.app.directory.challenge()
            return self.send(200, {"contract": PROFILE, "nonce": nonce, "csrf": csrf})
        if method == "POST" and self.path == BASE + "/session":
            body = self.body()
            if type(body) is not dict or set(body) != {"responsible_bearer", "nonce", "csrf"}:
                raise Refused("FORBIDDEN_ROLE")
            sid = self.app.directory.login(body["responsible_bearer"], body["nonce"], body["csrf"])
            self.app.person(sid, binding)
            return self.send(200, {"contract": PROFILE, "report_session": sid})
        match = re.fullmatch(
            BASE
            + r"/jobs/([0-9a-f-]{36})/(report|history|actions|decisions|revisions|grants|revocations)",
            self.path,
        )
        if not match:
            raise TransportError(404)
        job, operation = match.groups()
        if str(UUID(job)) != job:
            raise Refused("FORBIDDEN_ROLE")
        if method != ("GET" if operation in ("report", "history") else "POST"):
            raise TransportError(405)
        body = self.body() if method == "POST" else None
        with self.app.operate(
            binding, self.headers.get("X-Report-Session"), job, operation, body, self.headers
        ) as result:
            extra = (
                [("ETag", '"' + result["display_hash"] + '"')] if "display_hash" in result else []
            )
            return self.send(200, result, extra)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = store.config(args.config, "APP")
    app = Application(cfg)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(cfg["certificate"], cfg["certificate_key"])
    address = ("127.0.0.1", 8770)
    if app.verified:
        tls.verify_mode = ssl.CERT_REQUIRED
        tls.load_verify_locations(cafile=app.transport["client_ca"])
        address = (app.transport["bind"], app.transport["port"])
    server = BoundedServer(address, Handler, tls)
    server.report_app = app
    server.source_sha = cfg["source_sha"]
    import json

    print(json.dumps({"stage": "REPORT_AUTHORITY_HTTPS_READY", "profile": app.profile}), flush=True)
    server.serve_forever(poll_interval=0.1)


if __name__ == "__main__":
    main()
