"""C3 assembly of Owner-merged C2 native reports and original task authority.

No constructor/DTO is access permission. The caller must retain the original
signed task context during production. Brief reads/writes use BOTH original
current contexts; neither a Worker lease nor a snapshot renews review authority.
"""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import os

from vrae.industry.l2_v1 import load
from vrae.application.ra4b_p2.m1.consumer import TaskHandle
from vrae.l2.native import NativeTask, NativeSource, current_report
from vrae.l2.ledger import Ledger
from vrae.l2_ops.briefs import CurrentL2
from vrae.l2_ops.native_diagnosis import NativeDiagnosis, analyze
from vrae.l2_ops.sources import OperationsDenied, SourceBundle
from vrae.reviewing.canonical import canonical, parse, sha
from .current_worker import current_worker


def produce(diagnosis, bundle, *, created_at):
    """Called inside the original current_worker context; never from browser JSON.

    created_at is the persisted FIRST report-creation time. Reconstitution after
    restart uses the same value, original task and source bytes, never a new ID.
    NativeSource performs the accepted full C1 replay; no authored fallback.
    """
    if type(diagnosis) is not NativeDiagnosis or type(bundle) is not SourceBundle:
        raise OperationsDenied("L2_NATIVE_PRODUCTION_INPUT_REQUIRED")
    stamp = datetime.fromisoformat(created_at)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise OperationsDenied("L2_NATIVE_CREATION_TIME_REQUIRED")
    evidence = diagnosis.evidence
    if (bundle.tenant_id != evidence.task.tenant_id
            or bundle.document()["content_sha256"] != evidence.source_bundle_sha256):
        raise OperationsDenied("L2_NATIVE_SOURCE_BINDING_DENIED")
    held = NativeTask(**asdict(evidence.task), native_pack_ref=evidence.pack.ref,
        industry_ref=diagnosis.industry_ref, diagnosis_ref=diagnosis.result_ref,
        source_bundle_sha256=evidence.source_bundle_sha256,
        source_access_mode=bundle.access_mode, created_at=created_at)
    return NativeSource(evidence.pack, diagnosis.document, held=held)


def bind_worker(evidence, source, bundle):
    """Check independently held original task against the C2 producer binding."""
    if type(source) is not NativeSource or type(bundle) is not SourceBundle:
        raise OperationsDenied("L2_NATIVE_PRODUCER_REQUIRED")
    held = source.held
    if (any(getattr(held, k) != value for k, value in asdict(evidence.task).items())
            or held.native_pack_ref != evidence.pack.ref
            or held.source_bundle_sha256 != evidence.source_bundle_sha256
            or held.source_bundle_sha256 != bundle.document()["content_sha256"]
            or held.source_access_mode != bundle.access_mode
            or held.tenant_id != bundle.tenant_id):
        raise OperationsDenied("L2_NATIVE_REPORT_TASK_MISMATCH")
    if load(tenant_id=held.tenant_id)["industry_ref"] != held.industry_ref:
        raise OperationsDenied("L2_NATIVE_INDUSTRY_CHANGED")


class NativeCurrentReader:
    """Application composition root supplies these original ports and sessions.

    Lock order is task PG authority -> C2 directory/ledger -> Brief PG COMMIT.
    The original task lease is deliberately not read or used as a deadline.
    """
    def __init__(self, port, task, sessions, sid, *, policy_expires_at,
                 ledger, review_sid, bundle):
        if type(ledger) is not Ledger or type(ledger.source) is not NativeSource:
            raise OperationsDenied("L2_NATIVE_LEDGER_REQUIRED")
        self.port, self.task, self.sessions, self.sid = port, task, sessions, sid
        self.policy_expires_at = policy_expires_at
        self.ledger, self.review_sid, self.bundle = ledger, review_sid, bundle
        self.report_id = ledger.source.read().version["report_id"]

    @contextmanager
    def current(self):
        checks = []
        with current_worker(self.port, self.task, self.sessions, self.sid,
                            policy_expires_at=self.policy_expires_at, guards=checks) as (evidence, deadline):
            bind_worker(evidence, self.ledger.source, self.bundle)
            path = self.ledger.path
            identity = (path.stat().st_dev, path.stat().st_ino)
            with current_report(self.ledger, self.review_sid, self.report_id) as report:
                active = True

                def validate():
                    if (not active or path.is_symlink()
                            or (path.stat().st_dev, path.stat().st_ino) != identity):
                        raise OperationsDenied("L2_REVIEW_LEDGER_REPLACED")
                    for check in checks:
                        check()
                    self.ledger.directory.require(self.review_sid, self.report_id)

                current = CurrentL2(report.pins, report.payload, report.review, report.blueprint,
                    min(deadline, report.authority_expires_at), validate)
                try:
                    current.snapshot()
                    yield current
                    current.assert_live()
                finally:
                    active = False


