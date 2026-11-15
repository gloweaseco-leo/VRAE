"""Publish exact secret-free native JUnit; never synthesize tests from stdout."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]


def main():
    label = sys.argv[1]
    assert re.fullmatch("[a-z0-9-]{3,40}", label)
    private = ROOT / "docs/03-engineering/ra4b-p2/.runtime" / ("m1-" + label)
    public = ROOT / "docs/03-engineering/ra4b-p2/.runtime" / ("public-" + label)
    public.mkdir(exist_ok=False)
    metadata = {"status": "INCOMPLETE_NATIVE_GATES_NOT_PASS", "label": label, "native": []}
    try:
        secrets = []
        for p in private.rglob("private-credential-scan-values.json"):
            secrets += json.loads(p.read_bytes())
        sources = json.loads((private / "source-manifest.json").read_bytes())
        receipts = []
        for name, folder, expected in [
            ("runtime", private, 17),
            ("restarted", private / "recovered", 2),
        ]:
            raw = (folder / "native-junit.xml").read_bytes()
            receipt = json.loads((folder / "receipt.json").read_bytes())
            assert receipt["native_junit_sha256"] == hashlib.sha256(raw).hexdigest()
            cases = list(ET.fromstring(raw).iter("testcase"))
            assert len(cases) == expected and all(
                c.find(k) is None for c in cases for k in ("failure", "error", "skipped")
            )
            assert receipt["returncode"] == 0 and receipt["red_or_skipped"] == []
            decoded = raw.decode()
            assert not any(value and value in decoded for value in secrets)
            assert not re.search(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", decoded)
            assert "<html" not in decoded.lower() and "objects_base64" not in decoded
            ids = [c.get("classname") + "::" + c.get("name") for c in cases]
            receipts.append(
                (
                    name,
                    raw,
                    {
                        "gate": name,
                        "cases": len(cases),
                        "native_junit_sha256": hashlib.sha256(raw).hexdigest(),
                        "ids": ids,
                        "exact_ids_sha256": hashlib.sha256(
                            ("\n".join(ids) + "\n").encode()
                        ).hexdigest(),
                    },
                )
            )
        cleanup = json.loads((private / "cleanup.json").read_bytes())
        assert len(cleanup) == 4 and all(r["absent"] for r in cleanup)
        proof = json.loads((private / "m1-proof.json").read_bytes())
        assert proof["legacy_graph_count_unchanged"]
        assert proof["real_worker_uid"] == 10002
        for name, raw, data in receipts:
            (public / (name + ".xml")).write_bytes(raw)
            metadata["native"].append(data)
        shutil.copyfile(private / "source-manifest.json", public / "source-manifest.json")
        shutil.copyfile(private / "m1-proof.json", public / "m1-proof.json")
        metadata.update(
            status="M1_NATIVE_PASS_NOT_FULL_BETA_EXIT",
            actual_pg_restart=True,
            sources_sha256=hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
            all_four_owned_resources_absent=True,
            raw_junit_preserved=True,
        )
    finally:
        (public / "publication.json").write_text(json.dumps(metadata, indent=2))
    assert metadata["status"] == "M1_NATIVE_PASS_NOT_FULL_BETA_EXIT"
    print(json.dumps({"status": metadata["status"], "native_cases": 19, "public": str(public)}))


if __name__ == "__main__":
    main()
