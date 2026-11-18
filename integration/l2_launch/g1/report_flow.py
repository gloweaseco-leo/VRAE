"""Current signed original M1 -> original industry/Guard -> original C2 ledger.

A DTO is never used as authority. The current_worker transaction stays open for
caller output. Controlled review never becomes formal human review or release.
"""

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace

import psycopg
from apps.operator_console.b5b_m2_sessions import GeneratedSessions
from vrae.application.ra4b_p2.m1.reader import JobAssignment, SignedGeneratedReader
from vrae.identity.boundary import TrustAnchor
from vrae.l2.identity import Directory, Person
from vrae.l2.ledger import Ledger
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource
from vrae.l2_ops.native_diagnosis import analyze
from integration.l2_ops.current_worker import current_worker
from integration.l2_ops.native_report import produce, production_stamp
from integration.l2_launch.g1.broker import ask


class ReportFlow:
    def __init__(self, store):
        self.store = store

    @contextmanager
    def current(self, record):
        cfg = self.store.cfg
        task = self.store.task(record)
        plan = self.store.plans[record["source_ref"]]
        role = "p2b1_test_a_reviewer"

        def connect(requested):
            if requested != role:
                raise ValueError("G1_REVIEW_ROLE_DENIED")
            return psycopg.connect(
                host="127.0.0.1",
                port=5432,
                dbname="vrae_ra4a_p1",
                user=role,
                password=cfg["reviewer_password"],
                autocommit=True,
                connect_timeout=2,
                options="-c statement_timeout=2000 -c lock_timeout=1500",
            )

        anchor = cfg["m1_anchor"]
        assignment = JobAssignment(
            anchor["issuer"],
            "synthetic-reviewer-1",
            role,
            task.tenant_id,
            task.job_id,
            anchor["expires"],
        )
        reader = SignedGeneratedReader(
            anchor=TrustAnchor(
                anchor["issuer"],
                anchor["audience"],
                json.dumps(anchor["jwks"]).encode(),
                anchor["expires"],
            ),
            assignments=[assignment],
            connect=connect,
        )
        port = L2Tasks(self.store.client, [RegisteredSource(plan.ref, plan.native)])
        sessions = GeneratedSessions(reader)
        sessions.bind_task(assignment, port.client, task)
        challenge, nonce, csrf = sessions.challenge(task.tenant_id, task.job_id)
        sid = sessions.login(challenge, ask(cfg["broker"], "m1", task, nonce), csrf)
        root = Path(cfg["report_root"]) / record["audit_ref"]
        root.mkdir(mode=0o700, exist_ok=True)
        stamp = production_stamp(root, task, plan.bundle)
        checks = []
        with current_worker(
            port,
            task,
            sessions,
            sid,
            policy_expires_at=datetime.fromisoformat(plan.policy["expires_at"]),
            guards=checks,
        ) as (evidence, deadline):
            diagnosis = analyze(evidence)
            source = produce(diagnosis, plan.bundle, created_at=stamp)
            initial = source.read()
            rid = initial.version["report_id"]
            review = cfg["review_anchor"]
            directory = Directory(
                issuer=review["issuer"],
                audience=review["audience"],
                jwks=review["jwks"],
                expires=review["expires"],
                mode="CONTROLLED",
                people=[
                    Person(
                        "g1-controlled-reviewer",
                        "g1-controlled-reviewer",
                        "G1 synthetic reviewer fixture; not a human approval",
                        task.tenant_id,
                        "REVIEWER",
                        (rid,),
                    )
                ],
            )
            nonce, csrf = directory.challenge()
            review_sid = directory.login(ask(cfg["broker"], "review", task, nonce), nonce, csrf)
            ledger = Ledger(root / "review.sqlite", source, directory)
            view = ledger.read(review_sid, rid)
            result = SimpleNamespace(
                task=task,
                plan=plan,
                evidence=evidence,
                diagnosis=diagnosis,
                source=source,
                ledger=ledger,
                review_sid=review_sid,
                report_id=rid,
                view=view,
                deadline=deadline,
            )
            yield result
            directory.require(review_sid, rid)
            for check in checks:
                check()

    def state(self, record):
        with self.current(record) as current:
            capture = current.evidence.pack.document["sources"][0]["document"]
            if any(p["snapshot"]["status"] == "ACCESS_BLOCKED" for p in capture["pages"]):
                return "ACCESS_BLOCKED"
            if not current.diagnosis.document["source_facts"]:
                return "INSUFFICIENT_EVIDENCE"
            return "DRAFT_READY"
