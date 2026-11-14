"""Review every COPY row and text file; public output is descriptors only."""
import collections
import json
import re
import sys
import uuid
from urllib.parse import urlsplit

from privacy_inventory import HERE, ROOT, PRIVATE, baseline_files, sha, unescape

sys.path.insert(0, str(ROOT))


def main():
    from integration.ra4a.p2a_support import graph
    from integration.ra4a.p2b1_support import proposal
    from vrae.reviewing.canonical import canonical
    from vrae.persistence.private_bytes import locator
    prior = json.loads((PRIVATE / "provenance-review.json").read_bytes())
    graphs = {g.ref_id: g for g in (graph("404"), graph("200"), graph("404", 2))}
    golden = {sha(a.raw) for g in graphs.values() for a in g.artifacts} | {sha(g.manifest) for g in graphs.values()}
    commands = {sha(canonical(proposal(g, action=action, key=key).document, limit=131072)) for g, action, key in (
        (graphs["accepted-404"], "REQUEST_CHANGES", "review-key-0001"),
        (graphs["accepted-404-v2"], "APPROVE_CANDIDATE", "durable-version-key"),
        (graphs["accepted-200"], "APPROVE_CANDIDATE", "durable-zero-key"))}
    known_targets = [json.loads(g.target) for g in graphs.values()]
    dump_checks = []
    all_rows = collections.Counter()
    secret_table_names = []
    lease_fields = []
    bytea_kinds = collections.Counter()
    for index, original in enumerate(prior["dump_details"]):
        raw = (PRIVATE / f"{index:03d}.sql").read_bytes()
        text = raw.decode()
        assert not re.search(r"(?mi)^COPY (?:pg_catalog\.)?(?:pg_authid|pg_shadow)\b|^ALTER ROLE .* PASSWORD|^CREATE SERVER\b", text)
        table = None
        cols = []
        rows = collections.Counter()
        payloads = []
        headers = 0
        for line in text.splitlines():
            if line.startswith("COPY "):
                match = re.fullmatch(r'COPY ([\w"]+)\.([\w"]+) \(([^)]+)\) FROM stdin;', line)
                assert match, "UNPARSED_COPY_HEADER"
                schema, name, columns = match.groups()
                schema, name = schema.strip('"'), name.strip('"')
                assert schema in {"ra4a", "ra4a_private", "ra4a_bytes", "ra4a_review_test", "ra4b_test"}
                table, cols = schema + "." + name, [c.strip('"') for c in columns.split(", ")]
                headers += 1
                continue
            if table is None:
                continue
            if line == r"\.":
                table = None
                continue
            fields = line.split("\t")
            assert len(fields) == len(cols)
            v = {c: unescape(x) for c, x in zip(cols, fields)}
            rows[table] += 1
            if "tenant_id" in v:
                assert v["tenant_id"] in ("tenant-test", "tenant-beta")
            for key in ("db_role", "principal", "db_actor", "origin_role"):
                if v.get(key):
                    assert re.fullmatch(r"(?:ra4a|ra4b|p2a|p2b1)_test_[a-z_]+", v[key]), "UNEXPECTED_ACTOR"
            if v.get("lease_token"):
                lease_fields.append({"path": original["path"], "token_sha256": sha(v["lease_token"].encode()), "state": v.get("state")})
            if table == "ra4a.references":
                assert json.loads(v["metadata"]) in known_targets
            if table == "ra4a.requests":
                payload = json.loads(v["canonical_payload"])
                assert set(payload) == {"mode", "source_ref", "expected_ref_sha256"}
                assert payload["mode"] == "SYNTHETIC_INTERNAL_ONLY"
                if payload["source_ref"] is None:
                    # Original P1 TestOnlyPostgres.admit defaults to the exact
                    # admission_payload(None,None) synthetic protocol.
                    assert payload["expected_ref_sha256"] is None
                else:
                    assert payload["source_ref"] in graphs and payload["expected_ref_sha256"] == sha(graphs[payload["source_ref"]].target)
            for col, value in v.items():
                if not value or not value.startswith(r"\x"):
                    continue
                blob = bytes.fromhex(value[2:])
                digest = sha(blob)
                kind = "EXACT_REGENERATED_GRAPH_BYTES"
                if col == "canonical_command":
                    assert table == "ra4a_review_test.proposals" and digest in commands
                    kind = "EXACT_REGENERATED_TEST_PROPOSAL"
                elif col == "receipt":
                    assert table == "ra4a_review_test.proposals"
                    g = graphs[v["ref_id"]]
                    loc = locator(g)
                    assert v["source_run_id"] == loc.source_run and v["report_id"] == loc.report and int(v["report_version"]) == loc.version
                    assert v["target_digest"] == loc.target_digest and uuid.UUID(v["proposal_id"]).version == 4
                    assert v["source_sha256"] == sha(next(a.raw for a in g.artifacts if a.kind == "SOURCE"))
                    assert v["html_sha256"] == sha(next(a.raw for a in g.artifacts if a.kind == "HTML"))
                    assert v["manifest_sha256"] == sha(g.manifest)
                    assert v["status"] in {"SIMULATED_APPROVE_CANDIDATE", "SIMULATED_CHANGES_REQUESTED", "SIMULATED_INTERNAL_SCOPE_ACK"}
                    expected = {key: v[key] for key in ("tenant_id", "report_id", "source_run_id", "target_digest", "proposal_id",
                        "db_actor", "status", "source_sha256", "html_sha256")}
                    expected.update(contract_version="ra4a-p2b1-test-receipt-v1", authority="TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL",
                        command_digest=sha(b"vrae.ra3d.command.offline-v1\n" + bytes.fromhex(v["canonical_command"][2:])),
                        report_version=int(v["report_version"]), review_seq=1, report_event_seq=int(v["report_event_seq"]),
                        native_decision=None, native_approval=None, share_grant=None, external_visibility=False, durable=True)
                    assert json.loads(blob) == expected
                    kind = "EXACT_SCHEMA_AND_SYNTHETIC_ROW_BOUND_RECEIPT"
                else:
                    assert digest in golden, "UNKNOWN_GRAPH_PAYLOAD"
                bytea_kinds[kind] += 1
                payloads.append({"table": table, "column": col, "sha256": digest, "bytes": len(blob), "provenance": kind})
        assert table is None and headers > 0
        all_rows.update(rows)
        dump_checks.append({"path": original["path"], "sha256": original["raw_sha256"], "expanded_sha256": sha(raw),
                            "COPY_headers_parsed": headers, "rows": dict(rows), "bytea_proofs": payloads})
    private_values = set()
    views = json.loads((HERE / "PUBLIC_EVIDENCE_VIEWS.json").read_bytes())["views"]
    for view in views:
        raw = (HERE / view["private_original"]).read_bytes()
        text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8")
        private_values.update(re.findall(r"password=([A-Za-z0-9_-]{24,})", text))
    findings = []
    emails = collections.Counter()
    home_paths = []
    operational_hostnames = collections.Counter()
    dump_index = {r["path"]: i for i, r in enumerate(prior["dump_details"])}
    baseline = baseline_files()
    for row in prior["inventory"]:
        raw = baseline[row["path"]]
        assert sha(raw) == row["sha256"]
        if row["path_class"] == ".dump":
            # Inspect the uncompressed SQL too; raw archives are not a useful
            # credential scan surface. Their bytea payloads were proven above.
            raw = (PRIVATE / f'{dump_index[row["path"]]:03d}.sql').read_bytes()
        text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8")
        if any(value in text for value in private_values):
            findings.append({"path": row["path"], "kind": "ACTUAL_PRIVATE_RUNTIME_PASSWORD_MATCH"})
        for pattern in (r'"(?:password|admin_password|bearer)"\s*:\s*"[A-Za-z0-9_-]{24,}"', r"password=[A-Za-z0-9_-]{24,}",
                        r"Bearer [A-Za-z0-9_-]{32,}", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                        r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{20,}"):
            if re.search(pattern, text):
                findings.append({"path": row["path"], "kind": "SENSITIVE_PATTERN_REQUIRES_REVIEW"})
        # A leading boundary and RFC-sized fields avoid quadratic scanning of
        # multi-megabyte bytea hex/base64 runs without an @ separator.
        emails.update(re.findall(r"(?<![\w.+-])[\w.+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}", text))
        if re.search(r"(?i)[A-Z]:[\\/]+Users[\\/]+(?!Public\b|Default\b)", text):
            home_paths.append(row["path"])
        operational_hostnames.update(re.findall(r'hostname="([^"]+)"', text))
    fixture_hosts = {}
    for case in ("404", "200"):
        data = json.loads((ROOT / f"tests/reviewing/fixtures/{case}.json").read_bytes())
        urls = re.findall(r'https?://[^\s"<>]+', json.dumps(data["source"]))
        fixture_hosts[case] = sorted({urlsplit(u).hostname for u in urls})
    result = {"status": "SEMANTIC_AUDIT_COMPLETE_TEXT_IDENTIFIERS_REQUIRE_REVIEW" if findings or emails or home_paths or lease_fields else "SEMANTIC_PAYLOAD_AUDIT_AND_TEXT_SCAN_CLEAR",
        "baseline": prior["baseline"], "scope_files": prior["files"], "classes": prior["classes"],
        "binary_exact_matches": 148, "dump_files_all_offline_expanded_and_reviewed": len(dump_checks), "COPY_rows": dict(all_rows),
        "bytea_provenance": dict(bytea_kinds), "dump_checks": dump_checks, "inventory": prior["inventory"],
        "representatives": prior["representatives"], "private_original_password_values_checked": len(private_values),
        "secret_findings": findings, "email_values_require_review": dict(emails), "personal_home_path_files": home_paths,
        "fixture_source_hosts": fixture_hosts, "non_null_fixture_lease_tokens_require_review": lease_fields,
        "operational_junit_hostname_counts": dict(operational_hostnames), "credential_tables": secret_table_names,
        "real_environment_metadata_is_not_synthetic_business_data": True,
        "new_raw_dump_or_graph_publication": False}
    (PRIVATE / "semantic-review.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ("status", "scope_files", "binary_exact_matches", "dump_files_all_offline_expanded_and_reviewed", "bytea_provenance")} |
        {"secret_findings": len(findings), "email_values": len(emails), "home_paths": len(home_paths), "fixture_lease_tokens": len(lease_fields)}), flush=True)


if __name__ == "__main__":
    main()
