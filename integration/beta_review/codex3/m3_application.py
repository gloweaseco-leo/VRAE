"""M3 local controller; accepted M1 generation, one existing SSR, no M2 fabrication."""

import json
import time
from dataclasses import replace

import psycopg

from .m3_bootstrap import install
from .runner import PRIVATE, Run, cmd, wait, write

MODE = "M1_GENERATED_REPORTS_M2_UI_PENDING"


class GeneratedRun(Run):
    native_module = "integration.beta_review.codex3.m3_native"

    def __init__(self, label, minor):
        super().__init__(label, minor, b5=True)
        self.boot = 0
        self.generated_dependencies = [
            {
                "interface": "M1 APP202 -> actual generated result",
                "state": "CONNECTED_ACCEPTED_PR104",
            },
            {"interface": "M2 signed SSR review/decision/A4", "state": "PENDING_OWNER_MERGED_M2"},
        ]
        self.result["scope"] = MODE

    def start_pg(self):
        super().start_pg()
        self.result["m1_bootstrap"] = install(self.r.lab)
        s = self.r.lab.state
        profile = {
            "host": "127.0.0.1",
            "port": self.r.lab.port,
            "dbname": "vrae_ra4a_p1",
            "role": "p2b1_test_a_reviewer",
            "password": s["runtime_passwords"]["p2b1_test_a_reviewer"],
        }
        write(self.folder / "m3-reviewer.private.json", profile)

    def start_native(self):
        self.native_out = self.folder / "native" / ("boot-" + str(self.boot))
        self.boot += 1
        super().start_native()
        write(
            self.folder / "m3-runtime.json",
            {
                "mode": MODE,
                "source_sha": self.result["source_sha"],
                "native_out": str(self.native_out.relative_to(self.folder)),
                "worker_processing": "vrae.application.ra4b_p2.m1.runtime",
                "review_ui": "PENDING_OWNER_MERGED_M2",
                "ssr_is_generated_job_reviewer": False,
            },
        )

    def publish(self):
        self.result["generated_jobs"] = []
        registry = self.folder / "m3-tasks"
        if registry.exists():
            for file in sorted(registry.glob("*.json")):
                task = json.loads(file.read_bytes())
                self.result["generated_jobs"].append(
                    {
                        "case": task["source"],
                        "request_sha256": __import__("hashlib")
                        .sha256(task["request_id"].encode())
                        .hexdigest(),
                        "job_sha256": __import__("hashlib")
                        .sha256(task["job_id"].encode())
                        .hexdigest(),
                    }
                )
        super().publish()

    def restart_pg(self):
        # Only the trusted controller inspects its own disposable DB for an idle
        # restart. API/Worker/SSR are still low-role and receive no admin profile.
        with self.r.lab.connect(dbname="vrae_ra4a_p1") as c:
            if c.execute(
                "SELECT count(*) FROM ra4a.jobs WHERE state IN ('PENDING','LEASED')"
            ).fetchone() != (0,):
                return {"actual_pg_restart": False, "denied": "M3_RESTART_REQUIRES_IDLE_QUEUE"}
        from .native_observation import stopped

        assert stopped(self, "m3_pg_restart") is None
        self.intentional_ssr_stop = self.ssr
        write(self.native_out / "stop.json", {"stop": True})
        self.client.wait(timeout=15)
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
        previous_port = self.r.lab.port
        cmd(["docker", "restart", self.r.lab.name])
        current_port = self.r.lab.refresh_port()
        self.r.reader.settings = replace(self.r.reader.settings, port=current_port)
        write(self.profile, self.r.profile())
        reviewer = json.loads((self.folder / "m3-reviewer.private.json").read_bytes())
        reviewer["port"] = current_port
        write(self.folder / "m3-reviewer.private.json", reviewer)
        write(
            self.folder / ("restart-transport-" + str(self.boot) + ".json"),
            {
                "previous_port": previous_port,
                "observed_owned_loopback_port": current_port,
                "ownership_verified_by_accepted_lab": True,
            },
        )

        def ready():
            try:
                with self.r.lab.connect(dbname="vrae_ra4a_p1") as c:
                    return c.execute("SELECT 1").fetchone() == (1,)
            except psycopg.OperationalError:
                return False

        wait(ready, 60)
        self.start_native()
        self.start_ssr()
        return {
            "actual_pg_restart": True,
            "migrations_rerun": False,
            "results_reseeded": False,
            "native_boot": self.boot,
            "transport_mapping_refreshed": True,
        }


def main(label, minor):
    launch = PRIVATE / "local-launches" / label
    stop = launch / "stop.json"
    r = GeneratedRun(label, minor)
    try:
        for name, fn in (
            ("accepted_pg_and_m1_inputs", r.start_pg),
            ("actual_m1_api_worker_start", r.start_native),
            ("single_existing_ssr_start", r.start_ssr),
        ):
            if stop.exists():
                r.result["status"] = "CANCELLED_DURING_STARTUP"
                return
            r.case(name, fn)
        r.result["status"] = "M1_READY_M2_UI_PENDING"
        write(
            r.folder / "started.json",
            {"origin": r.r.origin, "source_sha": r.result["source_sha"], "mode": MODE},
        )
        requests = r.folder / "m3-control"
        requests.mkdir()
        deadline = time.monotonic() + 1700
        while not stop.exists() and time.monotonic() < deadline:
            assert r.client.poll() is None and r.ssr.poll() is None, "M3_COMPONENT_EXIT"
            for request in sorted(requests.glob("*.request.json")):
                response = request.with_name(
                    request.name.replace(".request.json", ".response.json")
                )
                if response.exists():
                    continue
                body = json.loads(request.read_bytes())
                assert set(body) == {"operation"} and body["operation"] == "restart-pg"
                result = r.case("actual_pg_restart_" + str(r.boot), r.restart_pg)
                temporary = response.with_suffix(".tmp")
                write(temporary, result)
                temporary.replace(response)
            time.sleep(0.2)
    except BaseException:
        r.result["status"] = "M3_RED_PRESERVED"
        raise
    finally:
        try:
            r.case("owned_cleanup", r.cleanup)
        finally:
            r.publish()
