"""Bounded child lifecycle using only the accepted low-role profiles."""

import json
import os
import subprocess
import sys
import time
import uuid
from .support import ROOT


class Child:
    def __init__(self, runtime):
        self.runtime = runtime
        self.process = None
        self.streams = []
        self.profile = runtime.lab.private / "reviewer.json"
        self.bridge = runtime.lab.private / "bridge.json"
        self.policies = runtime.lab.private / "policies.json"
        self.audit = runtime.lab.private / "child-audit.jsonl"
        for path, value in (
            (self.profile, runtime.profile()),
            (self.bridge, runtime.bridge_profile()),
            (self.policies, runtime.policy_profile()),
        ):
            path.write_text(json.dumps(value), encoding="utf-8")

    def start(self):
        name = "child-" + uuid.uuid4().hex[:8]
        ready = self.runtime.lab.private / (name + "-ready.json")
        args = []
        for key, path in (
            ("profile", self.profile),
            ("bridge", self.bridge),
            ("policies", self.policies),
            ("audit", self.audit),
            ("ready", ready),
        ):
            args += ["--" + key, str(path)]
        self.streams = [
            (self.runtime.lab.private / (name + suffix)).open("wb")
            for suffix in (".stdout.log", ".stderr.log")
        ]
        self.process = subprocess.Popen(
            [sys.executable, "-B", "-m", "integration.b5b.http_server", *args],
            cwd=ROOT,
            stdout=self.streams[0],
            stderr=self.streams[1],
            env=dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1"),
        )
        deadline = time.monotonic() + 30
        while not ready.exists():
            if self.process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("B5B_CHILD_NOT_READY")
            time.sleep(0.05)
        self.origin = json.loads(ready.read_bytes())["origin"]
        return self

    def stop(self):
        before = self.process.poll() if self.process else None
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=15)
        assert self.process is None or self.process.poll() is not None
        for stream in self.streams:
            stream.close()
        if self.process:
            (self.runtime.lab.private / 'child-process-cleanup.json').write_text(
                json.dumps({'exit_before_cleanup': before, 'exit_after_cleanup': self.process.poll()}),
                encoding='utf-8',
            )
