"""UID10003: original signed M1 context, original C1/C2 and controlled ledger."""

from dataclasses import asdict
from datetime import datetime, UTC
import hashlib
import json
import os
from pathlib import Path
import sys
import sqlite3

import psycopg

from apps.operator_console.b5b_m2_sessions import GeneratedSessions
from integration.l2_ops.native_report import produce_current, production_stamp
from integration.l2_ops.source_profiles import selected
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient, TaskHandle
from vrae.application.ra4b_p2.m1.reader import JobAssignment, SignedGeneratedReader
from vrae.identity.boundary import TrustAnchor
from vrae.l2.identity import Directory, Person
from vrae.l2.ledger import Ledger
from vrae.l2_ops.tasks import L2Tasks, RegisteredSource
from vrae.reviewing.canonical import canonical


def exchange(kind, **values):
    print(json.dumps({"kind": kind, **values}), flush=True)
    return json.loads(sys.stdin.readline())


def main():
    assert os.geteuid() == 10003
    cfg = json.loads(sys.stdin.readline())
    task = TaskHandle(**cfg["task"])
    source_ref, bundle, native = selected("industrial-p40-v3")
    client = TaskClient(
        AppEndpoint(
            cfg["app_bearer"],
            "tenant-test",
            frozenset(("accepted-404", "accepted-200", source_ref)),
        )
    )
    port = L2Tasks(client, [RegisteredSource(source_ref, native)])
    role = "p2b1_test_a_reviewer"

    def connect(requested):
        assert requested == role
        return psycopg.connect(
            host="127.0.0.1",
            port=5432,
            dbname="vrae_ra4a_p1",
            user=role,
            password=cfg["reviewer_password"],
            autocommit=True,
            connect_timeout=3,
            options="-c statement_timeout=2000 -c lock_timeout=1500",
        )

    anchor = cfg["anchor"]
    reader = SignedGeneratedReader(
        anchor=TrustAnchor(
            anchor["issuer"],
            anchor["audience"],
            json.dumps(anchor["jwks"]).encode(),
            anchor["expires"],
        ),
        assignments=[
            JobAssignment(
                anchor["issuer"],
                "synthetic-reviewer-1",
                role,
                task.tenant_id,
                task.job_id,
                anchor["expires"],
            )
        ],
        connect=connect,
    )
    sessions = GeneratedSessions(reader)
    sessions.bind_task(reader.assignments[0], port.client, task)
    challenge, nonce, csrf = sessions.challenge(task.tenant_id, task.job_id)
    signed = exchange("m1-sign", nonce=nonce)
    sid = sessions.login(challenge, signed["bearer"], csrf)
    root = Path("/evidence/consumer")
    stamp = production_stamp(root, task, bundle)
    source, activities = produce_current(
        port,
        task,
        sessions,
        sid,
        policy_expires_at=datetime.fromisoformat(cfg["policy_expires_at"]),
        bundle=bundle,
        created_at=stamp,
    )
    view = source.read()
    rid = view.version["report_id"]
    review = cfg["review_anchor"]
    directory = Directory(
        issuer=review["issuer"],
        audience=review["audience"],
        jwks=review["jwks"],
        expires=review["expires"],
        mode="CONTROLLED",
        people=[
            Person(
                "launch-synthetic-reviewer",
                "launch-synthetic-reviewer",
                "合成运行恢复演练员，非正式人审",
                task.tenant_id,
                "REVIEWER",
                (rid,),
            )
        ],
    )
    if cfg["phase"] == "restore":
        with (
            sqlite3.connect(root / "reviews.backup.sqlite") as saved,
            sqlite3.connect(root / "reviews.sqlite") as target,
        ):
            saved.backup(target)
    ledger = Ledger(root / "reviews.sqlite", source, directory)
    nonce, csrf = directory.challenge()
    signed = exchange("c2-sign", nonce=nonce)
    review_sid = directory.login(signed["bearer"], nonce, csrf)
    current = ledger.read(review_sid, rid)
    mismatch_denied = False
    try:
        ledger.review(
            review_sid,
            rid,
            version=current.version["version"] + 1,
            content_hash=current.version["content_hash"],
            display_hash=current.display_hash,
            action="APPROVE",
            reason="OFFLINE_SYNTHETIC mismatched version must fail",
            items={
                x["id"]: "ACK" for x in current.document["findings"] + current.document["blueprint"]
            },
            attest=True,
        )
    except ValueError:
        mismatch_denied = True
    assert mismatch_denied
    if cfg["phase"] == "first":
        receipt = ledger.review(
            review_sid,
            rid,
            version=current.version["version"],
            content_hash=current.version["content_hash"],
            display_hash=current.display_hash,
            action="APPROVE",
            reason="OFFLINE_SYNTHETIC恢复演练；不是真人Gold或客户批准。",
            items={
                x["id"]: "ACK" for x in current.document["findings"] + current.document["blueprint"]
            },
            attest=True,
        )
    else:
        receipt = ledger.history(review_sid, rid)[1][0]
    assert receipt["formal_human_review"] is False and receipt["external_delivery"] is False
    with (
        sqlite3.connect(root / "reviews.sqlite") as live,
        sqlite3.connect(root / "reviews.backup.sqlite") as backup,
    ):
        live.backup(backup)
    (root / "reviews.backup.sqlite").chmod(0o600)
    # Real C2 current-key revocation: no fabricated DTO substitutes for the directory.
    key_id = directory.require(review_sid, rid).key_id
    directory.revoked_keys.add(key_id)
    refused = False
    try:
        ledger.read(review_sid, rid)
    except ValueError:
        refused = True
    assert refused
    value = {
        "task": asdict(task),
        "pack_ref": source.held.native_pack_ref,
        "report_id": rid,
        "version": current.version["version"],
        "content_hash": current.version["content_hash"],
        "display_hash": current.display_hash,
        "controlled_receipt_sha256": hashlib.sha256(canonical(receipt)).hexdigest(),
        "controlled_formal_human": False,
        "external_delivery": False,
        "blueprint_packages": len(current.document["blueprint"]),
        "current_c2_key_revocation_denied": refused,
        "wrong_report_version_denied": mismatch_denied,
        "source_access_mode": bundle.access_mode,
        "real_model_calls": 0,
        "money_status": "UNKNOWN",
        "activities": list(activities),
        "verified_at": datetime.now(UTC).isoformat(),
    }
    print(json.dumps({"kind": "result", "value": value}), flush=True)


if __name__ == "__main__":
    main()
