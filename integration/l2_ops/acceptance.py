"""TEST_ONLY one-command acceptance and evidence capture before owned teardown.

No runtime grant, server or replacement engine. Original launch, browser and
cleanup remain authoritative. Private dumps are never part of the public export.
"""
import hashlib
import json
import re
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET

from integration.beta_review.codex3 import local_app
from integration.beta_review.codex3.m3_browser_run import run as browser
from integration.beta_review.codex3.runner import ROOT


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def command(args):
    return subprocess.check_output(args, cwd=ROOT, stderr=subprocess.PIPE)


def credentials(private):
    found = set()
    def walk(value, sensitive=False):
        if isinstance(value, str):
            if sensitive and len(value) > 12:
                found.add(value.encode())
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, sensitive or any(word in key.lower() for word in ("password", "bearer", "key_secret", "private_key")))
        elif isinstance(value, list):
            for item in value:
                walk(item, sensitive)
    for path in [*(private/"pg").rglob("state.json"), *private.glob("*.json")]:
        walk(json.loads(path.read_bytes()))
    return found


def owned(private, label, expected=None):
    record = json.loads((private/"ownership.json").read_bytes())
    assert record["value"] == label and record["label"] == "vrae.beta.codex3"
    item = json.loads(command(["docker", "inspect", record["pg"]]))[0]
    assert item["Config"]["Labels"]["vrae.b5_p0"] == record["pg"]
    assert any(m.get("Name") == record["pg"]+"-data" for m in item["Mounts"])
    if expected is not None:
        assert item["Id"] == expected, "OWNED_PG_ID_CHANGED"
    return record, item["Id"]


