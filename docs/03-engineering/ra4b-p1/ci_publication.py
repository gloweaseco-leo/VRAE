"""Curated metadata/JUnit only, including truthful bounded failure diagnostics."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from integration.ra4b.evidence import PREFIX, console_stage, sanitized_junit  # noqa: E402

PATTERNS = (r"password=[A-Za-z0-9_-]{24,}", r"Bearer [A-Za-z0-9_-]{32,}",
            r'"(?:password|admin_password|bearer)"\s*:\s*"[A-Za-z0-9_-]{24,}"',
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}")
CATALOG_KEYS = {"migrations", "server_version", "roles", "tables", "policies", "grants", "functions", "github_checkout",
                "synthetic_authority_only", "actual_human_approvals", "share_grants"}
B4_CATALOG_KEYS = {"functions", "triggers", "original_policies", "roles", "projection_rls", "actual_sessions", "raw_table_acl",
                   "memberships", "legacy_raw_select_debt"}
RUNTIME_FILES = {"network.json", "output-access.json", "http-authority-negatives.json", "http-commit-expiry.json",
    "http-parser-bounds.json", "durable-runtime.json", "accepted-sources-runtime.json", "receipts.json", "dead-letter.json",
    "lost-response.json", "db-down-result.json", "recovery.json", "runtime-result.json"}
CONTROL_FILES = {"result.json", "stages.json", "credential-scan.json", "teardown.json", "source-integrity.json",
    "source-volume-cleanup.json", "runtime-credential-scan.json", "container-result.json", "unit-stage-result.json", "runtime-stage-result.json"}
FORBIDDEN_KEYS = {"password", "admin_password", "runtime_passwords", "bearer", "lease_token", "private_key", "raw", "html",
                  "document", "payload", "canonical_payload", "canonical_command", "objects_base64", "source_bytes"}
STAGE_NAMES = {"pg1", "pg2-before-0004", "pg2-after-0004", "p2a", "p2b1", "identity-pg", "crypto"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def metadata_view(value, key=""):
    """Known-producer metadata: numbers, flags, hashes, IDs and closed enums."""
    if key in FORBIDDEN_KEYS:
        raise ValueError("RAW_OR_SECRET_FIELD_NOT_PUBLIC_METADATA")
    if key in {"native_approval", "native_decision", "share_grant"} and value is not None:
        raise ValueError("REAL_AUTHORITY_FIELD_NOT_PUBLIC_METADATA")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        return [metadata_view(v, key) for v in value]
    if isinstance(value, dict):
        if any(not re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", k) for k in value):
            raise ValueError("UNEXPECTED_METADATA_KEY")
        return {k: metadata_view(v, k) for k, v in value.items()}
    if not isinstance(value, str):
        raise ValueError("UNEXPECTED_METADATA_TYPE")
    if key == "python":
        if not re.fullmatch(r"[0-9][^\r\n]{0,255}", value):
            raise ValueError("UNEXPECTED_PYTHON_VERSION")
    elif key in {"container", "network", "data_volume", "volume", "name", "volumes"}:
        if not re.fullmatch(r"vrae-[a-zA-Z0-9-]{1,100}", value):
            raise ValueError("UNEXPECTED_OWNED_RESOURCE_NAME")
    elif key == "source_ref":
        if value not in {"accepted-404", "accepted-200"}:
            raise ValueError("UNEXPECTED_SOURCE_REFERENCE")
    elif key == "output_mode":
        if not re.fullmatch(r"0o[0-7]{3}", value):
            raise ValueError("UNEXPECTED_OUTPUT_MODE")
    elif key == "exception_type":
        if value not in {"PermissionError", "FileNotFoundError", "OSError", "AssertionError", "CalledProcessError", "TimeoutExpired", "RuntimeError", "ValueError", "TypeError", "KeyError"}:
            raise ValueError("UNEXPECTED_EXCEPTION_CLASS")
    elif key == "deferred_ids":
        return "native-id-sha256:" + digest(value.encode())
    elif key == "sqlstates":
        if not re.fullmatch(r"[0-9A-Z]{5}", value):
            raise ValueError("UNEXPECTED_SQLSTATE")
    elif key == "crc32":
        if not re.fullmatch(r"[a-f0-9]{8}", value):
            raise ValueError("UNEXPECTED_NATIVE_XML_CRC32")
    elif not (re.fullmatch(r"[A-Z][A-Z0-9_]{0,159}", value) or re.fullmatch(r"[a-f0-9]{64}", value)
              or re.fullmatch(r"[a-f0-9-]{36}", value) or value in {"lo", "claim", "finish", "worker", "admin", "exited", "container", "network", "volume"}
              or key == "events" and value in {"worker_commit", "admin_commit", "admin_rollback"}
              or key == "stage" and value in STAGE_NAMES):
        raise ValueError("UNEXPECTED_METADATA_STRING")
    return value


def source_view(value):
    rows = value if isinstance(value, list) else value["source"]
    result = []
    for row in rows:
        name = PurePosixPath(row["path"])
        assert not name.is_absolute() and ".." not in name.parts
        result.append({"path": name.as_posix(), **{k: row[k] for k in ("sha256", "lf_sha256") if re.fullmatch(r"[a-f0-9]{64}", row[k])}})
    projected = {"kind": "PUBLIC_SOURCE_PATH_HASH_MANIFEST_NO_SOURCE_BYTES", "files": result}
    if isinstance(value, dict) and re.fullmatch(r"sha256:[a-f0-9]{64}", value.get("image_id", "")):
        projected["image_id"] = value["image_id"]
    return projected


def harness_junit(records, blockers):
    root = ET.Element("testsuites", name="B4_HARNESS_STAGES_NOT_ORDINARY_TEST_SUBSTITUTES")
    errors = len(blockers) + sum(r.get("status") != "PASS" for r in records)
    suite = ET.SubElement(root, "testsuite", name="harness", tests=str(len(records) + len(blockers)), errors=str(errors))
    for record in records:
        entry = ET.SubElement(suite, "testcase", classname="ra4b.harness", name=record.get("phase", "UNKNOWN") + "_" + record["stage"])
        if record.get("status") != "PASS":
            ET.SubElement(entry, "error", message=record.get("exception_type", "FAILED_STAGE"))
    for index, blocker in enumerate(blockers):
        case = ET.SubElement(suite, "testcase", classname="ra4b.harness", name="BLOCKED_" + str(index))
        ET.SubElement(case, "error", message=blocker["reason"]).text = "See bounded publication.json; raw diagnostics remain non-public."
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main(slug, *, evidence_root=HERE, output_dir=None):
    assert slug in ("311", "313")
    base = Path(evidence_root)
    output = Path(output_dir) if output_dir else base / ("ci-public-" + slug)
    output.mkdir(exist_ok=False)
    phases = [base / ("ci-" + name + "-" + slug) for name in ("pg", "unit", "runtime")]
    blockers, ledger, counts, retained, stages = [], [], {}, [], []
    for phase in phases:
        kind = phase.name.split("-")[1]
        result = phase / "result.json"
        required = {"pg": "PG_AND_FROZEN_PRELUDE_PASS_NOT_FINAL_RUNTIME_PASS",
                    "unit": "ORDINARY_PASS_SEPARATE_ISOLATED_GATES_REQUIRED", "runtime": "PASS"}[kind]
        if not result.exists() or json.loads(result.read_bytes()).get("status") != required:
            blockers.append({"phase": phase.name, "reason": "INCOMPLETE_OR_FAILED_GATE"})
        teardown = phase / "teardown.json" if kind == "unit" else phase / "teardown/teardown.json"
        owned = {"owned_container_removed", "owned_volume_removed"} | ({"owned_network_removed"} if kind != "unit" else set())
        if not teardown.exists() or not all(json.loads(teardown.read_bytes()).get(k) is True for k in owned):
            blockers.append({"phase": phase.name, "reason": "OWNED_CLEANUP_CLEARANCE_MISSING"})
        if kind in {"pg", "runtime"}:
            scan = phase / "credential-scan.json"
            if not scan.exists() or json.loads(scan.read_bytes()).get("matches") != 0:
                blockers.append({"phase": phase.name, "reason": "ACTUAL_CREDENTIAL_CLEARANCE_MISSING"})
        state = phase / "container-result.json"
        if state.exists() and (json.loads(state.read_bytes()).get("exit") != 0 or json.loads(state.read_bytes()).get("oom_killed")):
            blockers.append({"phase": phase.name, "reason": "ACTUAL_CONTAINER_EXIT_NONZERO_OR_OOM"})
        for path in sorted(phase.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(base).as_posix()
            if path.is_symlink() or not path.resolve().is_relative_to(phase.resolve()):
                blockers.append({"path": relative, "reason": "UNSAFE_OUTPUT_PATH"})
                continue
            raw = path.read_bytes()
            ledger.append({"path": relative, "sha256": digest(raw), "bytes": len(raw)})
            try:
                text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8")
            except UnicodeError:
                text = ""
            sensitive = any(re.search(pattern, text) for pattern in PATTERNS)
            if sensitive:
                blockers.append({"path": relative, "reason": "SENSITIVE_PATTERN_RAW_PUBLICATION_DENIED"})
            public, view_kind = None, None
            if path.suffix == ".xml":
                public, native = sanitized_junit(raw)
                counts[relative] = native
                if native["failures"] or native["errors"]:
                    blockers.append({"path": relative, "reason": "ORIGINAL_NATIVE_JUNIT_FAILED"})
                if kind != "unit" and native["skipped"]:
                    blockers.append({"path": relative, "reason": "UNEXPECTED_NATIVE_SKIP_OUTSIDE_ORDINARY_SUITE"})
                view_kind = "SANITIZED_NATIVE_JUNIT_OUTCOMES_PRESERVED"
            elif path.suffix == ".json" and not sensitive:
                value = json.loads(raw)
                try:
                    if path.name == "source.json":
                        value = source_view(value)
                    elif path.name == "pg-catalog-and-calls.json":
                        value = {k: v for k, v in value.items() if k in CATALOG_KEYS}
                    elif path.name == "b4-catalog.json":
                        value = {k: v for k, v in value.items() if k in B4_CATALOG_KEYS}
                    elif path.name == "migration-compat.json":
                        value = {k: v for k, v in value.items() if k in {"old_policies", "p2a_schema_sha256_unchanged", "epoch_rows_at_fresh_bootstrap", "initialization"}}
                    elif path.name == "native-junit-retention.json":
                        # Publish the actual post-cleanup SHA/CRC and counts;
                        # raw testcase parameter IDs remain private.
                        value = metadata_view({k: v for k, v in value.items() if k in {
                            "status", "sha256", "crc32", "bytes", "cases", "passed", "skipped",
                            "failed", "errors", "qa_passed", "review_passed", "raw_xml_private",
                            "stdout_used_to_construct_xml"}})
                    elif path.name in CONTROL_FILES or path.name in RUNTIME_FILES or path.name.startswith("epoch-order-") or path.name in {"two-workers-claim.json", "two-workers-finish.json"}:
                        value = metadata_view(value)
                    else:
                        continue
                    public = (json.dumps(value, indent=2) + "\n").encode()
                    view_kind = "EXPLICIT_KNOWN_PRODUCER_METADATA_VIEW"
                    if path.name.endswith("stage-result.json"):
                        stage = console_stage(value)
                        stages.append(stage)
                        if stage.get("status") == "FAIL":
                            blockers.append({"phase": phase.name, "reason": "ACTUAL_STAGE_FAILED"})
                except (ValueError, TypeError, KeyError):
                    blockers.append({"path": relative, "reason": "UNRECOGNIZED_PUBLIC_METADATA_SCHEMA"})
            elif path.name == "supervisor.stdout.log":
                for line in text.splitlines():
                    if line.startswith(PREFIX):
                        try:
                            stage = console_stage(json.loads(line[len(PREFIX):]))
                            stages.append(stage)
                            if stage.get("status") == "FAIL":
                                blockers.append({"phase": phase.name, "reason": "ACTUAL_STAGE_FAILED"})
                        except (ValueError, TypeError):
                            blockers.append({"path": relative, "reason": "MALFORMED_BOUNDED_STAGE_RESULT"})
            if public is not None:
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(public)
                retained.append({"path": relative, "kind": view_kind, "raw_sha256": digest(raw), "public_sha256": digest(public)})
    stages = list({json.dumps(r, sort_keys=True): r for r in stages}.values())
    blockers = list({json.dumps(r, sort_keys=True): r for r in blockers}.values())
    report = {"status": "FAILED_GATES_WITH_SANITIZED_DIAGNOSTICS" if blockers else "CLEARED_CURATED_METADATA_AND_JUNIT",
        "blockers": blockers, "native_junit_counts": counts, "raw_source_sha256": ledger, "public_views": retained,
        "bounded_stage_results": stages, "raw_dump_byte_graph_log_copies": 0,
        "raw_error_text_not_public": True, "original_raw_available": "LOCAL_PRIVATE_OR_EPHEMERAL_CI_WORKSPACE_ONLY",
        "gate": "B4_P1_CANDIDATE_NOT_G1_EXIT", "real_human_approvals": 0, "share_grants": 0}
    (output / "publication.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "harness-stages.xml").write_bytes(harness_junit(stages, blockers))
    print(json.dumps({"publication": report["status"], "blockers": len(blockers), "curated_files": len(retained)}))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
