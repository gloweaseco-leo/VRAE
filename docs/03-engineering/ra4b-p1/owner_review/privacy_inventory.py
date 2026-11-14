"""Audit the already-public baseline; never publish new raw data or dump bytes."""
import collections
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import uuid

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
PRIVATE = HERE / ".runtime/owner-review/privacy"
BASE = "ae628003b4aa9f18054cb79fba5db60fefb02b3d"
sys.path.insert(0, str(ROOT))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def baseline_files():
    child = subprocess.Popen(["git", "-c", "core.autocrlf=false", "archive", BASE, "--",
                              "docs/03-engineering/ra4b-p1"], cwd=ROOT, stdout=subprocess.PIPE)
    with tarfile.open(fileobj=child.stdout, mode="r|") as package:
        files = {member.name: package.extractfile(member).read() for member in package if member.isfile()}
    assert child.wait() == 0
    return files


def unescape(value):
    if value == r"\N":
        return None
    chars = {"t": "\t", "n": "\n", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "\\": "\\"}
    return re.sub(r"\\(\\|t|n|r|b|f|v|[0-7]{1,3})", lambda m: chars.get(m[1], chr(int(m[1], 8)) if m[1].isdigit() else m[1]), value)


def main():
    PRIVATE.mkdir(parents=True, exist_ok=False)
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE, "--", "docs/03-engineering/ra4b-p1"]).decode().splitlines()
    files = baseline_files()
    from integration.ra4a.p2a_support import graph
    golden = {}
    examples = []
    for case, version in (("404", 1), ("200", 1), ("404", 2)):
        g = graph(case, version)
        for artifact in g.artifacts:
            golden.setdefault(sha(artifact.raw), []).append({"fixture": case, "version": version, "kind": artifact.kind, "key": artifact.key})
        golden.setdefault(sha(g.manifest), []).append({"fixture": case, "version": version, "kind": "MANIFEST"})
        d = json.loads(next(a.raw for a in g.artifacts if a.kind == "DRAFT"))
        examples.append({"fixture": case, "version": version, "private": d["private"], "shareable": d["shareable"],
                         "approval_status": d["approval_status"], "issue_count": len(d["issues"]),
                         "producer": "tests/reviewing/synthetic.py::inputs -> p2a_support.graph -> private_bytes.assemble"})
    inventory = []
    dumps = []
    bin_bad = []
    for name in paths:
        path = ROOT / name
        raw = files[name]
        digest = sha(raw)
        suffix = path.suffix
        provenance = "B4_CAPTURED_TEST_OPERATIONAL_EVIDENCE_REQUIRES_TEXT_REVIEW"
        row = {"path": name, "sha256": digest, "bytes": len(raw), "path_class": suffix or "configuration"}
        if suffix == ".bin":
            provenance = "EXACT_REGENERATED_FROZEN_SYNTHETIC_GRAPH_BYTES"
            row["golden_matches"] = golden.get(digest, [])
            if not row["golden_matches"]:
                bin_bad.append(name)
        elif suffix == ".dump":
            provenance = {"synthetic-metadata.dump": "integration/ra4a/test_recovery.py::test_pg_dump_restore_retains_data_owners_rls_and_idempotency",
                "private-bytes.dump": "integration/ra4a/p2a/cases.py::test_real_dump_restore_and_volume_restart_original_bytes_latest_version",
                "test-review-ledger.dump": "integration/ra4a/p2b1/cases.py::test_b25_real_dump_restore_restart_receipts_state_audit_outbox"}[path.name]
            assert raw.startswith(b"PGDMP")
            dumps.append(row)
        elif suffix == ".py":
            provenance = "B4_TEST_HARNESS_SOURCE"
        row["provenance"] = provenance
        inventory.append(row)
    (PRIVATE / "initial-inventory.json").write_text(json.dumps(inventory, indent=2))
    assert not bin_bad, "UNKNOWN_BINARY_PROVENANCE_STOP"
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as package:
        for i, row in enumerate(dumps):
            raw = files[row["path"]]
            info = tarfile.TarInfo(f"{i:03d}.dump")
            info.size = len(raw)
            package.addfile(info, io.BytesIO(raw))
    image = (ROOT / "infra/ra4a/image.txt").read_text().strip()
    ident = "vrae-ra4b-privacy-" + uuid.uuid4().hex[:12]
    script = 'mkdir -p /tmp/input /tmp/sql; tar -xf - -C /tmp/input; for f in /tmp/input/*.dump; do n=${f##*/}; pg_restore --file=/tmp/sql/${n%.dump}.sql "$f" || exit 1; done; tar -cf - -C /tmp/sql .'
    command = ["docker", "run", "--rm", "-i", "--name", ident, "--label", "vrae.ra4b.privacy=TEST_ONLY_OFFLINE_AUDIT",
        "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", "512m", "--cpus", "1", "--pids-limit", "64", "--tmpfs", "/tmp:rw,nosuid,nodev,size=128m",
        "--entrypoint", "/bin/sh", image, "-c", script]
    child = subprocess.run(command, input=archive.getvalue(), capture_output=True, timeout=300)
    (PRIVATE / "offline-expand.stderr.log").write_bytes(child.stderr)
    child.check_returncode()
    expanded = {}
    with tarfile.open(fileobj=io.BytesIO(child.stdout)) as package:
        for member in package:
            if member.isfile():
                raw = package.extractfile(member).read()
                target = PRIVATE / Path(member.name).name
                assert target.suffix == ".sql"
                target.write_bytes(raw)
                expanded[target.stem] = raw
    allowed = {"ra4a", "ra4a_private", "ra4a_bytes", "ra4a_review_test", "ra4b_test"}
    unknown = []
    details = []
    for i, row in enumerate(dumps):
        raw = expanded[f"{i:03d}"]
        text = raw.decode()
        table_counts = collections.Counter()
        bytea = []
        table = None
        columns = []
        for line in text.splitlines():
            match = re.match(r'COPY ([\w"]+)\.([\w"]+) \(([^)]+)\) FROM stdin;', line)
            if match:
                schema, table, cols = match.groups()
                schema, table = schema.strip('"'), table.strip('"')
                assert schema in allowed
                columns = [c.strip('"') for c in cols.split(", ")]
                table = schema + "." + table
                continue
            if table is None:
                continue
            if line == r"\.":
                table = None
                continue
            fields = line.split("\t")
            assert len(fields) == len(columns)
            values = {c: unescape(v) for c, v in zip(columns, fields)}
            table_counts[table] += 1
            if "tenant_id" in values and values["tenant_id"] not in ("tenant-test", "tenant-beta"):
                unknown.append({"path": row["path"], "table": table, "field": "tenant_id", "value_sha256": sha(values["tenant_id"].encode())})
            for col, value in values.items():
                if value and value.startswith(r"\x"):
                    blob = bytes.fromhex(value[2:])
                    digest = sha(blob)
                    entry = {"table": table, "column": col, "sha256": digest, "bytes": len(blob), "golden_matches": golden.get(digest, [])}
                    if not entry["golden_matches"]:
                        unknown.append({"path": row["path"], "table": table, "field": col, "blob_sha256": digest})
                    bytea.append(entry)
        details.append({"path": row["path"], "raw_sha256": row["sha256"], "expanded_sql_sha256": sha(raw),
                        "producer": row["provenance"], "copy_table_rows": dict(table_counts), "bytea": bytea})
    report = {"status": "PROVENANCE_EXPANSION_REQUIRES_REVIEW" if unknown else "BINARY_AND_DUMP_PAYLOADS_MATCH_SYNTHETIC_FACTORIES_TEXT_AUDIT_PENDING",
        "baseline": BASE, "classes": dict(collections.Counter(r["path_class"] for r in inventory)), "files": len(inventory),
        "bin_count": sum(r["path_class"] == ".bin" for r in inventory), "dump_count": len(dumps), "unknown": unknown,
        "representatives": examples, "offline_only_no_database_connection": True, "dump_details": details,
        "new_raw_outputs": "PRIVATE_IGNORED_ONLY", "inventory": inventory}
    (PRIVATE / "provenance-review.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("status", "files", "bin_count", "dump_count")} | {"unknown_payloads": len(unknown)}), flush=True)


if __name__ == "__main__":
    main()
