"""Out-of-band provisioning only; profile changes invalidate all prior sessions."""

import json
from pathlib import Path
from uuid import UUID

from vrae.b3_p0.contracts import Witness
from vrae.persistence.private_bytes import Locator

from .b5a_profile import load_profile
from .b5p0_binding import Binding
from .b5p0_http import RehearsalApplication
from .b5p0_journal import Journal
from .contracts import refuse


def load(profile, bridge, *, audit=None):
    profile, bridge = Path(profile), Path(bridge)
    base, original = load_profile(profile, audit)
    raw = bridge.read_bytes()
    cfg = json.loads(raw)
    if (
        set(cfg) != {"version", "links", "journal", "key_secret"}
        or cfg["version"] != "B5P0_TEST_ONLY_1"
        or len(raw) > 131072
    ):
        raise ValueError("B5P0_PRIVATE_PROFILE_SHAPE")
    journal = Path(cfg["journal"]).resolve()
    if not journal.is_relative_to(bridge.parent.resolve()):
        raise ValueError("B5P0_PRIVATE_JOURNAL_PATH")
    bindings = {}
    for key, row in cfg["links"].items():
        if set(row) != {"issuer", "subject", "role", "location", "witness", "b3_subject"}:
            raise ValueError("B5P0_BINDING_SHAPE")
        bindings[key] = Binding(
            row["issuer"],
            row["subject"],
            row["role"],
            Witness(UUID(row["witness"]), Locator(**row["location"])),
            row["b3_subject"],
        )
    if set(bindings) != set(base.sessions.bindings):
        raise ValueError("B5P0_EXACT_ASSIGNMENTS_REQUIRED")

    def fresh():
        try:
            if profile.read_bytes() != original or bridge.read_bytes() != raw:
                raise ValueError("B5P0_PROVISIONING_CHANGED")
        except Exception:
            base.sessions.sessions.clear()
            base.sessions.actions.clear()
            base.sessions.challenges.clear()
            refuse("UNAUTHORIZED")

    return RehearsalApplication(
        base,
        bindings,
        Journal(journal),
        key_secret=bytes.fromhex(cfg["key_secret"]),
        audit=audit,
        refresh=fresh,
    )
