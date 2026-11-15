"""B6-owned private state, reusing the accepted B5A disposable PG16 lifecycle."""

from pathlib import Path
import re
import secrets
import uuid

from integration.ra4c_b5a.lab import Lab as AcceptedLab

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "integration/b6_p0/.runtime"


class Lab(AcceptedLab):
    def __init__(self, name):
        if not re.fullmatch(r"[a-z0-9-]{3,48}", name):
            raise ValueError("B6_OWNED_RUN_NAME")
        # Do not call the accepted initializer: it would write its own feature's
        # runtime directory. All B6 state is confined to this allowed new path.
        self.private = RUNTIME / name
        self.private.mkdir(parents=True, exist_ok=False)
        self.state_path = self.private / "state.json"
        ident = "vrae-b5a-" + uuid.uuid4().hex[:12]
        # The accepted start/stop retain their exact label and ownership checks;
        # this random identity is exclusively held by this B6 fixture instance.
        self.resources = [("container", ident), ("network", ident + "-net"), ("volume", ident + "-data")]
        self.name = ident
        self.state = {
            "container": ident, "host": "127.0.0.1", "dbname": "vrae_ra4a_p1",
            "admin_password": secrets.token_urlsafe(32),
            "runtime_passwords": {r: secrets.token_urlsafe(24) for r in (
                "ra4a_test_a_app", "ra4a_test_b_app", "ra4a_test_a_worker", "ra4a_test_b_worker", "ra4a_test_unassigned")},
        }
        self.port = self.dbname = None
        self.graphs = {}
