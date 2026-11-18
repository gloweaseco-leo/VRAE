"""Native P0 quality verification; no PG, browser, external source or signing."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "84276325befdcf858852a1ec791e8b0695a515eb"
FROZEN = (
    "vrae",
    "apps",
    "contracts",
    "industry-packs",
    "tests/benchmark/human_gold.py",
    "tests/benchmark/quality.py",
    "tests/benchmark/scenarios.py",
    "tests/fixtures/industry/l2-industrial-v1",
    "industry-packs/l2-industrial-v1",
    "tests/benchmark/samples",
    "vrae/evidence/pack.py",
    "vrae/rules/execution.py",
    "vrae/industry",
    "vrae/l2",
    "db",
)
OWN = (
    "tests/benchmark/s2_sites.py",
    "tests/benchmark/s2_quality.py",
    "tests/benchmark/s2_review.py",
    "tests/s2_quality",
    "integration/l2_ops/s2_quality_cli.py",
    "integration/l2_ops/s2_quality_verify.py",
    ".github/workflows/s2-c3-quality.yml",
)
REVIEWED_S4_HEAD = 'acfbb379097c662d39d128a0fa8538ddef248408'
REVIEWED_S4_BASE = '676fdde5c14a23bb284a0cb00df25773b30ed4b3'
REVIEWED_S4_FILES = frozenset({
    'vrae/l2/executive.py', 'vrae/l2_ops/intake.py', 'vrae/l2_ops/intake_panel.py',
    'apps/operator_console/l2_executive_views.py', 'apps/operator_console/l2_http.py',
    'apps/operator_console/l2_views.py', 'apps/operator_console/l2.css',
})


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def reviewed_s4_overlay(changed, base):
    """Owner-approved exact blobs only; never a general core-directory waiver."""
    if base != REVIEWED_S4_BASE or not changed or not set(changed) <= REVIEWED_S4_FILES:
        return False
    return all(git('rev-parse', 'HEAD:'+name) == git('rev-parse', REVIEWED_S4_HEAD+':'+name)
               for name in changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--base-ref", default=BASELINE)
    parser.add_argument("--python-current")
    parser.add_argument("--python311")
    parser.add_argument("--python313")
    parser.add_argument('--reviewed-s4', action='store_true', help='Exact Owner-reviewed PR140 component blobs')
    args = parser.parse_args()
    if not re.fullmatch("[a-z0-9-]{3,40}", args.label):
        parser.error("new bounded label required")
    if args.python_current:
        if args.python311 or args.python313:
            parser.error("current or dual pair, not both")
        interpreters = [args.python_current]
    else:
        if not args.python311 or not args.python313:
            parser.error("supply both actual native interpreters")
        interpreters = [args.python311, args.python313]
    if not re.fullmatch("[a-f0-9]{40}", args.base_ref):
        parser.error("exact accepted base SHA required")
    changed = git("diff", "--name-only", args.base_ref + "...HEAD", "--", *FROZEN).splitlines()
    if changed and not (args.reviewed_s4 and reviewed_s4_overlay(changed, args.base_ref)):
        raise RuntimeError("FROZEN_SOURCE_CHANGED")
    if git("diff", "--name-only", "HEAD", "--", *OWN):
        raise RuntimeError("COMMIT_EXECUTABLE_CANDIDATE_BEFORE_NATIVE_GATE")
    if git("rev-parse", "HEAD:vrae/evidence/pack.py") != "8d45d5882103323e62bc4bd61a4379899e759966":
        raise RuntimeError("FROZEN_PACK_BLOB_CHANGED")
    output = ROOT / "docs/03-engineering/l2-operations/s2-quality" / args.label
    output.mkdir(parents=True, exist_ok=False)
    head = git("rev-parse", "HEAD")
    files = git("ls-files", "--", *OWN, *FROZEN).splitlines()
    manifest = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
    (output / "source-manifest.json").write_text(
        json.dumps(dict(source_sha=head, files=manifest), indent=2), encoding="utf-8"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONUTF8"] = "1"
    results = []
    for index, exe in enumerate(interpreters):
        minor = (
            subprocess.check_output(
                [
                    exe,
                    "-c",
                    "import sys;print(str(sys.version_info.major)+str(sys.version_info.minor))",
                ]
            )
            .decode()
            .strip()
        )
        if minor not in ("311", "313") or (
            not args.python_current and minor != str((311, 313)[index])
        ):
            raise RuntimeError("NATIVE_INTERPRETER_MISMATCH")
        imported_root = (
            subprocess.check_output(
                [
                    exe,
                    "-c",
                    "from pathlib import Path; import vrae; print(Path(vrae.__file__).resolve().parent.parent)",
                ],
                cwd=ROOT,
                env=env,
            )
            .decode()
            .strip()
        )
        if Path(imported_root).resolve() != ROOT:
            raise RuntimeError("FOREIGN_SOURCE_IMPORT_ROOT")
        folder = output / minor
        folder.mkdir()
        started = time.monotonic_ns()
        commands = [
            [
                exe,
                "-X",
                "utf8",
                "-m",
                "pytest",
                "-q",
                "tests/benchmark",
                "tests/s2_quality/quality_cases.py",
                "tests/s2_quality/input_cases.py",
                "tests/s2_quality/source_scope_cases.py",
                "tests/industry/l2_cases.py",
                "--junitxml=" + str(folder / "native.xml"),
            ],
            [
                exe,
                "-X",
                "utf8",
                "integration/l2_ops/s2_quality_cli.py",
                "packet",
                "--output",
                str(folder / "unsigned-packet"),
            ],
            [
                exe,
                "-X",
                "utf8",
                "integration/l2_ops/s2_quality_cli.py",
                "verify-export",
                "--output",
                str(folder / "unsigned-packet"),
            ],
            [exe, "-X", "utf8", "integration/l2_ops/s2_quality_cli.py", "assess"],
            [exe, "-X", "utf8", "integration/l2_ops/s2_quality_cli.py", "legacy"],
        ]
        for stage, command in enumerate(commands):
            with (folder / f"stage-{stage}.txt").open("wb") as log:
                result = subprocess.run(
                    command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
                )
            if result.returncode:
                raise RuntimeError(f"PRESERVED_NATIVE_RED_{minor}_stage_{stage}")
        hashes = {
            f.relative_to(folder).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in folder.rglob("*")
            if f.is_file()
        }
        intake = json.loads((folder / "stage-3.txt").read_text("utf-8"))
        legacy = json.loads((folder / "stage-4.txt").read_text("utf-8"))
        assert intake["denominator"] == legacy["eligible_verified_rows"] == 0
        assert legacy["pending_rows"] == 26 and all(v is None for v in intake["metrics"].values())
        receipt = dict(
            source_sha=head,
            native_python=subprocess.check_output([exe, "--version"]).decode().strip(),
            wall_ns=time.monotonic_ns() - started,
            scope="C3_P0_OFFLINE_ENGINEERING_NOT_FULL_S2_E2E",
            import_root=imported_root,
            quality_status="S2_QUALITY_NOT_EVALUABLE",
            original_26_pending=26,
            resources_started=[],
            model_calls=0,
            external_network_calls=0,
            cost_status="UNKNOWN",
            files=hashes,
        )
        (folder / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        results.append(receipt)
        print(
            json.dumps(
                dict(minor=minor, status="C3_P0_ENGINEERING_READY_GOLD_PENDING", source_sha=head)
            ),
            flush=True,
        )
    if manifest != {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}:
        raise RuntimeError("SOURCE_CHANGED_DURING_VERIFICATION")
    (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
