"""Server-owned post-COMMIT observations and original ledger checkpoints."""

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import threading

from vrae.intelligence import BudgetPolicy, Ledger, PriceSnapshot
from vrae.intelligence.s3 import CompletionPins
from vrae.l2_ops.sources import OperationsDenied


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise OperationsDenied("S5_PRIVATE_STATE_REQUIRED")
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def read(path, limit=1_000_000):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise OperationsDenied("S5_TRUSTED_STATE_UNAVAILABLE")
    return json.loads(path.read_bytes())


def completion(root, source, evidence, deadline):
    task = source.held
    if not re.fullmatch(r"[0-9a-f-]{36}", task.job_id):
        raise OperationsDenied("S5_CANONICAL_TASK_REQUIRED")
    value = read(root / (task.job_id + ".json"), 8192)
    keys = ("tenant_id", "request_id", "run_id", "job_id", "source_ref")
    if (
        set(value)
        != {
            "version",
            "task",
            "lease_started_at",
            "lease_expires_at",
            "worker_completed_at",
            "finish_event",
            "signed_result_sha256",
            "completion_clock_basis",
            "observed_committed_at",
        }
        or value["version"] != "S5_SERVER_POST_COMMIT_1"
        or value["completion_clock_basis"]
        != "VISIBLE_ROW_CREATED_AT_WITH_ORIGINAL_DEFERRED_LEASE_GUARD"
        or datetime.fromisoformat(value["observed_committed_at"]).tzinfo is None
        or value["task"] != {k: getattr(task, k) for k in keys}
        or value["finish_event"] != evidence.signed_locator["finish_event"]
        or value["signed_result_sha256"] != evidence.signed_locator["report_sha256"]
    ):
        raise OperationsDenied("S5_POST_COMMIT_BINDING_DENIED")
    pins = CompletionPins(
        task=task,
        report_content_hash=source.read().version["content_hash"],
        lease_started_at=datetime.fromisoformat(value["lease_started_at"]),
        lease_expires_at=datetime.fromisoformat(value["lease_expires_at"]),
        worker_completed_at=datetime.fromisoformat(value["worker_completed_at"]),
        authority_expires_at=deadline,
    )
    # A real early COMMIT is allowed, but S3 may start only after lease expiry.
    times = (pins.lease_started_at, pins.lease_expires_at, pins.worker_completed_at, deadline)
    if (
        any(t.tzinfo is None for t in times)
        or (pins.lease_expires_at - pins.lease_started_at).total_seconds() != 30
        or not pins.lease_started_at <= pins.worker_completed_at < pins.lease_expires_at
    ):
        raise OperationsDenied("S5_ORIGINAL_LEASE_COMMIT_REQUIRED")
    return pins


class Book:
    """Original ledger plus independently server-written latest checkpoint pin."""

    def __init__(self, root, context):
        self.lock = threading.RLock()
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.scope = context.gateway_pins.scope
        self.policy = BudgetPolicy("CNY", "1.0")
        self.price = PriceSnapshot("s5-offline-synthetic-only", "CNY", "0.01", "0.02")
        self.path, self.pin = self.root / "ledger.json", self.root / "latest-pin.json"
        if self.path.exists() != self.pin.exists():
            raise OperationsDenied("S5_CHECKPOINT_INCOMPLETE")
        if self.path.exists():
            saved, held = read(self.path), read(self.pin, 8192)
            if held["scope"] != asdict(self.scope):
                raise OperationsDenied("S5_CHECKPOINT_SCOPE_DENIED")
            self.ledger = Ledger.restore(
                saved,
                expected_ledger_ref=held["ledger_ref"],
                scope=self.scope,
                policy=self.policy,
                price=self.price,
            )
        else:
            self.ledger = Ledger(self.scope, self.policy, self.price)
        self.save()

    def save(self):
        with self.lock:
            value = self.ledger.snapshot()
            write(self.path, value)
            write(self.pin, {"scope": asdict(self.scope), "ledger_ref": value["ledger_ref"]})

    def finish(self, path, result):
        self.save()
        write(
            path,
            {
                "mode": result["mode"],
                "state": "COMPLETED",
                "scope": asdict(self.scope),
                "receipt_ref": result["receipt_ref"],
                "context_ref": result["context_ref"],
                "result_sha256": hashlib.sha256(
                    json.dumps(result, sort_keys=True).encode()
                ).hexdigest(),
            },
        )
