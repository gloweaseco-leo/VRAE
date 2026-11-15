"""Own fixture storage; inherit accepted real PG lifecycle and B5/B3 operations."""

from dataclasses import asdict
from pathlib import Path
import re
import secrets
import threading
import time
import uuid
from apps.operator_console.b5a_http import Application as BaseApplication, server
from apps.operator_console.b5p0_http import RehearsalApplication
from apps.operator_console.b5b_http import Application
from vrae.b6_p0.reader import PrivateHandoffReader, RecipientPolicyDescriptor
from integration.ra4c_b5p0.lab import Lab as AcceptedLab
from integration.ra4c_b5p0.support import Runtime as AcceptedRuntime, Slice

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path(__file__).resolve().parent / ".runtime"


class Lab(AcceptedLab):
    def __init__(self, name):
        if not re.fullmatch(r"[a-z0-9-]{3,48}", name):
            raise ValueError("B5B_OWNED_LABEL_REQUIRED")
        self.private = PRIVATE / name
        self.private.mkdir(parents=True, exist_ok=False)
        self.state_path = self.private / "state.json"
        self.name = "vrae-b5p0-" + uuid.uuid4().hex[:12]
        self.resources = [
            ("container", self.name),
            ("network", self.name + "-net"),
            ("volume", self.name + "-data"),
        ]
        self.state = {
            "container": self.name,
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
        self.port = self.dbname = None
        self.graphs = {}


class Runtime(AcceptedRuntime):
    def __init__(self, name, shared=None):
        self.shared = shared
        self.lab = Lab(name) if shared is None else Slice(shared, name)
        self.events, self.secrets = [], []
        self.http = self.thread = None
        self.hook = None

    def policies(self):
        return {
            task: RecipientPolicyDescriptor(
                b.issuer, b.subject, b.db_role, b.location, "pol-001", 1, int(time.time()) + 1800
            )
            for task, b in self.bindings.items()
        }

    def policy_profile(self):
        return {
            "version": "B5B_PRIVATE_POLICY_1",
            "policies": {k: asdict(v) for k, v in self.policies().items()},
        }

    def launch(self):
        self.base = BaseApplication(self.store, self.tasks)
        self.app = RehearsalApplication(
            self.base, self.links, self.journal, key_secret=self.secret, audit=self.event
        )
        self.handoff = PrivateHandoffReader(self.store, self.policies())
        self.consumer = Application(self.app, self.handoff)
        self.http = server(self.consumer)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.origin = self.consumer.origin
