"""Only the disposable fixture holds admin/signer; HTTP uses Reviewer settings."""

from dataclasses import asdict
import json
import secrets
import threading
import time
from uuid import uuid4

from apps.operator_console.b5a_http import Application, server
from apps.operator_console.b5a_sessions import SessionStore
from apps.operator_console.b5p0_binding import Binding, mapping_subject
from apps.operator_console.b5p0_http import RehearsalApplication
from apps.operator_console.b5p0_journal import Journal
from integration.ra4c_b5a.probe import provision
from integration.ra4c_b5a.support import Client, Forms, Runtime as OldRuntime
from integration.b3_p0.support import bootstrap, counts, protected
from tests.identity.issuer import Issuer, ISSUER, AUDIENCE
from vrae.identity.boundary import Assignment, TrustAnchor
from vrae.b3_p0.contracts import Witness
from vrae.persistence.private_bytes import locator

from .lab import Lab


class Runtime:
    def __init__(self, name, shared=None):
        self.shared = shared
        self.lab = Lab(name) if shared is None else Slice(shared, name)
        self.events, self.secrets = [], []
        self.http = self.thread = None
        self.hook = None

    def event(self, value):
        self.events.append(value)
        if self.hook:
            self.hook(value)

    def bootstrap(self):
        self.lab.start()
        if self.shared is None:
            bootstrap(self.lab)
        self.reader, self.tasks = provision(self.lab, self.event)
        self.issuer = Issuer()
        now = int(time.time())
        self.bindings = {
            "task-" + case: Assignment(
                ISSUER, "synthetic-reviewer-1", self.reader.settings.user, locator(g), now + 1800
            )
            for case, g in self.lab.graphs.items()
        }
        self.store = SessionStore(
            anchor=TrustAnchor(ISSUER, AUDIENCE, self.issuer.jwks(), now + 1800),
            bindings=self.bindings,
            readers={self.reader.settings.user: self.reader},
        )
        self.links = {}
        with self.lab.connect() as c:
            for task, b in self.bindings.items():
                subject = mapping_subject(b.issuer, b.subject, b.db_role, b.location)
                token = uuid4()
                loc = b.location
                c.execute(
                    "INSERT INTO b3_p0.witnesses VALUES(%s,%s,%s,%s,1,clock_timestamp()+interval '30 minutes',%s,%s,%s,%s,%s)",
                    (
                        loc.tenant,
                        token,
                        b.db_role,
                        subject,
                        loc.ref_id,
                        loc.source_run,
                        loc.report,
                        loc.version,
                        loc.target_digest,
                    ),
                )
                self.links[task] = Binding(
                    b.issuer, b.subject, b.db_role, Witness(token, loc), subject
                )
        self.secret = secrets.token_bytes(32)
        self.journal = Journal(self.lab.private / "recovery.sqlite")
        self.initial_roots = self.roots()
        return self

    def start(self):
        self.bootstrap()
        self.launch()
        return self

    def launch(self):
        self.base = Application(self.store, self.tasks)
        self.app = RehearsalApplication(
            self.base, self.links, self.journal, key_secret=self.secret, audit=self.event
        )
        self.http = server(self.app)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.origin = self.app.origin

    def client(self):
        return Client(self.origin)

    def form(self, client, case="404"):
        path = "/b5a/tasks/task-" + case + "/rehearsal"
        status, body, _ = client.request("GET", path)
        assert status == 200, body[:100]
        fields = Forms(body.decode()).forms[path]
        from integration.ra4a.p2b1_support import proposal

        cmd = proposal(self.lab.graphs[case]).document
        fields["action"] = cmd.get("action", "SIMULATED_INTERNAL_SCOPE_ACK")
        fields["reason"] = cmd["reason"] or ""
        for i, d in enumerate(cmd["dispositions"]):
            fields["disposition." + str(i)] = d["disposition"]
        return path, fields, body

    def data(self):
        with self.lab.connect() as c:
            return counts(c)

    def roots(self):
        with self.lab.connect() as c:
            return protected(c)

    def original_facts(self, case):
        from vrae.reviewing.canonical import sha

        with self.reader.request(self.bindings["task-" + case]) as actual:
            facts = {
                "case": case,
                "target_sha256": actual["pin"].target_sha256,
                "manifest_sha256": actual["pin"].manifest_sha256,
                "objects": [
                    {"kind": kind, "key": key, "length": len(raw), "sha256": sha(raw)}
                    for (kind, key), raw in sorted(actual["raw"].items())
                ],
            }
        return facts

    def profile(self):
        return OldRuntime.profile(self)

    def bridge_profile(self):
        return {
            "version": "B5P0_TEST_ONLY_1",
            "journal": str(self.journal.path),
            "key_secret": self.secret.hex(),
            "links": {
                k: {
                    "issuer": v.issuer,
                    "subject": v.subject,
                    "role": v.role,
                    "location": asdict(v.witness.location),
                    "witness": str(v.witness.token),
                    "b3_subject": v.b3_subject,
                }
                for k, v in self.links.items()
            },
        }

    def stop(self):
        # Publication scanner inputs are private, never a public evidence file.
        if self.lab.private.exists():
            values = [
                self.lab.state["admin_password"],
                *self.lab.state["runtime_passwords"].values(),
                *self.secrets,
            ]
            if hasattr(self, "links"):
                values += [str(v.witness.token) for v in self.links.values()]
            (self.lab.private / "scan-secrets.json").write_text(
                json.dumps(values), encoding="utf-8"
            )
        if self.http:
            self.http.shutdown()
            self.http.server_close()
        if self.thread:
            self.thread.join(timeout=10)
        if hasattr(self, "initial_roots"):
            from collections import Counter

            observations = {
                "case_id": getattr(self, "case_id", "separate_browser_fixture"),
                "event_counts": dict(Counter(e["event"] for e in self.events)),
                "sqlstates": [
                    {k: v for k, v in e.items() if k in {"event", "sqlstate", "table"}}
                    for e in self.events
                    if "sqlstate" in e
                ],
                "protected_roots_before": self.initial_roots,
                "protected_roots_after": self.roots(),
                "counts": self.data(),
                "verified_originals": [
                    e for e in self.events if e["event"] == "native_original_verified"
                ],
                "original_descriptors": getattr(self, "original_descriptors", []),
            }
            (self.lab.private / "observations.json").write_text(
                json.dumps(observations, sort_keys=True), encoding="utf-8"
            )
        self.lab.stop()