def snapshot(private, label, expected, stage):
    record, ident = owned(private, label, expected)
    target = private/("acceptance-snapshot-"+stage)
    target.mkdir(exist_ok=False)
    files = {}
    for database in ("vrae_ra4a_p1", "vrae_l2_internal"):
        raw = command(["docker", "exec", record["pg"], "pg_dump", "-Fc", "-U", "postgres", "-d", database])
        path = target/(database+".dump")
        path.write_bytes(raw)
        files[path.name] = {"bytes": len(raw), "sha256": sha(raw)}
    if stage != "before-browser":
        for name in ("reviews.sqlite", "active-proof.json", "s0-audit-request.json",
                     *("s0-audit-"+case+".json" for case in (
                         "idempotent", "wrong-task", "pg-interruption", "task-connection-loss", "sqlite-unavailable",
                         "post-exit-review-change", "concurrent-review", "c2-revocation"))):
            result = subprocess.run(["docker", "cp", record["volume"]+"-ssr:/state/l2-native/"+name, str(target/name)],
                                    cwd=ROOT, capture_output=True, check=False)
            if result.returncode == 0:
                raw = (target/name).read_bytes()
                files[name] = {"bytes": len(raw), "sha256": sha(raw)}
        query = """SELECT coalesce(json_agg(x),'[]'::json) FROM (
          SELECT b.brief_ref,b.content_sha256,b.authorization_expires_at,b.created_at,
          EXISTS(SELECT 1 FROM l2_ops_v1.brief_completions f WHERE
          (f.tenant_id,f.brief_ref,f.content_sha256)=(b.tenant_id,b.brief_ref,b.content_sha256)) completed
          FROM l2_ops_v1.briefs b WHERE b.tenant_id='tenant-test' ORDER BY b.brief_ref)x"""
        raw = command(["docker", "exec", record["pg"], "psql", "-U", "postgres", "-d", "vrae_l2_internal", "-Atc", query])
        (target/"brief-row-states.json").write_bytes(raw)
        files["brief-row-states.json"] = {"bytes": len(raw), "sha256": sha(raw)}
    proof = {"scope": "PRIVATE_SYNTHETIC_DATABASE_DO_NOT_PUBLISH_DUMPS", "stage": stage,
        "container_id": ident, "label": label, "source_sha": command(["git", "rev-parse", "HEAD"]).decode().strip(),
        "snapshot_unix_ns": time.time_ns(), "multi_store_snapshot_atomic": False, "files": files}
    (target/"manifest.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    return target


def publish(label, private, secrets, outcome):
    output = ROOT/"docs/03-engineering/l2-operations"/label
    output.mkdir(exist_ok=False)
    # Raw Windows evidence keeps its exact bytes even under core.autocrlf.
    (output/".gitattributes").write_text("* -text whitespace=cr-at-eol\n", encoding="utf-8")
    source = ROOT/"docs/03-engineering/beta-closure/codex3/.private"/label
    inputs = []
    folder = private/"browser-native-l2"
    allowed = {"browser.json", "browser-failure.json", "assertions.json", "browser-process-cleanup.json",
               "native-chain.json", "live-dual-authority.json", "real-task-switch.json"}
    if folder.exists():
        inputs += [(p, p.name) for p in folder.iterdir() if p.is_file() and (p.name in allowed or p.suffix in {".png", ".pdf"})]
    inputs += [(p, p.name) for p in source.glob("*") if p.name in {"result.json", "component-stages.xml", "source-manifest.json", "publication.json"}]
    inputs += [(p, p.name) for p in private.glob("s0-worker-*.json")]
    inputs += [(p, p.name) for p in private.glob("restart-*.json")]
    inputs += [(p, p.name) for p in private.glob("*") if p.is_file() and p.name in {
        "ownership.json", "l2-owned-cleanup.json", "l2-business-storage.json", "l2-readiness.json"}]
    inputs += [(p, "worker-"+p.parent.name+".log") for p in (private/"native").rglob("m1-worker.log")]
    for target in private.glob("acceptance-snapshot-*"):
        for name in ("manifest.json", "brief-row-states.json"):
            if (target/name).exists():
                inputs.append((target/name, target.name+"-"+name))
    forbidden = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|postgres(?:ql)?://[^\s\"']+:[^\s\"']+@")
    for path, name in inputs:
        raw = path.read_bytes()
        assert not any(value in raw for value in secrets), "ACTUAL_CREDENTIAL_PUBLICATION_MATCH"
        assert not forbidden.search(raw), "SECRET_PATTERN_PUBLICATION_MATCH"
        (output/name).write_bytes(raw)
    records = json.loads((folder/"assertions.json").read_bytes()) if (folder/"assertions.json").exists() else []
    suite = ET.Element("testsuite", name="Actual Chrome S0 assertions and acceptance completion",
        tests=str(len(records)+1), failures=str(sum(not r["pass"] for r in records)+(not outcome["pass"])), errors="0", skipped="0")
    for item in [*records, {"name": "owned_acceptance_completion", "pass": outcome["pass"]}]:
        case = ET.SubElement(suite, "testcase", classname="Chrome.actual_assertion", name=item["name"])
        if not item["pass"]:
            ET.SubElement(case, "failure", message="Original RED retained; no rerun or fabricated PASS")
    (output/"browser-assertions.xml").write_bytes(ET.tostring(suite, encoding="utf-8", xml_declaration=True))
    (output/"acceptance.json").write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    files = {p.name: {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in output.iterdir() if p.is_file()}
    (output/"evidence-manifest.json").write_text(json.dumps({"source_sha": outcome["source_sha"],
        "actual_secret_values_checked": len(secrets), "credential_matches": 0,
        "private_dumps_profiles_tokens_excluded": True, "files": files}, indent=2), encoding="utf-8")
    return output


def accept(label, minor):
    assert re.fullmatch("[a-z0-9-]{3,30}", label)
    assert tuple(map(int, minor.split("."))) == sys.version_info[:2], "NATIVE_DRIVER_MINOR_MISMATCH"
    from . import readiness
    assert readiness.enabled(), "ACCEPTED_PERFORMANCE_MAIN_REQUIRED"
    head = command(["git", "rev-parse", "HEAD"]).decode().strip()
    result, code = local_app.start(label, minor, False, workbench=True, l2_prepare=True)
    assert code == 0 and result["state"] == "STARTING"
    private = local_app.folder_for(label)
    outcome = {"source_sha": head, "minor": minor, "label": label, "pass": False,
               "scope": "S0_SYNTHETIC_NATIVE_BROWSER_PENDING_OWNER", "owner_final_pass": False}
    secrets, failure, ident = set(), None, None
    try:
        deadline = time.monotonic()+300  # overall test orchestration, not any service/auth timeout
        while True:
            state = local_app.status(label)
            if state["state"] == "M3_READY":
                break
            assert state["state"] == "STARTING", "ORIGINAL_STARTUP_FAILED"
            assert time.monotonic()<deadline, "ORIGINAL_STARTUP_NOT_READY"
            time.sleep(0.2)
        assert state["source_sha"] == head
        secrets.update(credentials(private))
        assert list((private/"pg").rglob("state.json")), "ACTUAL_CREDENTIAL_SET_REQUIRED"
        _, ident = owned(private, label)
        snapshot(private, label, ident, "before-browser")
        outcome["browser"] = browser(label, native_l2=True)
        outcome["pass"] = True
    except BaseException as error:
        failure = error
        outcome["failure_type"] = type(error).__name__
        log_root = private if private.is_dir() else local_app.launch_for(label)
        (log_root/"acceptance-original-red.private.log").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        secrets.update(credentials(private))
        if ident:
            try:
                snapshot(private, label, ident, "final" if outcome["pass"] else "red")
                outcome["private_snapshot_saved_before_teardown"] = True
            except BaseException as error:
                outcome["pass"] = False
                outcome["snapshot_failure_type"] = type(error).__name__
                failure = failure or error
        local_app.request_stop(label)
        deadline = time.monotonic()+180
        while not (local_app.launch_for(label)/"supervisor-end.json").exists():
            assert time.monotonic()<deadline, "OWNED_TEARDOWN_NOT_CONFIRMED"
            time.sleep(0.1)
        closed = local_app.status(label)
        cleanup_path = private/"l2-owned-cleanup.json"
        cleanup = json.loads(cleanup_path.read_bytes()) if cleanup_path.exists() else {
            "recorded_container_absent": False, "recorded_pg_volumes_absent": False,
            "status": "UNKNOWN_NOT_PROVEN", "old_anonymous_volumes": "UNKNOWN_UNTOUCHED"}
        outcome["owned_cleanup"] = cleanup
        outcome["closed"] = closed["state"] == "CLOSED"
        outcome["pass"] = outcome["pass"] and outcome["closed"] and cleanup["recorded_container_absent"] and cleanup["recorded_pg_volumes_absent"]
        assert command(["git", "rev-parse", "HEAD"]).decode().strip() == head
        folder = publish(label, private, secrets, outcome)
    if failure:
        raise RuntimeError("S0_ACCEPTANCE_RED_PRESERVED_"+str(folder)) from None
    assert outcome["pass"]
    return {"source_sha": head, "status": "LOCAL_CANDIDATE_PASS_PENDING_OWNER", "public_evidence": str(folder), "closed": True}
