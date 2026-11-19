"""Current PG source -> original NativeSource and original review ledger.

This port deliberately retains NativeSource's CONTROLLED review restriction.
A verified-human release profile must be reviewed separately; neither an invite,
Worker COMMIT nor a controlled review can authorize customer publication.
"""

import base64
from contextlib import contextmanager
import hashlib
import json
from vrae.evidence import EvidencePack
from vrae.l2.native import NativeSource, NativeTask
from vrae.l2.ledger import Ledger
from integration.authorized_targets.store import connect
from contracts.l2_launch.contract import canonical


@contextmanager
def current_review(binding, job_id, path, directory):
    # The original PostgreSQL source/subject/policy/assignment locks are retained
    # through the ledger operation, with a final fresh check before PG COMMIT.
    with connect(binding) as c, c.transaction():

        def current():
            return bytes(
                c.execute(
                    "SELECT target_v1.review_source(%s,%s)", (binding["tenant_id"], job_id)
                ).fetchone()[0]
            )

        raw = current()
        d = json.loads(raw)
        if d["task"]["tenant_id"] != binding["tenant_id"] or d["task"]["job_id"] != str(job_id):
            raise ValueError("CURRENT_REVIEW_SCOPE")
        objects = {k: base64.b64decode(v, validate=True) for k, v in d["objects_base64"].items()}
        pack = EvidencePack(canonical(d["pack"]), tuple(sorted(objects.items())))
        held = NativeTask(**d["native_document"]["native_context"])
        source = NativeSource(pack, d["diagnosis"], held=held)
        replay = source.read()
        if replay.display_hash != d["display_hash"] or replay.version != d["version"]:
            raise ValueError("CURRENT_REVIEW_REPLAY")
        ledger = Ledger(path, source, directory)
        yield ledger
        if hashlib.sha256(current()).digest() != hashlib.sha256(raw).digest():
            raise ValueError("CURRENT_REVIEW_CHANGED")
