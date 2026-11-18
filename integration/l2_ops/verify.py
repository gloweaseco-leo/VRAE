"""Native Python3.11/3.13 on Windows or Linux, isolated PG16, actual restart.

This validates the C3 business package. Synthetic reader fixtures are not an
accepted C1 L2 result port or a complete browser/Worker L2 demonstration.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def command(args, **kwargs):
    p = subprocess.run(args, check=False, cwd=ROOT, capture_output=True, text=True, **kwargs)
    if p.returncode:
        raise RuntimeError(f"command failed {args[0:2]}: {p.stdout}\n{p.stderr}")
    return p.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--python311")
    parser.add_argument("--python313")
    parser.add_argument("--python-current")
    focused = parser.add_mutually_exclusive_group()
    focused.add_argument("--business-only", action="store_true", help="Only the new native business routes and actual PG restart marker; not the full package")
    focused.add_argument("--lifecycle-only", action="store_true", help="Only real PG commit/restart/owned-volume cleanup; not package or Worker proof")
    focused.add_argument("--executive-only", action="store_true", help="S4 summary/receiver browser plus original PG/signature fences")
    parser.add_argument("--pg-image", default="postgres:16-alpine")
    args = parser.parse_args()
    version_code = "import sys; print(str(sys.version_info.major)+str(sys.version_info.minor))"
    if args.python_current:
        if args.python311 or args.python313:
            parser.error("Use current interpreter or the explicit dual-version pair")
        minor = command([args.python_current, "-c", version_code])
        if minor not in {"311", "313"}:
            parser.error("Native Python3.11 or3.13 required")
        interpreters = ((minor, args.python_current),)
    else:
        if not args.python311 or not args.python313:
            parser.error("Supply both native interpreters for dual-version validation")
        interpreters = (("311", args.python311), ("313", args.python313))
    for minor, interpreter in interpreters:
        if command([interpreter, "-c", version_code]) != minor:
            parser.error("Actual interpreter does not match the requested version")
    if not args.label.isalnum() or len(args.label) > 30:
        raise ValueError("bounded alphanumeric label")
    folder = ROOT / "integration/l2_ops/.private" / args.label
    folder.mkdir(parents=True, exist_ok=False)
    output = ROOT / "docs/03-engineering/l2-operations" / args.label
    output.mkdir(parents=True, exist_ok=False)
    image = command(["docker", "image", "inspect", args.pg_image, "--format", "{{.Id}}"])
    source_paths = ["vrae/l2_ops", "integration/l2_ops", "integration/l2_executive", "apps/operator_console/l2_executive_views.py", "apps/operator_console/l2_http.py", "apps/operator_console/l2_views.py", "apps/operator_console/l2.css", "scripts/beta_internal.py", "integration/ra4c_b5a/publication.py", ".github/workflows/l2-ops.yml", "apps/operator_console/b5b_http.py", "vrae/l2", "vrae/industry/l2_v1"]
    command(["git", "diff", "--exit-code", "HEAD", "--", *source_paths])
    candidate_sha = command(["git", "rev-parse", "HEAD"])
    files = command(["git", "ls-files", "--", *source_paths]).splitlines()
    source_manifest = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}
    (output / "source-manifest.json").write_text(json.dumps({"candidate_sha": candidate_sha,
        "files_sha256": source_manifest}, indent=2), encoding="utf-8")
    results = []
    for minor, interpreter in interpreters:
        # No random queue selection. Name randomness is not diagnostic sampling.
        name = f"vrae-l2ops-{args.label}-{minor}"
        network = name + "-net"
        password = secrets.token_urlsafe(32)
        envfile = folder / f"pg-{minor}.env"
        envfile.write_text(f"POSTGRES_PASSWORD={password}\nPOSTGRES_DB=l2ops\n", encoding="utf-8")
        started = time.monotonic_ns()
        container_started = network_started = False
        container_id = None
        try:
            command(["docker", "network", "create", network])
            network_started = True
            container_id = command(["docker", "run", "-d", "--pull", "never", "--name", name,
                     "--network", network, "--env-file", str(envfile),
                     "-p", "127.0.0.1::5432", image])
            container_started = True
            if not re.fullmatch(r"[a-f0-9]{64}", container_id):
                raise RuntimeError("owned PG container ID was not recorded")
            port = command(["docker", "port", name, "5432/tcp"]).rsplit(":", 1)[1]
            for _ in range(60):
                p = subprocess.run(["docker", "exec", name, "pg_isready", "-U", "postgres", "-d", "l2ops"], check=False, capture_output=True)
                if p.returncode == 0:
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("PG startup did not become ready")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
            if args.executive_only:
                env['S4_OUTPUT'] = str(output / f'browser-{minor}')
                env['S4_REAL_BROWSER'] = '1'
            env["L2OPS_RUNTIME_OUTPUT"] = str(folder / f"runtime-{minor}.private")
            env["L2OPS_TEST_DSN"] = f"host=127.0.0.1 port={port} user=postgres password={password} dbname=l2ops connect_timeout=5"
            version = command([interpreter, "--version"])
            xml = output / f"native-{minor}.xml"
            suites = (["integration/l2_ops/checks/test_executive.py", "integration/l2_ops/checks/test_intake.py",
                       "integration/l2_ops/runtime_tests/test_pg.py::test_pg_executive_summary_and_independent_receipts",
                       "integration/l2_ops/runtime_tests/test_pg.py::test_pg_native_business_ui_denies_without_current_dual_authority",
                       "integration/l2_ops/runtime_tests/test_pg.py::test_pg_restart_marker"] if args.executive_only else
                      ["integration/l2_ops/runtime_tests/test_pg.py::test_pg_restart_marker"] if args.lifecycle_only else
                      ["integration/l2_ops/checks/test_panel.py",
                       "integration/l2_ops/checks/test_native_report.py::test_production_keeps_task_context_and_records_separate_c2_runtime",
                       "integration/l2_ops/runtime_tests/test_pg.py::test_pg_native_business_ui_preview_save_readback_and_nonce_replay",
                       "integration/l2_ops/runtime_tests/test_pg.py::test_pg_native_business_ui_denies_without_current_dual_authority",
                       "integration/l2_ops/runtime_tests/test_pg.py::test_pg_restart_marker"] if args.business_only
                      else ["integration/l2_ops/checks", "integration/l2_ops/runtime_tests",
                            "--ignore=integration/l2_ops/runtime_tests/test_pg_restart.py"])
            tests = command([interpreter, "-m", "pytest", "-q", *suites, *(['--tb=short'] if args.executive_only else []), f"--junitxml={xml}"], env=env)
            (output / f"native-{minor}.txt").write_text(tests, encoding="utf-8")
            before = command(["docker", "exec", name, "psql", "-U", "postgres", "-d", "l2ops", "-Atc",
                              "SELECT content_sha256 || ':' || md5(document) FROM l2_ops_v1.briefs WHERE brief_ref='restart-readback'"])
            command(["docker", "restart", name])
            for _ in range(60):
                if subprocess.run(["docker", "exec", name, "pg_isready", "-U", "postgres", "-d", "l2ops"], check=False, capture_output=True).returncode == 0:
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("PG restart did not become ready")
            after = command(["docker", "exec", name, "psql", "-U", "postgres", "-d", "l2ops", "-Atc",
                             "SELECT content_sha256 || ':' || md5(document) FROM l2_ops_v1.briefs WHERE brief_ref='restart-readback'"])
            if not before or before != after:
                raise RuntimeError("restart readback mismatch")
            from psycopg.conninfo import make_conninfo
            # Docker Desktop allocates a NEW ephemeral host port on restart.
            # Re-discover the actual loopback mapping; do not reuse the old DSN.
            restarted_port = command(["docker", "port", name, "5432/tcp"]).rsplit(":", 1)[1]
            env["L2OPS_RUNTIME_DSN"] = make_conninfo(
                Path(env["L2OPS_RUNTIME_OUTPUT"]).read_text(encoding="utf-8"), port=restarted_port)
            (output / f"transport-{minor}.json").write_text(json.dumps(
                {"before_loopback_port": port, "after_loopback_port": restarted_port,
                 "binding": "127.0.0.1", "rediscovered_after_restart": True}, indent=2), encoding="utf-8")
            restart_tests = command([interpreter, "-m", "pytest", "-q", "integration/l2_ops/runtime_tests/test_pg_restart.py",
                                     f"--junitxml={output / f'restart-{minor}.xml'}"], env=env)
            (output / f"restart-{minor}.txt").write_text(restart_tests, encoding="utf-8")
            server_version = command(["docker", "exec", name, "psql", "-U", "postgres", "-Atc", "SHOW server_version_num"])
            results.append({"candidate_sha": candidate_sha, "python": version, "platform": platform.platform(), "pg_version_num": server_version,
                            "pg_image_id": image, "restart_readback": before, "xml_sha256": hashlib.sha256(xml.read_bytes()).hexdigest(),
                            "measurement_wall_ns": time.monotonic_ns() - started,
                            "cost_status": "UNKNOWN", "amount_micros": None,
                            "scope": ("S4_SUMMARY_RECEIVER_REAL_PG_DETACHED_TASK_NOT_WORKER_E2E" if args.executive_only else
                                      "C3_PG_LIFECYCLE_ONLY_NOT_PACKAGE_OR_WORKER_E2E" if args.lifecycle_only else
                                      "C3_BUSINESS_ROUTES_REAL_PG_SYNTHETIC_TASK_NOT_FULL_PACKAGE_OR_WORKER_E2E" if args.business_only
                                      else "C3_PACKAGE_REAL_PG_SYNTHETIC_UPSTREAM_NOT_FULL_L2_E2E")})
        except Exception as exc:  # noqa: BLE001 -- archive/redact every failure, then propagate
            from psycopg.conninfo import conninfo_to_dict
            secret_values = [password]
            runtime_file = folder / f"runtime-{minor}.private"
            if runtime_file.is_file():
                secret_values.append(conninfo_to_dict(runtime_file.read_text(encoding="utf-8"))["password"])
            original = str(exc)
            (folder / f"original-red-{minor}.txt").write_text(original, encoding="utf-8")
            safe = original
            for secret in secret_values:
                safe = safe.replace(secret, "[REDACTED_EPHEMERAL_TEST_PASSWORD]")
            originals = folder / f"original-xml-{minor}"
            originals.mkdir(exist_ok=True)
            for xml_path in output.glob("*.xml"):
                raw = xml_path.read_bytes()
                (originals / xml_path.name).write_bytes(raw)
                content = raw.decode("utf-8")
                for secret in secret_values:
                    content = content.replace(secret, "[REDACTED_EPHEMERAL_TEST_PASSWORD]")
                xml_path.write_text(content, encoding="utf-8")
            (output / f"red-{minor}.json").write_text(json.dumps({"error": safe,
                "private_original_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "stage": "C3_PACKAGE_VALIDATION", "retained": True,
                "credentials_redacted": True}, ensure_ascii=False, indent=2), encoding="utf-8")
            raise RuntimeError(safe) from None
        finally:
            removed_volumes = []
            if container_started:
                actual_id = command(["docker", "inspect", name, "--format", "{{.Id}}"])
                if actual_id != container_id:
                    raise RuntimeError("owned PG container identity changed; do not remove another resource")
                mounts = json.loads(command(["docker", "inspect", name, "--format", "{{json .Mounts}}"] ))
                volumes = [m["Name"] for m in mounts if m.get("Type") == "volume"
                           and m.get("Destination") == "/var/lib/postgresql/data"]
                if len(mounts) != 1 or len(volumes) != 1 or not re.fullmatch(r"[a-f0-9]{64}", volumes[0]):
                    raise RuntimeError("expected owned anonymous PG data volume was not identified")
                command(["docker", "rm", "-f", "-v", container_id])
                for volume in volumes:
                    if command(["docker", "volume", "ls", "-q", "--filter", "name=^" + volume + "$"]):
                        raise RuntimeError("owned anonymous PG data volume remains")
                removed_volumes = volumes
            if network_started:
                command(["docker", "network", "rm", network])
            remaining = command(["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"])
            if remaining:
                raise RuntimeError("owned container remains")
            cleanup = {"owned_containers_remaining": [], "owned_pg_volumes_remaining": [],
                       "removed_anonymous_pg_volumes": removed_volumes,
                       "container_id": container_id, "label": args.label, "minor": minor}
            (output / f"cleanup-{minor}.json").write_text(json.dumps(cleanup, indent=2), encoding="utf-8")
            (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2), encoding="utf-8")
    command(["git", "diff", "--exit-code", "HEAD", "--", *source_paths])
    if command(["git", "rev-parse", "HEAD"]) != candidate_sha or any(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != expected for p, expected in source_manifest.items()
    ):
        raise RuntimeError("tested source changed during verification")
    (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
