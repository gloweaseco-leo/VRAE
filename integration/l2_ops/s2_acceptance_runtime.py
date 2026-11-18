"""Finite TEST_ONLY real S2 stage, original launch/SSR/PG and exact owned teardown."""
import argparse
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
from .acceptance import command, credentials, owned, snapshot

ACCEPTED_MAIN = "6a15ab4514d24c60b4d03d4ec795f6e3bcd435c3"
OWNER_LABEL = "vrae.beta.codex3"


def observe_owned(label, private, records):
    record = json.loads((private/"ownership.json").read_bytes())
    assert record["value"] == label
    ids = command(["docker", "ps", "-aq", "--no-trunc", "--filter",
                   "label="+OWNER_LABEL+"="+label]).decode().split()
    for cid in ids:
        item = json.loads(command(["docker", "inspect", cid]))[0]
        assert item["Id"] == cid and item["Config"]["Labels"].get(OWNER_LABEL) == label
        for mount in item["Mounts"]:
            if mount["Type"] == "volume":
                records.setdefault(mount["Name"], {"name": mount["Name"], "container_id": cid,
                    "owner_label": label, "destination": mount["Destination"]})
    (private/"s2-owned-mounts.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


def clean_recorded(records):
    results = []
    for name, item in records.items():
        check = subprocess.run(["docker", "volume", "inspect", name], cwd=ROOT, capture_output=True)
        removed = False
        if check.returncode == 0:
            volume = json.loads(check.stdout)[0]
            assert volume["Name"] == name
            # Only volumes actually observed attached to this exact owned container.
            assert not command(["docker", "ps", "-aq", "--filter", "volume="+name]).strip()
            command(["docker", "volume", "rm", name])
            removed = True
        assert subprocess.run(["docker", "volume", "inspect", name], cwd=ROOT,
                              capture_output=True).returncode != 0
        results.append({**item, "absent": True, "removed_after_owned_stop": removed})
    return {"volumes": results, "old_anonymous_volumes": "UNKNOWN_UNTOUCHED", "global_prune": False}


def publish(label, private, secrets, outcome):
    out = ROOT/"docs/03-engineering/l2-operations"/label
    out.mkdir(exist_ok=False)
    (out/".gitattributes").write_text("* -text whitespace=cr-at-eol\n", encoding="utf-8")
    folder = private/"browser-s2-l2"
    allowed = {"browser.json", "browser-failure.json", "assertions.json",
               "browser-process-cleanup.json", "s2-native-chain.json"}
    files = [(p, p.name) for p in folder.glob("*") if p.is_file()
             and (p.name in allowed or p.suffix in (".png", ".pdf"))]
    files += [(p, p.name) for p in private.glob("*") if p.is_file() and
              (p.name.startswith("s0-worker-") or p.name.startswith("restart-") or p.name in
               ("l2-owned-cleanup.json", "s2-owned-cleanup.json", "l2-business-storage.json",
                "s2-source-manifest.json", "s2-owned-mounts.json"))]
    for location in private.glob("acceptance-snapshot-*"):
        for name in ("manifest.json", "brief-row-states.json"):
            if (location/name).exists():
                files.append((location/name, location.name+"-"+name))
    forbidden = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|postgres(?:ql)?://[^\s\"']+:[^\s\"']+@")
    for source, name in files:
        raw = source.read_bytes()
        assert not forbidden.search(raw) and not any(s in raw for s in secrets), "S2_SECRET_PUBLICATION_DENIED"
        (out/name).write_bytes(raw)
    rows = json.loads((folder/"assertions.json").read_bytes()) if (folder/"assertions.json").exists() else []
    suite = ET.Element("testsuite", name="S2 actual browser stage",
        tests=str(len(rows)+1), failures=str(sum(not x["pass"] for x in rows)+(not outcome["pass"])),
        errors="0", skipped="0")
    for row in [*rows, {"name":"owned_stage_completion", "pass":outcome["pass"]}]:
        case = ET.SubElement(suite, "testcase", classname="S2.actual_browser", name=row["name"])
        if not row["pass"]:
            ET.SubElement(case, "failure", message="Actual RED preserved")
    (out/"browser-junit.xml").write_bytes(ET.tostring(suite, encoding="utf-8", xml_declaration=True))
    (out/"s2-stage.json").write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    manifest = {p.name:{"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in out.iterdir() if p.is_file()}
    (out/"evidence-manifest.json").write_text(json.dumps({"source_sha":outcome["source_sha"],
        "files":manifest,"exact_credentials_checked":len(secrets),"credential_matches":0,
        "private_dumps_profiles_keys_tokens_excluded":True}, indent=2), encoding="utf-8")
    return out



def failure_receipt(private, label, phase, error):
    """Allowlisted locations and exact private-log digests, never log text."""
    logs = []
    frames = []
    original_type = None
    own_log = private/"s2-original-red.private.log"
    if not own_log.is_file():
        own_log = local_app.launch_for(label)/"s2-original-red.private.log"
    candidates = (("s2_controller", own_log),
                  ("original_supervisor", local_app.launch_for(label)/"local-supervisor.private.log"))
    for role, location in candidates:
        if not location.is_file():
            continue
        raw = location.read_bytes()
        logs.append({"role": role, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        # Inspect a bounded suffix. No source lines, messages or absolute paths leave this function.
        text = raw[-262144:].decode("utf-8", errors="replace")
        if role == "original_supervisor":
            # The first traceback wins even if later teardown also fails.
            text = text.split("Traceback (most recent call last):", 1)[-1]
            type_match = re.search(r"^((?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))(?::|$)", text, re.M)
            if type_match:
                original_type = type_match[1].rsplit(".", 1)[-1]
                text = text[:type_match.start()]
            for path, line, method in re.findall(r'File "([^"\n]+)", line (\d+), in ([A-Za-z_][A-Za-z0-9_]*)', text):
                match = re.search(r'(?:^|[/\\])((?:integration|vrae|apps|tests|infra)[/\\][A-Za-z0-9_./\\-]+\.py)$', path)
                if match:
                    module = match[1].replace("\\", "/")
                    if ".." not in module.split("/"):
                        frames.append({"module": module, "line": int(line), "method": method})
    return {"phase": phase, "exception_type": type(error).__name__,
            "original_exception_type": original_type, "original_method_locations": frames[-8:],
            "private_logs": logs, "private_text_published": False,
            "root_cause": "UNKNOWN_REQUIRES_PRIVATE_LOG_CORRELATION"}

def accept(label, minor):
    assert re.fullmatch("[a-z0-9-]{3,30}", label)
    assert minor == ".".join(map(str, sys.version_info[:2])), "S2_NATIVE_MINOR_REQUIRED"
    command(["git", "merge-base", "--is-ancestor", ACCEPTED_MAIN, "HEAD"])
    assert not command(["git", "status", "--porcelain", "--untracked-files=no"]).strip(), "S2_COMMIT_BEFORE_REAL_RUN"
    assert not command(["git", "diff", "--name-only", ACCEPTED_MAIN, "HEAD", "--",
                        "vrae", "apps", "db", "contracts", "industry-packs"]).strip()
    head = command(["git", "rev-parse", "HEAD"]).decode().strip()
    private = local_app.folder_for(label)
    outcome = {"source_sha":head,"accepted_main":ACCEPTED_MAIN,"minor":minor,"label":label,
        "scope":"S2_P2_INDUSTRIAL_SAME_TASK_STAGE_NOT_FULL_S2_EXIT","pass":False,
        "formal_human_gold":False,"external_delivery":False,"model_calls":0}
    saved: str | None = None
    error: BaseException | None = None
    secrets: set[bytes] = set()
    mounts: dict[str, dict] = {}
    phase = "original_local_app.start"
    failed_phase = None
    try:
        started, code = local_app.start(label, minor, False, workbench=True, l2_prepare=True)
        assert code == 0 and started["state"] == "STARTING"
        phase = "original_local_app.status_until_ready"
        deadline = time.monotonic()+300
        while True:
            state = local_app.status(label)
            if state["state"] == "M3_READY":
                break
            assert state["state"] == "STARTING", "S2_ORIGINAL_STARTUP_RED"
            assert time.monotonic() < deadline, "S2_ORCHESTRATION_START_DEADLINE"
            time.sleep(0.2)
        assert state["source_sha"] == head
        secrets.update(credentials(private))
        phase = "original_owned_pg_identity"
        _, saved = owned(private, label)
        observe_owned(label, private, mounts)
        paths = ["integration/l2_ops/s2_acceptance_sources.py", "integration/l2_ops/native_business.py",
                 "integration/l2_ops/native_tasks.py", "integration/l2_ops/s2_acceptance_journey.mjs",
                 "integration/l2_ops/s2_acceptance_runtime.py",
                 "integration/beta_review/codex3/m3_browser.mjs",
                 "integration/beta_review/codex3/m3_browser_run.py",
                 "integration/s2_buyer_workbench/workbench.py",
                 "integration/s2_buyer_workbench/buyer_cards.py", "vrae/reporting/s2_candidate.py",
                 "vrae/rules/s2/contract.py", "vrae/evidence/pack.py"]
        manifest = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
        (private/"s2-source-manifest.json").write_text(json.dumps(
            {"source_sha":head,"actual_working_bytes":manifest},indent=2),encoding="utf-8")
        phase = "original_snapshot.before_browser"
        snapshot(private, label, saved, "s2-before")
        phase = "original_browser.same_task"
        outcome["browser"] = browser(label, s2_l2=True)
        assert manifest == {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
        cleanup = json.loads((private/"browser-s2-l2/browser-process-cleanup.json").read_bytes())
        assert cleanup["exit_observed"], "S2_CHROME_EXIT_NOT_OBSERVED"
        outcome["chrome_cleanup"] = cleanup
        outcome["pass"] = True
    except BaseException as exc:
        error = exc
        failed_phase = phase
        outcome["failure_type"] = type(exc).__name__
        root = private if private.exists() else local_app.launch_for(label)
        root.mkdir(parents=True, exist_ok=True)
        (root/"s2-original-red.private.log").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        if private.exists():
            secrets.update(credentials(private))
        if saved:
            try:
                observe_owned(label, private, mounts)
                snapshot(private, label, saved, "s2-final" if outcome["pass"] else "s2-red")
            except BaseException as exc:
                failed_phase = failed_phase or "original_snapshot.final"
                error = error or exc
                outcome["pass"] = False
                outcome["snapshot_failure"] = type(exc).__name__
        try:
            local_app.request_stop(label)
            deadline = time.monotonic()+180
            while not (local_app.launch_for(label)/"supervisor-end.json").exists():
                assert time.monotonic() < deadline, "S2_OWNED_STOP_NOT_CONFIRMED"
                time.sleep(0.1)
            assert local_app.status(label)["state"] == "CLOSED"
            outcome["closed"] = True
            outcome["owned_cleanup"] = clean_recorded(mounts)
            (private/"s2-owned-cleanup.json").write_text(json.dumps(outcome["owned_cleanup"],indent=2),encoding="utf-8")
            pg_cleanup = json.loads((private/"l2-owned-cleanup.json").read_bytes())
            assert pg_cleanup["recorded_container_absent"] and pg_cleanup["recorded_pg_volumes_absent"]
        except BaseException as exc:
            failed_phase = failed_phase or "original_owned_teardown"
            error = error or exc
            outcome["pass"] = False
            outcome["cleanup_failure"] = type(exc).__name__
        assert command(["git", "rev-parse", "HEAD"]).decode().strip() == head
        if error is not None:
            outcome["first_failure"] = failure_receipt(private, label, failed_phase, error)
        public = publish(label, private, secrets, outcome)
    if error or not outcome["pass"]:
        raise RuntimeError("S2_ACTUAL_STAGE_RED_PRESERVED_"+str(public)) from None
    return {"source_sha":head,"status":"LOCAL_S2_STAGE_CANDIDATE_GOLD_PENDING",
            "evidence":str(public),"closed":True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--minor", choices=("3.11","3.13"), required=True)
    args = parser.parse_args()
    print(json.dumps(accept(args.run,args.minor)))


if __name__ == "__main__":
    main()
