"""Publish original XML and executed synthetic data, never fabricated results."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def main():
    private = ROOT / "docs/03-engineering/l2-industrial-v1/.runtime"
    public = private / "public-ci"
    public.mkdir(exist_ok=False)
    publication = {"status": "INCOMPLETE_NOT_PASS"}
    try:
        original = (private / "ci-native.xml").read_bytes()
        root = ET.fromstring(original)
        cases = list(root.iter("testcase"))
        # Failure XML is retained as original bytes too. This fixture-only gate
        # has no credentials or customer data; never publish arbitrary inputs.
        assert not re.search(rb"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", original)
        assert b"Bearer " not in original and b"postgresql://" not in original
        (public / "native.xml").write_bytes(original)
        ids = [c.get("classname") + "::" + c.get("name") for c in cases]
        expected = json.loads((ROOT / "integration/industry_l2/expected_ids.json").read_text(encoding="utf-8"))
        assert ids == expected and len(ids) == 19 and len(set(ids)) == 19
        assert all(c.find(k) is None for c in cases for k in ("error", "failure", "skipped"))
        result = json.loads((private / "ci-demo/diagnosis.json").read_bytes())
        assert result["diagnostic_depth"] == "L2" and not result["shareable"]
        assert len(result["procurement_chains"]) == 2
        for name in ("diagnosis.json", "source.json", "summary.md"):
            shutil.copyfile(private / "ci-demo" / name, public / name)
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
        source = {name: hashlib.sha256(subprocess.check_output(["git", "cat-file", "blob", "HEAD:" + name], cwd=ROOT)).hexdigest()
                  for name in tracked if name.startswith(("vrae/industry/", "industry-packs/l2-industrial-v1/", "integration/industry_l2/", "tests/industry/", "tests/fixtures/industry/l2-industrial-v1/", "contracts/v1/industry/"))}
        publication.update(status="L2_NATIVE_AND_OFFLINE_DEMO_PASS_NOT_EXTERNAL_APPROVAL", native_cases=len(cases),
                           exact_ids=ids, native_xml_sha256=hashlib.sha256(original).hexdigest(),
                           diagnosis_ref=result["diagnosis_ref"], source_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
                           committed_source_sha256=source, network="RECORDED_LOCAL_FIXTURE_ONLY_NO_REAL_DOMAIN")
    finally:
        (public / "publication.json").write_text(json.dumps(publication, indent=2) + "\n", encoding="utf-8")
    assert publication["status"] == "L2_NATIVE_AND_OFFLINE_DEMO_PASS_NOT_EXTERNAL_APPROVAL"


if __name__ == "__main__":
    main()
