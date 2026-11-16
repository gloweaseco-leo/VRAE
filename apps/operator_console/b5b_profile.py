"""Local B5B policy configuration; existing signed B5/B3 provisioning unchanged."""

import json
from pathlib import Path
from vrae.persistence.private_bytes import Locator
from vrae.b6_p0.reader import PrivateHandoffReader, RecipientPolicyDescriptor
from .b5p0_profile import load as load_rehearsal
from .b5b_http import Application
from .contracts import refuse


def load(profile, bridge, policies, *, audit=None, generated_profile=None, deep_profile=None):
    app = load_rehearsal(profile, bridge, audit=audit)
    policies = Path(policies)
    raw = policies.read_bytes()
    if not 1 <= len(raw) <= 131072:
        raise ValueError("B5B_POLICY_PROFILE_BOUND")

    def unique(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError("B5B_POLICY_DUPLICATE")
            result[k] = v
        return result

    cfg = json.loads(raw, object_pairs_hook=unique)
    if set(cfg) != {"version", "policies"} or cfg["version"] != "B5B_PRIVATE_POLICY_1":
        raise ValueError("B5B_POLICY_PROFILE_SHAPE")
    descriptors = {}
    for task, row in cfg["policies"].items():
        row = dict(row)
        row["location"] = Locator(**row["location"])
        descriptors[task] = RecipientPolicyDescriptor(**row)
    handoff = PrivateHandoffReader(app.sessions, descriptors)

    def fresh():
        try:
            if policies.read_bytes() != raw:
                refuse("UNAUTHORIZED")
        except Exception:
            refuse("UNAUTHORIZED")

    generated = None
    if generated_profile is not None:
        from .b5b_m2_profile import load as load_generated
        generated = load_generated(generated_profile)
    deep = None
    if deep_profile is not None:
        from .l2_profile import load as load_deep
        deep = load_deep(deep_profile)
    return Application(app, handoff, refresh=fresh, generated=generated, deep=deep)
