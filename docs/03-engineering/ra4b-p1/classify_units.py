"""Classify already complete, unchanged native JUnit; never rerun or alter tests."""

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def main():
    from integration.ra4b import unit_check
    for label in ("unit311-v2", "unit313-v3"):
        out = HERE / label
        assert json.loads((out / "source-integrity.json").read_bytes()) == {"before": True, "after": True, "files": 6445}
        unit_check.OUT = out
        result = unit_check.classify_existing()
        (out / "postprocessor-correction.json").write_text(json.dumps({"original_native_pytest_failures": 0,
            "original_native_pytest_errors": 0, "original_supervisor_exit": 1,
            "cause": "NEW_SUMMARIZER_WRONGLY_REJECTED_ORIGINAL_GUARDED_ISOLATION_DEFERRALS",
            "native_junit_or_outcomes_changed": False, "isolated_gates_still_required": True}, indent=2))
        print(json.dumps({"label": label, "ordinary": result["ordinary_passed"], "deferred": result["skipped_for_separate_isolated_jobs"]}))


if __name__ == "__main__":
    main()