class Slice:
    """Real isolated DB cloned from accepted disposable schema, never fake SQL."""

    def __init__(self, owner, name):
        self.owner = owner
        self.private = owner.private / name
        self.private.mkdir(parents=True, exist_ok=False)
        self.dbname = "vrae_p2b1_" + uuid4().hex[:12]
        self.graphs = owner.graphs
        self.state = owner.state
        self.name = owner.name

    def start(self):
        from psycopg import sql

        with self.owner.connect(dbname="postgres") as c:
            c.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                    sql.Identifier(self.dbname), sql.Identifier(self.owner.dbname)
                )
            )

    def connect(self, role="postgres", dbname=None):
        return self.owner.connect(role, dbname or self.dbname)

    def settings(self, role="p2b1_test_a_reviewer"):
        from apps.operator_console.b5a_reader import ReviewerSettings

        return ReviewerSettings(
            "127.0.0.1", self.owner.port, self.dbname, role, self.state["runtime_passwords"][role]
        )

    def refresh_port(self):
        return self.owner.refresh_port()

    def stop(self):
        import re
        from psycopg import sql

        assert re.fullmatch(r"vrae_p2b1_[0-9a-f]{12}", self.dbname)
        with self.owner.connect(dbname="postgres") as c:
            c.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(self.dbname)))
        (self.private / "cleanup.json").write_text(
            json.dumps({"database_dropped": True, "shared_pg16": True}), encoding="utf-8"
        )
