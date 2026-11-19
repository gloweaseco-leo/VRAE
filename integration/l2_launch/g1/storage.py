"""Transport receipts in original PG; original TaskClient owns every task fact."""

from dataclasses import asdict
from datetime import datetime, UTC, timedelta
import hashlib
import hmac
import secrets
from urllib.parse import urlsplit

import psycopg
from psycopg.types.json import Jsonb
from contracts.l2_launch.contract import Refused, check_permission, digest, validate
from contracts.l2_launch.vf_b import VERSION, submission_document
from vrae.application.ra4b_p2.m1.consumer import TaskHandle
from integration.l2_launch.g1.bootstrap import hydrate
from integration.l2_launch.g1.fixture_keys import verifier

REALM_LOCK = 913450761234


class TransportStore:
    def __init__(self, cfg, client):
        self.cfg, self.client = cfg, client
        with self.connect() as c:
            rows = c.execute(
                "SELECT document FROM g1_http.sourceplans ORDER BY source_ref"
            ).fetchall()
        self.plans = {v.ref: v for v in (hydrate(row[0]) for row in rows)}

    def connect(self):
        cfg = self.cfg
        if (
            cfg["tenant"] != "tenant-test"
            or cfg["meta_role"] != "g1_http_a"
            or cfg["mode"] != "OFFLINE_SYNTHETIC"
        ):
            raise Refused("FORBIDDEN_ROLE")
        c = psycopg.connect(
            host="127.0.0.1",
            port=5432,
            dbname="vrae_ra4a_p1",
            user=cfg["meta_role"],
            password=cfg["meta_password"],
            autocommit=True,
            connect_timeout=2,
            options="-c statement_timeout=2000 -c lock_timeout=1500",
        )
        row = c.execute(
            "SELECT session_user,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=session_user"
        ).fetchone()
        if row != (cfg["meta_role"], False, False, False, False):
            c.close()
            raise Refused("FORBIDDEN_ROLE")
        return c

    def realm(self, c):
        row = c.execute("SELECT value FROM g1_http.settings WHERE key='realm'").fetchone()
        if row is None:
            raise Refused("FORBIDDEN_ROLE")
        value = row[0]
        if (
            value["epoch"] != self.cfg["epoch"]
            or value["service_hash"]
            != hashlib.sha256(self.cfg["service_token"].encode()).hexdigest()
        ):
            raise Refused("FORBIDDEN_ROLE")
        if datetime.now(UTC).timestamp() >= value["controller_expires"]:
            raise Refused("FORBIDDEN_ROLE")
        return value

    def source_for(self, submission):
        url = submission["command"]["request"]["site_url"]
        found = [plan for plan in self.plans.values() if plan.audit["site_url"] == url]
        if len(found) != 1:
            raise Refused("SOURCE_NOT_ALLOWED")
        return found[0]

    def verify_submission(self, c, body):
        validate("VFSubmit", body)
        realm = self.realm(c)
        plan = self.source_for(body)
        if body["command"]["request"]["audit_mode"] != "L1":
            raise Refused("SOURCE_NOT_ALLOWED")
        caller = {
            "tenant_id": self.cfg["tenant"],
            "actor_id": "g1-vf-server-fixture",
            "role": "SERVICE",
        }
        now = datetime.now(UTC)
        check_permission(body["command"], plan.policy, caller, verifier(realm["keys"]), now)
        found = c.execute(
            "SELECT document FROM g1_http.invitations WHERE reference=%s", (body["invitation_ref"],)
        ).fetchone()
        invitation = found[0] if found else None
        consent = body["diagnosis_consent"]
        permission = body["command"]["permission_reference"]
        if (
            not invitation
            or invitation["revoked"]
            or invitation["tenant_id"] != self.cfg["tenant"]
            or invitation["subject_ref"] != body["subject_ref"]
            or invitation["policy_sha256"] != digest(plan.policy)
            or datetime.fromisoformat(invitation["expires_at"]) <= now
            or body["normalized_host"] != urlsplit(plan.audit["site_url"]).hostname
            or consent["consent_version"] != permission["consent_version"]
            or consent["text_sha256"] != permission["consent_sha256"]
            or not datetime.fromisoformat(plan.policy["created_at"])
            <= datetime.fromisoformat(consent["accepted_at"])
            <= now
            or invitation["request_sha256"] != digest(body["command"]["request"])
        ):
            raise Refused("POLICY_REQUIRED")
        verifier(realm["keys"]).verify(
            body["submission_proof"],
            "permission",
            submission_document(body),
            self.cfg["tenant"],
            now,
        )
        return plan, invitation

    @staticmethod
    def record(row):
        if row is None:
            raise Refused("FORBIDDEN_ROLE")
        names = (
            "tenant",
            "idem",
            "intent_hash",
            "audit_ref",
            "source_ref",
            "subject_ref",
            "submission",
            "native_task",
            "created_at",
        )
        return dict(zip(names, row))

    def lookup(self, c, ref):
        return self.record(
            c.execute(
                "SELECT tenant,idem,intent_hash,audit_ref,source_ref,subject_ref,submission,native_task,created_at FROM g1_http.admissions WHERE audit_ref=%s AND tenant=%s",
                (ref, self.cfg["tenant"]),
            ).fetchone()
        )

    def task(self, record):
        if not record["native_task"]:
            raise Refused("R0_STORAGE_UNAVAILABLE", 503, True)
        return TaskHandle(**record["native_task"])

    def submit(self, body):
        tenant = self.cfg["tenant"]
        intent = digest(body)
        with self.connect() as c, c.transaction():
            c.execute("SELECT pg_advisory_xact_lock_shared(%s)", (REALM_LOCK,))
            plan, _ = self.verify_submission(c, body)
            idem = body["command"]["request"]["idempotency_key"]
            lock = int.from_bytes(hashlib.sha256(tenant.encode()).digest()[:8], "big", signed=True)
            c.execute("SELECT pg_advisory_xact_lock(%s)", (lock,))
            old = c.execute(
                "SELECT tenant,idem,intent_hash,audit_ref,source_ref,subject_ref,submission,native_task,created_at FROM g1_http.admissions WHERE tenant=%s AND idem=%s",
                (tenant, idem),
            ).fetchone()
            if old:
                record = self.record(old)
                if record["intent_hash"] != intent:
                    raise Refused("IDEMPOTENCY_CONFLICT", 409)
            else:
                # A per-source bound, checked against ORIGINAL current queue facts.
                active = c.execute(
                    "SELECT tenant,idem,intent_hash,audit_ref,source_ref,subject_ref,submission,native_task,created_at FROM g1_http.admissions WHERE tenant=%s AND source_ref=%s",
                    (tenant, plan.ref),
                ).fetchall()
                for row in active:
                    prior = self.record(row)
                    if not prior["native_task"] or self.client.status(self.task(prior))[
                        "job_state"
                    ] in ("PENDING", "LEASED"):
                        raise Refused("QUOTA_EXCEEDED", 429, True)
                request = body["command"]["request"]
                seen = c.execute(
                    "SELECT 1 FROM g1_http.admissions WHERE tenant=%s AND (submission->'command'->'request'->>'request_id'=%s OR submission->'command'->'request'->>'audit_id'=%s)",
                    (tenant, request["request_id"], request["audit_id"]),
                ).fetchone()
                if seen:
                    raise Refused("IDEMPOTENCY_CONFLICT", 409)
                ref = "aref-" + secrets.token_hex(16)
                c.execute(
                    "INSERT INTO g1_http.admissions(tenant,idem,intent_hash,audit_ref,source_ref,subject_ref,submission) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                    (tenant, idem, intent, ref, plan.ref, body["subject_ref"], Jsonb(body)),
                )
                record = self.lookup(c, ref)
        # The immutable intent is already committed; a lost APP response cannot
        # erase it. The sole original PG admission is retried with the SAME key.
        internal = (
            "g1-"
            + hmac.new(
                self.cfg["routing_key"].encode(), (tenant + ":" + idem).encode(), hashlib.sha256
            ).hexdigest()
        )
        task = self.client.create(plan.ref, idempotency_key=internal)
        with self.connect() as c, c.transaction():
            self.verify_submission(c, body)
            c.execute(
                "UPDATE g1_http.admissions SET native_task=%s WHERE tenant=%s AND idem=%s",
                (Jsonb(asdict(task)), tenant, idem),
            )
            record = self.lookup(c, record["audit_ref"])
        # Original status revalidates current PG authority after both COMMITs.
        self.client.status(task)
        body = {
            "contract_version": VERSION,
            "audit_ref": record["audit_ref"],
            "run_id": self.public_run(task),
            "run_status": "CREATED",
            "diagnosis_complete": False,
            "poll_after_seconds": 10,
        }
        validate("VFAccepted", body)
        return body

    def public_run(self, task):
        return task.run_id

    def current_record(self, c, ref):
        record = self.lookup(c, ref)
        self.verify_submission(c, record["submission"])
        self.client.status(self.task(record))
        return record

    def install_return(self, ref, grant, proof):
        with self.connect() as c, c.transaction():
            record = self.current_record(c, ref)
            realm = self.realm(c)
            validate("VFReturnGrant", grant)
            verifier(realm["keys"]).verify(
                proof, "share", grant, self.cfg["tenant"], datetime.now(UTC)
            )
            plan = self.plans[record["source_ref"]]
            if (
                grant["audit_ref"] != ref
                or grant["subject_ref"] != record["subject_ref"]
                or grant["policy_sha256"] != digest(plan.policy)
                or grant["revoked"]
            ):
                raise Refused("FORBIDDEN_ROLE")
            c.execute(
                "INSERT INTO g1_http.return_grants(tenant,audit_ref,document,proof) VALUES(%s,%s,%s,%s)",
                (self.cfg["tenant"], ref, Jsonb(grant), Jsonb(proof)),
            )

    def challenge(self):
        cookie = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        with self.connect() as c:
            self.realm(c)
            c.execute(
                "INSERT INTO g1_http.challenges VALUES(%s,%s,%s,%s,false)",
                (
                    self.cfg["tenant"],
                    hashlib.sha256(cookie.encode()).hexdigest(),
                    hashlib.sha256(csrf.encode()).hexdigest(),
                    datetime.now(UTC) + timedelta(seconds=60),
                ),
            )
        return cookie, csrf

    def csrf_for(self, cookie):
        return hmac.new(
            self.cfg["routing_key"].encode(), ("csrf:" + cookie).encode(), hashlib.sha256
        ).hexdigest()

    def exchange(self, ref, token, challenge_cookie, challenge_csrf):
        if type(token) is not str or not 32 <= len(token) <= 256:
            raise Refused("FORBIDDEN_ROLE")
        with self.connect() as c, c.transaction():
            record = self.current_record(c, ref)
            realm = self.realm(c)
            if type(challenge_cookie) is not str or type(challenge_csrf) is not str:
                raise Refused("FORBIDDEN_ROLE")
            challenged = c.execute(
                "SELECT csrf_hash,expires_at,used FROM g1_http.challenges WHERE hash=%s FOR UPDATE",
                (hashlib.sha256(challenge_cookie.encode()).hexdigest(),),
            ).fetchone()
            if (
                not challenged
                or challenged[2]
                or challenged[1] <= datetime.now(UTC)
                or not hmac.compare_digest(
                    challenged[0], hashlib.sha256(challenge_csrf.encode()).hexdigest()
                )
            ):
                raise Refused("FORBIDDEN_ROLE")
            row = c.execute(
                "SELECT document,proof,used_at,revoked FROM g1_http.return_grants WHERE audit_ref=%s FOR UPDATE",
                (ref,),
            ).fetchone()
            if not row:
                raise Refused("FORBIDDEN_ROLE")
            grant, proof, used, revoked = row
            verifier(realm["keys"]).verify(
                proof, "share", grant, self.cfg["tenant"], datetime.now(UTC)
            )
            if (
                used
                or revoked
                or grant["revoked"]
                or datetime.fromisoformat(grant["expires_at"]) <= datetime.now(UTC)
                or not hmac.compare_digest(
                    grant["token_sha256"], hashlib.sha256(token.encode()).hexdigest()
                )
            ):
                raise Refused("FORBIDDEN_ROLE")
            cookie = secrets.token_urlsafe(32)
            csrf = self.csrf_for(cookie)
            expiry = datetime.fromisoformat(grant["expires_at"])
            c.execute(
                "UPDATE g1_http.challenges SET used=true WHERE hash=%s",
                (hashlib.sha256(challenge_cookie.encode()).hexdigest(),),
            )
            c.execute(
                "UPDATE g1_http.return_grants SET used_at=clock_timestamp() WHERE audit_ref=%s",
                (ref,),
            )
            c.execute(
                "INSERT INTO g1_http.sessions VALUES(%s,%s,%s,%s,%s,%s,%s,false)",
                (
                    self.cfg["tenant"],
                    hashlib.sha256(cookie.encode()).hexdigest(),
                    ref,
                    record["subject_ref"],
                    hashlib.sha256(csrf.encode()).hexdigest(),
                    realm["epoch"],
                    expiry,
                ),
            )
        return cookie, csrf, expiry

    def session(self, c, ref, cookie, csrf):
        record = self.current_record(c, ref)
        realm = self.realm(c)
        if type(cookie) is not str or type(csrf) is not str:
            raise Refused("FORBIDDEN_ROLE")
        row = c.execute(
            "SELECT audit_ref,subject_ref,csrf_hash,epoch,expires_at,revoked FROM g1_http.sessions WHERE hash=%s FOR SHARE",
            (hashlib.sha256(cookie.encode()).hexdigest(),),
        ).fetchone()
        grant = c.execute(
            "SELECT revoked FROM g1_http.return_grants WHERE audit_ref=%s", (ref,)
        ).fetchone()
        if (
            not row
            or row[0] != ref
            or row[1] != record["subject_ref"]
            or row[3] != realm["epoch"]
            or row[4] <= datetime.now(UTC)
            or row[5]
            or not grant
            or grant[0]
            or not hmac.compare_digest(row[2], hashlib.sha256(csrf.encode()).hexdigest())
        ):
            raise Refused("FORBIDDEN_ROLE")
        return record
