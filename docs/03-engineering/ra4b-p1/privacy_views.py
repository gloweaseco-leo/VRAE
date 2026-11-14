"""Public views retain outcomes; exact private originals are sealed, never erased."""

import hashlib
import json
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "PUBLIC_EVIDENCE_VIEWS.json"
PRIVATE = HERE / ".runtime" / "original-evidence"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    previous = json.loads(LEDGER.read_bytes()) if LEDGER.exists() else {"views": []}
    entries = {r["public_path"]: r for r in previous["views"]}
    changed = 0
    homes = {os.environ.get("USERPROFILE", "")} - {""}
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or ".runtime" in path.parts or "__pycache__" in path.parts or path == LEDGER:
            continue
        if path.suffix not in (".json", ".jsonl", ".xml", ".log", ".md", ".diff", ".txt"):
            continue
        name = path.relative_to(HERE).as_posix()
        raw = path.read_bytes()
        if name in entries and entries[name]["public_sha256"] == digest(raw):
            assert digest((HERE / entries[name]["private_original"]).read_bytes()) == entries[name]["original_sha256"]
            continue
        encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
        try:
            text = raw.decode(encoding)
        except UnicodeError:
            continue
        view, credentials = re.subn(r"(?i)(password=)[A-Za-z0-9_-]{24,}", r"\1[REDACTED_EPHEMERAL_PG_PASSWORD]", text)
        view, bearers = re.subn(r"Bearer [A-Za-z0-9_-]{32,}", "Bearer [REDACTED_EPHEMERAL_TEST_BEARER]", view)
        pii = 0
        for home in homes:
            for variant in {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}:
                pii += view.count(variant)
                view = view.replace(variant, "[LOCAL_USER_HOME]")
        if view == text:
            continue
        assert name not in entries, "CHANGED_PREVIOUS_PUBLIC_VIEW_REQUIRES_NEW_VERSIONED_EVIDENCE"
        target = PRIVATE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists()
        target.write_bytes(raw)
        public = view.encode(encoding)
        path.write_bytes(public)
        entries[name] = {"public_path": name, "original_sha256": digest(raw), "public_sha256": digest(public),
                         "private_original": target.relative_to(HERE).as_posix(), "credential_spans": credentials + bearers,
                         "local_home_spans": pii, "outcomes_or_assertions_modified": False,
                         "kind": "REDACTED_PUBLIC_VIEW_EXACT_ORIGINAL_RETAINED_PRIVATELY"}
        changed += 1
    result = {"status": "PUBLIC_VIEWS_NOT_RAW_ORIGINALS", "views": list(entries.values()),
              "private_originals": "IGNORED_RUNTIME_NOT_FOR_PUBLICATION", "original_evidence_deleted": False}
    LEDGER.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"new_public_views": changed, "total_private_originals_retained": len(entries)}))


if __name__ == "__main__":
    main()
