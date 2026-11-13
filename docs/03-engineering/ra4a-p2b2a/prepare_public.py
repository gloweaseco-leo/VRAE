"""Preserve original development failures privately; publish byte-hash ledger.

Failed Python tracebacks contain workstation account paths. No original is
rewritten. Final passing native evidence remains directly reviewable publicly.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil

HERE = Path(__file__).resolve().parent
PRIVATE = (HERE / ".runtime/private-evidence").resolve()


def main():
    original = HERE / "local311-dev1"
    execution = json.loads((original / "execution.json").read_text())
    legacy = next(c for c in execution["commands"] if c["stage"] == "legacy")
    # Preserve failed first-pass JUnit too; report.py checks every corrective ID.
    assert legacy["exit"] in (0, 1) and (original / "legacy/tests.xml").is_file()
    PRIVATE.mkdir(parents=True, exist_ok=True)
    assert PRIVATE.is_relative_to(HERE)
    public = HERE / "legacy311"
    assert not public.exists()
    shutil.copytree(original / "legacy", public)
    (public / "execution.json").write_text(json.dumps({
        "python": execution["python"], "head_at_execution": execution["head"],
        "actual_command": legacy, "source": execution["source"],
    }, indent=2) + "\n", encoding="utf-8")
    names = ("local311-dev1", "local311-final-pg", "local313-final-pg",
             "local311-pg-authorized", "local313-pg-authorized", "local311-pg-v2",
             "local313-pg-v2", "dev-crypto.xml", "dev313-crypto", "red-tests.xml", "red.log")
    ledger = []
    for name in names:
        source = (HERE / name).resolve()
        destination = (PRIVATE / name).resolve()
        assert source.is_relative_to(HERE) and destination.is_relative_to(PRIVATE)
        assert not source.is_symlink() and not destination.exists()
        if not source.exists():
            continue
        files = [source] if source.is_file() else sorted(p for p in source.rglob("*") if p.is_file())
        for path in files:
            assert path.resolve().is_relative_to(source if source.is_dir() else HERE)
            raw = path.read_bytes()
            ledger.append({"original_path": path.relative_to(HERE).as_posix(),
                           "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        # Checked absolute source/destination remain inside this task directory.
        shutil.move(str(source), str(destination))
    redactions = []
    home = str(Path.home())
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or ".runtime" in path.parts or "__pycache__" in path.parts:
            continue
        original_bytes = path.read_bytes()
        encoding = "utf-16" if original_bytes[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
        try:
            original_text = original_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
        public_text = original_text
        for spelling in (home.replace("\\", "\\\\"), home, Path.home().as_posix()):
            public_text = re.sub(re.escape(spelling), "[LOCAL_USER_HOME]", public_text,
                                 flags=re.IGNORECASE)
        if public_text == original_text:
            continue
        saved = (PRIVATE / "redacted-public-originals" / path.relative_to(HERE)).resolve()
        assert saved.is_relative_to(PRIVATE) and not saved.exists()
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(original_bytes)
        public_bytes = public_text.encode(encoding)
        path.write_bytes(public_bytes)
        redactions.append({"public_path": path.relative_to(HERE).as_posix(),
                           "raw_sha256": hashlib.sha256(original_bytes).hexdigest(),
                           "public_sha256": hashlib.sha256(public_bytes).hexdigest(),
                           "change": "Local account home path only; original preserved privately"})
    (HERE / "PRIVATE_DEVELOPMENT_EVIDENCE.json").write_text(json.dumps({
        "reason": "Original failed/debug traces retain local account paths; kept privately without rewriting",
        "location": ".runtime/private-evidence (git-ignored; never uploaded)",
        "raw_byte_ledger": ledger,
        "public_metadata_redactions": redactions,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"original_files_preserved_privately": len(ledger), "legacy311_public_copy": True}))


if __name__ == "__main__":
    main()
