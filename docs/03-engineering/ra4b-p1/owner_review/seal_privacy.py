"""Export only provenance descriptors and hashes; all expanded data stays private."""
import collections
import json
import subprocess

from privacy_inventory import BASE, HERE, ROOT, PRIVATE, sha


def main():
    semantic = json.loads((PRIVATE / "semantic-review.json").read_bytes())
    identifiers = json.loads((PRIVATE / "identifier-review.json").read_bytes())
    assert not semantic["secret_findings"] and not semantic["personal_home_path_files"]
    assert not semantic["non_null_fixture_lease_tokens_require_review"]
    assert len(identifiers["rows"]) == 5 and all(r["domain_class"] == "RESERVED_SYNTHETIC" for r in identifiers["rows"])
    assert semantic["binary_exact_matches"] == 148 and len(semantic["dump_checks"]) == 28
    assert set(h for values in semantic["fixture_source_hosts"].values() for h in values) == {"example.org"}
    protected = ["tests/reviewing/synthetic.py", "tests/reviewing/fixtures/404.json", "tests/reviewing/fixtures/200.json",
                 "integration/ra4a/p2a_support.py", "vrae/persistence/private_bytes.py", "vrae/persistence/contracts.py",
                 "integration/ra4a/test_recovery.py", "integration/ra4a/p2a/cases.py", "integration/ra4a/p2b1/cases.py",
                 "db/migrations/0001_ra4a_test_only.sql", "db/migrations/0002_ra4a_private_bytes.sql", "db/migrations/0003_ra4a_test_review_cas.sql"]
    source = []
    for name in protected:
        blob = subprocess.check_output(["git", "rev-parse", BASE + ":" + name], cwd=ROOT).decode().strip()
        raw = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT)
        assert raw.replace(b"\r\n", b"\n") == (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
        source.append({"path": name, "baseline_git_blob": blob, "lf_sha256": sha(raw.replace(b"\r\n", b"\n")), "unchanged": True})
    inventory = [{k: r[k] for k in ("path", "sha256", "bytes", "path_class", "provenance")} for r in semantic["inventory"]]
    reviewed_text = {".log": "CAPTURED_TEST_SUBPROCESS_OPERATIONAL_LOG_TEXT_AND_INPUT_PROVENANCE_REVIEWED",
        ".json": "TEST_CATALOG_MANIFEST_RESULT_OR_HASH_METADATA_TEXT_AND_INPUT_PROVENANCE_REVIEWED",
        ".jsonl": "TEST_SQL_OR_AUDIT_EVENT_METADATA_TEXT_AND_INPUT_PROVENANCE_REVIEWED",
        ".xml": "NATIVE_TEST_JUNIT_WITH_RESERVED_SYNTHETIC_PARAMETERS_AND_REAL_OPERATIONAL_METADATA",
        ".md": "AUTHOR_WRITTEN_B4_TECHNICAL_DECISION_DOCUMENT", ".diff": "B4_TECHNICAL_REPAIR_DIFF",
        ".txt": "B4_TECHNICAL_SQL_DIAGNOSTIC_SOURCE", "configuration": "B4_EVIDENCE_GIT_ATTRIBUTES_OR_IGNORE_RULES"}
    for row in inventory:
        if row["provenance"] == "B4_CAPTURED_TEST_OPERATIONAL_EVIDENCE_REQUIRES_TEXT_REVIEW":
            row["provenance"] = reviewed_text[row["path_class"]]
    classes = collections.Counter(r["path_class"] for r in inventory)
    assert classes[".dump"] == 28 and classes[".bin"] == 148 and classes[".log"] == 645 and len(inventory) == 1553
    out = HERE / "owner_review/privacy"
    out.mkdir(exist_ok=True)  # Regenerates only this new descriptor-only report, never original evidence.
    (out / "BASELINE_PATH_SHA_SIZE.json").write_text(json.dumps({"baseline": BASE, "files": inventory}, indent=2))
    report = {"status": "BASELINE_SYNTHETIC_BUSINESS_PAYLOAD_PROVENANCE_VERIFIED_NO_SECRET_OR_CLIENT_DATA_FOUND",
        "owner_comment": 6856220858, "baseline": BASE, "file_count": len(inventory), "classes": dict(classes),
        "method_is_not_pattern_scan_only": ["baseline Git-object inventory", "148 byte-identical regenerated fixture artifacts",
            "all28 archives offline pg_restore --file expansion without a database connection", "all COPY headers/rows parsed including quoted identifiers",
            "387 graph objects match independent frozen factories", "15 exact generated proposals", "15 schema/row-bound TEST_ONLY receipts",
            "closed synthetic tenants/actors and absence of auth catalog/password DDL", "text + expanded SQL private-password fingerprint and sensitive-pattern audit",
            "five email-like identifiers individually traced to reserved example domains", "original producer code/fixture Git blob verification"],
        "source_provenance": source, "representative_safe_proof": semantic["representatives"],
        "text_producer_boundaries": ["integration/ra4a/conftest.py records native test IDs/outcomes and catalog queries only",
            "integration/ra4a/p2a_plugin.py exports independently held fixed graph artifacts",
            "B4 runtime_lab.command/run_full.stage/regression.stage capture only owned synthetic test subprocesses",
            "runtime_check request logging omits Authorization/configuration and records bounded synthetic source/status receipts",
            "runtime state/config credentials enter owned processes privately, never as a collected business source",
            "PUBLIC_EVIDENCE_VIEWS retains exact private originals and hashes for the pre-push secret/home redactions"],
        "COPY_row_counts": semantic["COPY_rows"], "bytea_provenance_counts": semantic["bytea_provenance"],
        "dump_details": semantic["dump_checks"],
        "email_identifier_review": identifiers["rows"],
        "known_original_private_password_fingerprints_checked": semantic["private_original_password_values_checked"],
        "actual_secret_matches": 0, "personal_home_path_matches": 0, "non_null_fixture_lease_tokens": 0,
        "fixture_source_hosts": semantic["fixture_source_hosts"],
        "operational_metadata": {"description": "Real test timestamps, Python/PG versions, TEST_ONLY role names, UUIDs and machine labels are execution metadata, not synthetic business content or real-person authority.",
            "existing_junit_machine_labels": [{"label_sha256": sha(name.encode()), "occurrences": count} for name, count in semantic["operational_junit_hostname_counts"].items()]},
        "retention_proposal": {"original_RED_and_first_push_preserved": True, "history_rewrite": False,
            "new_raw_dump_or_byte_graph_publication": False, "future_raw_output": "private ignored local output or ephemeral CI workspace",
            "future_public_output": "sanitized JUnit, bounded stage/error classification, selected catalog metadata and SHA/size receipts",
            "existing_synthetic_raw_archive_removal": "Deferred to Owner archive decision; no silent deletion or force push."}}
    (out / "PROVENANCE_AUDIT.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"status": report["status"], "baseline_files": len(inventory), "new_raw_files": 0}))


if __name__ == "__main__":
    main()
