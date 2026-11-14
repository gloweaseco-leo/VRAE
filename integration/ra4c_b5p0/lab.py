"""Disposable B5P0 PG16 bootstrap; only accepted migrations and synthetic originals."""

from contextlib import contextmanager
import json
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
import uuid

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "integration/ra4c_b5p0/.runtime"
LABEL = "vrae.b5_p0"


def docker(*args):
    p = subprocess.run(["docker", *args], capture_output=True, timeout=90)
    if p.returncode:
        raise RuntimeError("B5P0_OWNED_DOCKER_FAILED") from None
    return p.stdout


@contextmanager
def wire(path):
    from integration.ra4a import support, p2a_support, p2b1_support

    modules = (support, p2a_support, p2b1_support)
    previous = [m.STATE for m in modules]
    for m in modules:
        m.STATE = path
    try:
        yield support, p2a_support, p2b1_support
    finally:
        for m, value in zip(modules, previous, strict=True):
            m.STATE = value


class Lab:
    def __init__(self, name):
        if not re.fullmatch(r"[a-z0-9-]{3,48}", name):
            raise ValueError("B5P0_RUN_NAME")
        self.private = RUNTIME / name
        self.private.mkdir(parents=True, exist_ok=False)
        self.state_path = self.private / "state.json"
        ident = "vrae-b5p0-" + uuid.uuid4().hex[:12]
        self.resources = [
            ("container", ident),
            ("network", ident + "-net"),
            ("volume", ident + "-data"),
        ]
        self.name = ident
        self.state = {
            "container": ident,
            "host": "127.0.0.1",
            "dbname": "vrae_ra4a_p1",
            "admin_password": secrets.token_urlsafe(32),
            "runtime_passwords": {
                r: secrets.token_urlsafe(24)
                for r in [
                    "ra4a_test_a_app",
                    "ra4a_test_b_app",
                    "ra4a_test_a_worker",
                    "ra4a_test_b_worker",
                    "ra4a_test_unassigned",
                ]
            },
        }
        self.port = None
        self.dbname = None
        self.graphs = {}

    def save(self):
        self.state_path.write_text(json.dumps(self.state), encoding="utf-8")

    def connect(self, role="postgres", dbname=None):
        return psycopg.connect(
            host="127.0.0.1",
            port=self.port,
            dbname=dbname or self.dbname or "vrae_ra4a_p1",
            user=role,
            password=self.state["admin_password"]
            if role == "postgres"
            else self.state["runtime_passwords"][role],
            autocommit=True,
            connect_timeout=3,
        )

    def start(self):
        image = (ROOT / "infra/ra4a/image.txt").read_text().strip()
        cfg = self.private / "postgres.env"
        cfg.write_text(
            "POSTGRES_PASSWORD="
            + self.state["admin_password"]
            + "\nPOSTGRES_DB=vrae_ra4a_p1\nPOSTGRES_INITDB_ARGS=--auth-host=scram-sha-256\n"
        )
        try:
            docker("network", "create", "--label", LABEL + "=" + self.name, self.name + "-net")
            docker("volume", "create", "--label", LABEL + "=" + self.name, self.name + "-data")
            docker(
                "run",
                "-d",
                "--name",
                self.name,
                "--network",
                self.name + "-net",
                "--label",
                LABEL + "=" + self.name,
                "--env-file",
                str(cfg),
                "-p",
                "127.0.0.1::5432",
                "--mount",
                "type=volume,src=" + self.name + "-data,dst=/var/lib/postgresql/data",
                "--memory",
                "512m",
                "--cpus",
                "1",
                "--pids-limit",
                "128",
                image,
            )
            endpoints = json.loads(
                docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", self.name)
            )["5432/tcp"]
            assert len(endpoints) == 1 and endpoints[0]["HostIp"] == "127.0.0.1"
            self.port = int(endpoints[0]["HostPort"])
            self.state["port"] = self.port
            self.save()
            deadline = time.monotonic() + 60
            while True:
                try:
                    with self.connect() as c:
                        assert (
                            160000
                            <= c.execute(
                                "SELECT current_setting('server_version_num')::int"
                            ).fetchone()[0]
                            < 170000
                        )
                    break
                except psycopg.OperationalError:
                    if time.monotonic() > deadline:
                        raise RuntimeError("B5P0_PG_READINESS") from None
                    time.sleep(0.25)
            with wire(self.state_path) as (_, p2a, p2b1):
                p2b1.migrate_p2b1()
                p2b1.seed_base()
                self.state = json.loads(self.state_path.read_text())
                self.dbname = "vrae_p2b1_" + uuid.uuid4().hex[:12]
                with self.connect(dbname="postgres") as c:
                    c.execute(
                        sql.SQL("CREATE DATABASE {} TEMPLATE vrae_ra4a_p1").format(
                            sql.Identifier(self.dbname)
                        )
                    )
                self.graphs = {case: p2a.graph(case) for case in ["404", "200"]}
                for graph in self.graphs.values():
                    p2b1.register_graph(self.dbname, graph)
        finally:
            cfg.unlink(missing_ok=True)
        return self

    def settings(self, role="p2b1_test_a_reviewer"):
        from apps.operator_console.b5a_reader import ReviewerSettings

        return ReviewerSettings(
            "127.0.0.1", self.port, self.dbname, role, self.state["runtime_passwords"][role]
        )

    def refresh_port(self):
        labels = json.loads(docker("inspect", "--format", "{{json .Config.Labels}}", self.name))
        assert labels.get(LABEL) == self.name
        endpoints = json.loads(
            docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", self.name)
        )["5432/tcp"]
        assert len(endpoints) == 1 and endpoints[0]["HostIp"] == "127.0.0.1"
        self.port = int(endpoints[0]["HostPort"])
        self.state["port"] = self.port
        self.save()
        return self.port

    def stop(self):
        rows = []
        for kind, name in self.resources:
            assert name in [v for _, v in self.resources] and re.fullmatch(
                r"vrae-b5p0-[0-9a-f]{12}(-net|-data)?", name
            )
            template = "{{json .Config.Labels}}" if kind == "container" else "{{json .Labels}}"
            probe = subprocess.run(
                ["docker", kind, "inspect", "--format", template, name], capture_output=True
            )
            if probe.returncode == 0:
                assert json.loads(probe.stdout).get(LABEL) == self.name
                docker(*(["rm", "-f", name] if kind == "container" else [kind, "rm", name]))
            else:
                assert b"no such" in probe.stderr.lower() or b"not found" in probe.stderr.lower()
            absent = subprocess.run(["docker", kind, "inspect", name], capture_output=True)
            assert absent.returncode and (
                b"no such" in absent.stderr.lower() or b"not found" in absent.stderr.lower()
            )
            rows.append({"kind": kind, "absent": True})
        if self.port:
            with socket.socket() as s:
                s.settimeout(1)
                assert s.connect_ex(("127.0.0.1", self.port)) != 0
        self.state_path.unlink(missing_ok=True)
        (self.private / "cleanup.json").write_text(
            json.dumps({"resources": rows, "port_closed": True}), encoding="utf-8"
        )