def produce_current(port, task, sessions, sid, *, policy_expires_at, bundle, created_at, audit=None):
    """Original signed task read -> full C1 -> full C2 replay, with live fencing."""
    with current_worker(port, task, sessions, sid, policy_expires_at=policy_expires_at) as (evidence, _):
        from vrae.l2_ops.accounting import ActivityTimer
        diagnosis = analyze(evidence)
        timer = ActivityTimer(task.job_id + "-c2-native-report", "DIAGNOSIS_RUNTIME", "SYSTEM")
        source = produce(diagnosis, bundle, created_at=created_at)
        activities = (*diagnosis.activities, timer.finish().priced())
        if audit is not None:
            audit(evidence, diagnosis)
    return source, activities


def production_stamp(root, task, bundle):
    """Private provenance only, never authority; stable first-creation after restart.

    Task handle and bundle come from trusted application ports, not HTTP input.
    Original task/C2 authority is still required to produce or read the report.
    """
    if (type(task) is not TaskHandle or type(bundle) is not SourceBundle
            or task.tenant_id != bundle.tenant_id):
        raise OperationsDenied("L2_NATIVE_CREATION_SCOPE_REQUIRED")
    root = Path(root)
    if root.is_symlink():
        raise OperationsDenied("L2_NATIVE_PRIVATE_STATE_REQUIRED")
    root.mkdir(parents=True, exist_ok=True)
    scope = {"task": asdict(task), "source_bundle_sha256": bundle.document()["content_sha256"]}
    path = root / (sha(canonical(scope)) + ".created.json")
    if path.is_symlink():
        raise OperationsDenied("L2_NATIVE_PRIVATE_STATE_REQUIRED")
    doc = {"contract": "l2-native-creation-v1", **scope, "created_at": datetime.now(UTC).isoformat()}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "wb") as f:
            f.write(canonical(doc))
            f.flush()
            os.fsync(f.fileno())
    if not 1 <= path.stat().st_size <= 8192:
        raise OperationsDenied("L2_NATIVE_CREATION_RECORD_DENIED")
    saved = parse(path.read_bytes(), limit=8192)
    if (set(saved) != {"contract", "task", "source_bundle_sha256", "created_at"}
            or saved["contract"] != "l2-native-creation-v1"
            or saved["task"] != scope["task"]
            or saved["source_bundle_sha256"] != scope["source_bundle_sha256"]):
        raise OperationsDenied("L2_NATIVE_CREATION_RECORD_DENIED")
    stamp = datetime.fromisoformat(saved["created_at"])
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise OperationsDenied("L2_NATIVE_CREATION_TIME_REQUIRED")
    return saved["created_at"]


def mount(app, source, directory, ledger_path, *, refresh):
    """Mount accepted DeepConsole on the EXISTING B5B Application, never a server.

    The composition root provisions original C2 Directory identities with the
    actual report ID; this function cannot add a person, role or report grant.
    Source must be produced from the original signed current task first.
    """
    from apps.operator_console.b5b_http import Application
    from apps.operator_console.l2_http import DeepConsole
    from vrae.l2.identity import Directory

    if (type(app) is not Application or app.generated is None
            or type(source) is not NativeSource or type(directory) is not Directory
            or directory.mode != "CONTROLLED"):
        raise OperationsDenied("L2_ORIGINAL_SSR_CONTROLLED_PORTS_REQUIRED")
    rid = source.read().version["report_id"]
    if not any(p.tenant_id == source.held.tenant_id and rid in p.report_ids
               and p.role in ("OWNER", "REVIEWER") for p in directory.people.values()):
        raise OperationsDenied("L2_NATIVE_REVIEW_PROVISIONING_REQUIRED")
    if app.deep is not None and app.deep.directory is not directory:
        raise OperationsDenied("L2_ORIGINAL_DIRECTORY_REQUIRED")
    if app.deep is not None:
        existing = app.deep.ledgers.get(rid)
        if existing is not None and (existing.source.expected != source.expected
                                     or existing.path != Path(ledger_path)):
            raise OperationsDenied("L2_NATIVE_REPORT_REPLACEMENT_DENIED")
    ledger = Ledger(ledger_path, source, directory)
    if app.deep is None:
        deep = DeepConsole(directory, {rid: ledger}, refresh)
        deep.l1_enabled = True
        app.deep = deep
    else:
        app.deep.ledgers[rid] = ledger
    return ledger


def attach_business(app, brief_ledger, *, report_id, bundle, activities, subject, factory):
    """Same original SSR, exact server-held actor and dual-authority reader factory."""
    from .native_business import NativeBusiness
    if app.native_business is None:
        app.native_business = NativeBusiness(app, brief_ledger)
    elif app.native_business.ledger is not brief_ledger:
        raise OperationsDenied("L2_NATIVE_BRIEF_STORE_REPLACEMENT_DENIED")
    app.native_business.bind(report_id, bundle=bundle, activities=activities, subject=subject, factory=factory)
    return "/b5a/l2/r/" + report_id + "/brief"
