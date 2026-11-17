"""M3 lifecycle glue for the Owner-accepted single M2 SSR and actual M1 Worker."""

import base64
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import queue
import re
import subprocess
import threading
import time
from uuid import UUID

import psycopg

from tests.identity.issuer import AUDIENCE, ISSUER, Issuer
from vrae.application.ra4b_p2.m1.reader import JobAssignment

from .m3_application import GeneratedRun
from .runner import OWNER_LABEL, PRIVATE, ROOT, cmd, wait, write

MODE = "M3_SYNTHETIC_BROWSER_WORKBENCH"


class Workbench(GeneratedRun):
    def __init__(self, label, minor):
        super().__init__(label, minor)
        self.result["scope"] = MODE
        self.generated_dependencies = [
            {"interface": "M1/M2 accepted business ports", "state": "CONNECTED"}
        ]
        self.bridge_process = None
        self.http = None
        self.http_thread = None
        self.pipe_thread = None
        self.transport_lock = threading.RLock()
        self.pending_jobs = queue.Queue()
        self.woken = set()
        self.committed = {}
        self.wake_serial = 0
        self.nonces = {}
        self.web_tasks = {}
        self.http_observations = []
        self.ssr_exits = []
        self.secret_values = []
        self.routing = self.source_volume + "-routing"
        self.routing_created = False
        self.bootstrap = {}
        self.issuer = Issuer()
        self.profile_data = None

    def start_pg(self):
        super().start_pg()
        sql = ROOT / "db/b5b_m2/001_internal_review.sql"
        with self.r.lab.connect(dbname="vrae_ra4a_p1") as c:
            assert c.execute("SELECT to_regnamespace('b5b_m2')").fetchone() == (None,)
            c.execute(sql.read_text(encoding="utf-8"))
        import hashlib

        self.result["m2_migration_sha256"] = hashlib.sha256(sql.read_bytes()).hexdigest()
        self.secret_values.extend(
            [self.r.lab.state["admin_password"], *self.r.lab.state["runtime_passwords"].values()]
        )

    def bootstrap_identity(self):
        from .m3_results import materialize, submit

        for case in ("404", "200"):
            task = submit(self.label, case, "m3-bootstrap-" + case + "-0001")
            self.bootstrap[case] = materialize(self.label, task["job_id"], 90)["locator"]
        write(self.folder / "bootstrap-pins.private.json", self.bootstrap)
        now = int(time.time())
        role = "p2b1_test_a_reviewer"
        password = self.r.lab.state["runtime_passwords"][role]
        self.secret_values.append(password)
        self.profile_data = {
            "version": "M2_SYNTHETIC_REVIEWER_1",
            "anchor": {
                "issuer": ISSUER,
                "audience": AUDIENCE,
                "jwks": json.loads(self.issuer.jwks()),
                "expires": now + 1700,
            },
            "assignments": [
                asdict(
                    JobAssignment(
                        ISSUER,
                        "synthetic-reviewer-1",
                        role,
                        "tenant-test",
                        pins["job_id"],
                        now + 1700,
                    )
                )
                for pins in self.bootstrap.values()
            ],
            "reviewers": {role: {"password": password}},
            "tasks": {
                case: {"tenant": "tenant-test", "job_id": pins["job_id"]}
                for case, pins in self.bootstrap.items()
            },
            "task_journal": "/state/tasks.sqlite",
        }

    def start_ssr(self):
        if not self.routing_created:
            cmd(
                [
                    "docker",
                    "volume",
                    "create",
                    "--label",
                    OWNER_LABEL + "=" + self.label,
                    self.routing,
                ]
            )
            self.routing_created = True
            cmd(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--cap-add",
                    "CHOWN",
                    "--mount",
                    "type=volume,src=" + self.routing + ",dst=/state",
                    self.result["runtime_image_id"],
                    "python",
                    "-c",
                    "import os;os.chmod('/state',0o700);os.chown('/state',10003,10003)",
                ]
            )
        if self.http is None:
            self.start_transport()
        # The trusted launcher projects only the already-isolated HTTP profile.
        endpoint = json.loads(
            cmd(
                [
                    "docker",
                    "exec",
                    "--user",
                    "10003:10003",
                    self.client_name,
                    "python",
                    "-c",
                    "from pathlib import Path;print(Path('/tmp/m3-consumer/config.json').read_text())",
                ]
            )
        )
        assert set(endpoint) == {"bearer", "tenant_id", "source_refs"}
        self.profile_data["task_endpoint"] = endpoint
        self.secret_values.append(endpoint["bearer"])
        self.ssr_name = self.source_volume + "-ssr"
        errors = (self.folder / ("ssr-boot-" + str(self.boot) + ".stderr.private.log")).open("wb")
        self.logs.append(errors)
        args = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            self.ssr_name,
            "--label",
            OWNER_LABEL + "=" + self.label,
            "--network",
            "container:" + self.r.lab.name,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "10003:10003",
            "--memory",
            "768m",
            "--pids-limit",
            "128",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=128m",
            "--mount",
            "type=volume,src=" + self.source_volume + ",dst=/work,readonly",
            "--mount",
            "type=volume,src=" + self.routing + ",dst=/state",
            self.result["runtime_image_id"],
            "python",
            "-X",
            "faulthandler",
            "-B",
            "-m",
            "integration.b5b.m2_bridge",
        ]
        self.bridge_process = subprocess.Popen(
            args,
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
            encoding="utf-8",
        )
        self.replies = queue.Queue()
        current, replies = self.bridge_process, self.replies

        def pump():
            try:
                for line in current.stdout:
                    replies.put(json.loads(line))
            finally:
                replies.put(None)

        self.pipe_thread = threading.Thread(target=pump, daemon=True)
        self.pipe_thread.start()
        current.stdin.write(
            json.dumps(self.ssr_configuration()) + "\n"
        )
        current.stdin.flush()
        assert self.replies.get(timeout=30) == {"ready": True}
        self.result["ssr_origin"] = self.r.origin
        self.result["single_ssr"] = {
            "entry": "integration.b5b.m2_bridge",
            "composition": "apps.operator_console.b5b_http.Application",
            "uid": 10003,
            "count": 1,
            "private_signer_in_ssr": False,
            "app_worker_db_config_in_ssr": False,
            "transport": "ACCEPTED_FINITE_LOOPBACK_STDIO_NO_SECOND_SSR",
        }
        write(
            self.folder / "m3-runtime.json",
            {
                "mode": MODE,
                "source_sha": self.result["source_sha"],
                "native_out": str(self.native_out.relative_to(self.folder)),
                "review_ui": "M2_CONNECTED",
                "ssr_is_generated_job_reviewer": True,
            },
        )

    def start_transport(self):
        owner = self

        class Relay(BaseHTTPRequestHandler):
            def respond(self):
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 <= size <= 24576:
                        self.send_error(413)
                        return
                    request = {
                        "method": self.command,
                        "path": self.path,
                        "headers": dict(self.headers),
                        "body": base64.b64encode(self.rfile.read(size)).decode(),
                    }
                    with owner.transport_lock:
                        assert owner.bridge_process.poll() is None, "M3_SSR_UNEXPECTED_EXIT"
                        owner.bridge_process.stdin.write(json.dumps(request) + "\n")
                        owner.bridge_process.stdin.flush()
                        reply = owner.replies.get(timeout=25)
                        assert reply is not None, "M3_SSR_EOF"
                        raw = base64.b64decode(reply["body"], validate=True)
                        wire = raw + json.dumps(reply["headers"]).encode()
                        assert not any(s.encode() in wire for s in owner.secret_values), (
                            "M3_SECRET_IN_RESPONSE"
                        )
                        owner.observe(self.command, self.path, reply["status"], raw)
                        self.send_response_only(reply["status"])
                        for key, value in reply["headers"]:
                            self.send_header(key, value)
                        self.end_headers()
                        if self.command != "HEAD":
                            self.wfile.write(raw)
                            self.wfile.flush()
                except Exception as exc:
                    write(
                        owner.folder / "transport-failure.private.json",
                        {"kind": type(exc).__name__},
                    )
                    self.close_connection = True

            do_GET = do_POST = do_HEAD = respond

            def log_message(self, *_args):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Relay)
        self.r.origin = "http://127.0.0.1:" + str(self.http.server_port)
        self.http_thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.http_thread.start()

    def ssr_configuration(self):
        return {"profile": self.profile_data, "origin": self.r.origin}

    def observe(self, method, path, status, raw):
        self.http_observations.append({"method": method, "path": path, "status": status})
        if status == 200 and method == "POST" and path.endswith("challenge"):
            doc = json.loads(raw)
            if set(doc) == {"nonce", "csrf"}:
                self.nonces[doc["nonce"]] = time.monotonic()
        if (
            status == 200
            and method == "GET"
            and re.fullmatch(r"/b5a/m2/task/[A-Za-z0-9_-]{43}", path)
        ):
            text = raw.decode()
            state = re.search(r'data-key="m2-job-state">([^<]+)', text)
            if state and state[1] == "PENDING":
                task = {
                    key: re.search('data-key="m2-' + key + '">([^<]+)', text)[1]
                    for key in ("request_id", "run_id", "job_id", "source_ref")
                }
                for key in ("request_id", "run_id", "job_id"):
                    assert str(UUID(task[key])) == task[key]
                assert task["source_ref"] in getattr(self, "allowed_source_refs", ("accepted-404", "accepted-200"))
                self.web_tasks[task["job_id"]] = task
                self.pending_jobs.put(task["job_id"])

    def read_commits(self):
        path = self.native_out / "m1-worker.log"
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("{") and line.endswith("}"):
                row = json.loads(line)
                rows.append(row)
                if "job_id" in row:
                    old = self.committed.get(row["job_id"])
                    assert old is None or old == row, "M3_CHANGED_COMMITTED_LOCATOR"
                    self.committed[row["job_id"]] = row
        return rows

    def dispatch(self):
        while True:
            try:
                job = self.pending_jobs.get_nowait()
            except queue.Empty:
                return
            self.read_commits()
            if job in self.committed:
                continue
            # Serialize this app's locked signed reads with each canonical
            # Worker invocation. Keep all original DB/lease/time budgets.
            # Claim still chooses its own legal job; no UUID is passed to it.
            with self.transport_lock:
                prior = set(self.committed)
                before = len(self.read_commits())
                self.wake_serial += 1
                path = self.native_out / ("auto-" + str(self.wake_serial) + ".wake.json")
                temporary = path.with_suffix(".tmp")
                write(temporary, {"process_one": True})
                temporary.replace(path)
                deadline = time.monotonic() + 90
                while not (set(self.committed) - prior):
                    assert self.client.poll() is None, "M3_CANONICAL_WORKER_EXIT"
                    rows = self.read_commits()
                    assert not any(
                        r.get("status") == "NO_LEGAL_PENDING_JOB" for r in rows[before:]
                    ), "M3_PENDING_ADMISSION_LOST"
                    assert time.monotonic() < deadline, "M3_REAL_WORKER_RESULT_DEADLINE"
                    time.sleep(0.05)
            self.woken.add(job)
            # If another legal pending job sorted first, process the remaining
            # real queue; never force/select/rewrite a job or retry a failure.
            if job not in self.committed:
                self.pending_jobs.put(job)

    def await_job(self, job):
        assert str(UUID(job)) == job and job in self.web_tasks
        self.dispatch()
        self.read_commits()
        result = self.committed[job]
        assert all(result[k] == self.web_tasks[job][k] for k in ("request_id", "run_id", "job_id"))
        return result

    def sign(self, nonce):
        observed = self.nonces.pop(nonce, None)
        assert observed is not None and time.monotonic() - observed < 30, (
            "M3_OBSERVED_CHALLENGE_REQUIRED"
        )
        now = int(time.time())
        return self.issuer.token({"iat": now, "nbf": now, "exp": now + 90, "nonce": nonce})

    def stop_ssr(self):
        p = self.bridge_process
        if p is None:
            return
        natural = p.poll()
        if natural is None:
            p.stdin.write('{"stop":true}\n')
            p.stdin.flush()
            p.wait(timeout=30)
        self.ssr_exits.append(
            {"boot": self.boot, "unexpected_exit": natural is not None, "returncode": p.returncode}
        )
        self.pipe_thread.join(timeout=5)
        assert p.returncode == 0 and natural is None and not self.pipe_thread.is_alive(), (
            "M3_SSR_PROCESS_RED"
        )
        assert (
            subprocess.run(["docker", "inspect", self.ssr_name], capture_output=True).returncode
            != 0
        )
        self.bridge_process = None

    def restart_pg(self):
        with self.transport_lock:
            with self.r.lab.connect(dbname="vrae_ra4a_p1") as c:
                if c.execute(
                    "SELECT count(*) FROM ra4a.jobs WHERE state IN ('PENDING','LEASED')"
                ).fetchone() != (0,):
                    return {"actual_pg_restart": False, "denied": "BUSY"}
            self.stop_ssr()
            write(self.native_out / "stop.json", {"stop": True})
            self.client.wait(timeout=15)
            assert self.client.returncode == 0
            assert (
                cmd(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        '{{index .Config.Labels "vrae.b5_p0"}}',
                        self.r.lab.name,
                    ]
                )
                .decode()
                .strip()
                == self.r.lab.name
            )
            before = self.r.lab.port
            cmd(["docker", "restart", self.r.lab.name])
            port = self.r.lab.refresh_port()
            self.r.reader.settings = replace(self.r.reader.settings, port=port)
            write(self.profile, self.r.profile())
            cfg = json.loads((self.folder / "m3-reviewer.private.json").read_bytes())
            cfg["port"] = port
            write(self.folder / "m3-reviewer.private.json", cfg)

            def ready():
                try:
                    with self.r.lab.connect(dbname="vrae_ra4a_p1") as c:
                        return c.execute("SELECT 1").fetchone() == (1,)
                except psycopg.OperationalError:
                    return False

            wait(ready, 60)
            self.issuer = Issuer()
            self.profile_data["anchor"]["jwks"] = json.loads(self.issuer.jwks())
            self.nonces.clear()
            self.start_native()
            self.start_ssr()
            result = {
                "actual_pg_restart": True,
                "ssr_process_restarted": True,
                "app_process_restarted": True,
                "routing_volume_preserved": True,
                "new_issuer_key": True,
            }
            write(
                self.folder / ("restart-" + str(self.boot) + ".json"),
                {
                    **result,
                    "previous_port": before,
                    "owned_loopback_port": port,
                    "migrations_rerun": False,
                    "results_reseeded": False,
                },
            )
            return result

    def cleanup(self):
        errors = []
        extra = []
        try:
            if self.http is not None:
                self.http.shutdown()
                self.http.server_close()
                self.http_thread.join(timeout=5)
                assert not self.http_thread.is_alive()
                import socket

                with socket.socket() as probe:
                    probe.settimeout(1)
                    assert probe.connect_ex(("127.0.0.1", self.http.server_port)) != 0
                extra.append(
                    {"resource": "finite_loopback_transport", "absent_or_port_closed": True}
                )
            self.stop_ssr()
            extra.append({"resource": "single_m2_ssr", "absent_or_port_closed": True})
        except Exception as exc:
            errors.append(type(exc).__name__)
            if self.bridge_process is not None:
                owned = (
                    cmd(
                        [
                            "docker",
                            "inspect",
                            "--format",
                            '{{index .Config.Labels "vrae.beta.codex3"}}',
                            self.ssr_name,
                        ]
                    )
                    .decode()
                    .strip()
                )
                assert owned == self.label
                cmd(["docker", "rm", "-f", self.ssr_name])
                self.bridge_process.wait(timeout=15)
                self.pipe_thread.join(timeout=5)
        finally:
            try:
                super().cleanup()
            finally:
                if self.routing_created:
                    assert (
                        cmd(
                            [
                                "docker",
                                "volume",
                                "inspect",
                                "--format",
                                '{{index .Labels "vrae.beta.codex3"}}',
                                self.routing,
                            ]
                        )
                        .decode()
                        .strip()
                        == self.label
                    )
                    cmd(["docker", "volume", "rm", self.routing])
                    assert (
                        subprocess.run(
                            ["docker", "volume", "inspect", self.routing], capture_output=True
                        ).returncode
                        != 0
                    )
                    extra.append(
                        {"resource": "durable_routing_volume", "absent_or_port_closed": True}
                    )
                self.result["cleanup"].extend(extra)
                self.result["cleanup_errors"].extend(errors)
                self.result["ssr_process_observation"] = self.ssr_exits
                write(self.folder / "http-observations.private.json", self.http_observations)
                write(self.folder / "browser-tasks.private.json", self.web_tasks)
                assert not errors

    def publish(self):
        candidate = self.folder / "browser-acceptance"
        allowed = {"browser.json", "assertions.json", "browser-process-cleanup.json"}
        inputs = [
            p for p in candidate.glob("*") if p.suffix in (".png", ".pdf") or p.name in allowed
        ]
        for path in inputs:
            raw = path.read_bytes()
            assert not any(value.encode() in raw for value in self.secret_values), (
                "M3_PUBLICATION_SECRET_MATCH"
            )
        fatal = []
        for path in self.folder.glob("ssr-boot-*.stderr.private.log"):
            raw = path.read_bytes()
            if b"Fatal Python error" in raw or b"Segmentation fault" in raw:
                fatal.append(path.name)
        self.result["browser_publication"] = {
            "files_checked": len(inputs),
            "exact_private_credential_matches": 0,
            "raw_report_source_profiles_controls_excluded": True,
            "fatal_capture": True,
            "fatal_files": fatal,
        }
        assert not fatal, "M3_SSR_NATIVE_FATAL"
        super().publish()


