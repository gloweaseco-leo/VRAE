"""Unmodified full ordinary discovery; native QA/Review counts from JUnit."""

import json
import hashlib
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from integration.ra4b.evidence import emit_stage, native_counts, probe_output

OUT = Path("/evidence")


def classify_existing():
    root = ET.parse(OUT / "tests.xml").getroot()
    cases = list(root.iter("testcase"))
    assert not list(root.iter("failure")) and not list(root.iter("error"))
    skipped = [c for c in cases if c.find("skipped") is not None]
    # Original ordinary-discovery guards defer these exact integration modules
    # to the unchanged separate firewall/Chromium jobs. They are never PASS here.
    assert len(skipped) == 25
    assert sum(c.get("classname") == "tests.collection.test_isolated" for c in skipped) == 24
    assert sum(c.get("classname") == "tests.browser.test_isolated_browser" for c in skipped) == 1
    qa = [c for c in cases if "test_ra3c_owner_adjudicated_v2" in c.get("classname", "")]
    review = [c for c in cases if c.get("classname", "").startswith("tests.reviewing.")]
    assert len(qa) == 118 and len(review) == 127
    assert not any(c.find("skipped") is not None for c in qa + review)
    prefix = "RA3D_D1D2_ACTUAL_RECEIPT="
    receipt = next(json.loads(line.split(prefix, 1)[1]) for line in (OUT / "stdout.log").read_text().splitlines() if prefix in line)
    result = {"status": "ORDINARY_PASS_SEPARATE_ISOLATED_GATES_REQUIRED", "python": receipt["python"],
              "discovered": len(cases), "ordinary_passed": len(cases) - len(skipped),
              "frozen_qa_v2": len(qa), "frozen_ra3d": len(review), "skipped_for_separate_isolated_jobs": len(skipped),
              "deferred_ids": [c.get("classname") + "::" + c.get("name") for c in skipped],
              "isolated_cases_claimed_pass": False, "frozen_tests_modified": False}
    (OUT / "result.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    held = json.loads(Path("/work/RA4B_SOURCE_MANIFEST.json").read_bytes())

    def verify():
        return all(hashlib.sha256((Path("/work") / row["path"]).read_bytes()).hexdigest() == row["sha256"] for row in held)

    stage, native_exit, access = "OUTPUT_PREFLIGHT", None, None
    try:
        access = probe_output()
        stage = "SOURCE_BEFORE"
        assert verify()
        stage = "PYTEST"
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider",
                                 "--junitxml=/evidence/tests.xml"], cwd="/work", capture_output=True)
        native_exit = result.returncode
        stage = "PERSIST_LOGS"
        (OUT / "stdout.log").write_bytes(result.stdout)
        (OUT / "stderr.log").write_bytes(result.stderr)
        stage = "SOURCE_AFTER"
        assert verify()
        (OUT / "source-integrity.json").write_text(json.dumps({"before": True, "after": True, "files": len(held)}))
        stage = "PYTEST_EXIT"
        result.check_returncode()
        stage = "CLASSIFY"
        classify_existing()
        emit_stage({"phase": "UNIT", "stage": "COMPLETE", "status": "PASS", "native_exit": native_exit,
                    "native_counts": native_counts(OUT / "tests.xml"), "output_access": access})
    except BaseException as exc:
        emit_stage({"phase": "UNIT", "stage": stage, "status": "FAIL", "exception_type": type(exc).__name__,
                    "errno": getattr(exc, "errno", None), "native_exit": native_exit,
                    "native_counts": native_counts(OUT / "tests.xml"), "output_access": access}, primary_failure=True)
        raise


if __name__ == "__main__":
    main()
