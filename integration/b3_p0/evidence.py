"""Explicit metadata-only observations; never source rows or capabilities."""

import os
from pathlib import Path
import re

from .support import encode


def record(name, facts):
    directory = os.environ.get("B3_OBSERVATIONS")
    if directory is None:
        return
    assert re.fullmatch(r"[a-z0-9-]{1,70}", name)
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (name + ".json")
    assert not path.exists()
    path.write_bytes(encode(facts))


def raw_acl(c):
    from integration.ra4e.security import table_acl_entries

    rows = c.execute(
        "SELECT relname,pg_get_userbyid(relowner),relacl::text,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace='b3_p0'::regnamespace AND relkind='r' ORDER BY 1"
    ).fetchall()
    return [
        {
            "table": name,
            "owner": owner,
            "raw_acl": raw,
            "null_acl": raw is None,
            "effective_entries": table_acl_entries(c, raw, owner),
            "rls": rls,
            "force_rls": force,
        }
        for name, owner, raw, rls, force in rows
    ]