def main(label, minor):
    return serve(Workbench(label, minor))


def serve(run):
    label = run.label
    stop = PRIVATE / "local-launches" / label / "stop.json"
    try:
        for name, function in (
            ("owned_pg_m1_m2", run.start_pg),
            ("original_api_worker", run.start_native),
            ("genuine_bootstrap_assignment", run.bootstrap_identity),
            ("single_m2_ssr", run.start_ssr),
        ):
            if stop.exists():
                run.result["status"] = "CANCELLED_DURING_STARTUP"
                return
            run.case(name, function)
        run.result["status"] = "M3_READY"
        write(
            run.folder / "started.json",
            {"origin": run.r.origin, "source_sha": run.result["source_sha"], "mode": MODE},
        )
        controls = run.folder / "m3-control"
        controls.mkdir()
        deadline = time.monotonic() + 1700
        while not stop.exists() and time.monotonic() < deadline:
            assert run.client.poll() is None and run.bridge_process.poll() is None, (
                "M3_COMPONENT_EXIT"
            )
            run.dispatch()
            for request in sorted(controls.glob("*.request.json")):
                response = request.with_name(
                    request.name.replace(".request.json", ".response.json")
                )
                if response.exists():
                    continue
                body = json.loads(request.read_bytes())
                operation = body.get("operation")
                if operation == "sign" and set(body) == {"operation", "nonce"}:
                    try:
                        result = run.sign(body["nonce"])
                    except AssertionError:
                        result = {"denied": "M3_OBSERVED_FRESH_CHALLENGE_REQUIRED"}
                elif operation == "await-job" and set(body) == {"operation", "job"}:
                    result = run.await_job(body["job"])
                elif operation == "native-proof" and set(body) == {"operation"}:
                    result = json.loads(cmd(["docker", "exec", "--user", "10003:10003", run.ssr_name,
                        "python", "-c", "from pathlib import Path; print(Path('/state/l2-native/active-proof.json').read_text())"]))
                elif operation in ("s0-audit-queue", "s0-audit-result") and set(body) == {"operation", "case"}:
                    from integration.l2_ops.workbench import PreparationWorkbench
                    assert type(run) is PreparationWorkbench, "S0_PRIVATE_AUDIT_RUNTIME_REQUIRED"
                    result = run.audit_control(body["case"], read=operation == "s0-audit-result")
                elif operation == "restart-pg" and set(body) == {"operation"}:
                    result = run.case("actual_pg_restart_" + str(run.boot), run.restart_pg)
                else:
                    result = {"denied": "M3_PRIVATE_CONTROL_DENIED"}
                temporary = response.with_suffix(".tmp")
                write(temporary, result)
                temporary.chmod(0o600)
                temporary.replace(response)
            time.sleep(0.1)
    except BaseException:
        run.result["status"] = "M3_RED_PRESERVED"
        raise
    finally:
        try:
            run.case("owned_cleanup", run.cleanup)
        finally:
            run.publish()
