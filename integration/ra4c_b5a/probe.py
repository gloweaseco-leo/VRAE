"""First real public-API compatibility gate, no HTTP or decision writes."""

import json
import time

from apps.operator_console.b5a_reader import OriginalPins, ReviewerReader, catalog_digest
from apps.operator_console.fixtures import make_fixture
from tests.identity.issuer import Issuer, ISSUER, AUDIENCE
from vrae.identity.boundary import Assignment, IdentityBoundary, TrustAnchor
from vrae.persistence.private_bytes import descriptors, locator
from vrae.reviewing.canonical import sha

from .lab import Lab


def provision(lab, audit=None):
    metadata, _ = make_fixture()
    tasks = {case: metadata.repository.task("task-" + case) for case in ["404", "200"]}
    pins = {
        locator(g): OriginalPins(
            case, locator(g), sha(g.target), sha(g.manifest), tuple(descriptors(g.artifacts))
        )
        for case, g in lab.graphs.items()
    }
    settings = lab.settings()
    with settings.connect() as c:
        schema = catalog_digest(c)
    reader = ReviewerReader(settings, pins, tasks, schema, audit=audit)
    return reader, tasks


def main():
    lab = Lab("entry-probe-311-01")
    try:
        lab.start()
        reader, tasks = provision(lab)
        issuer = Issuer()
        now = int(time.time())
        records = []
        for case, g in lab.graphs.items():
            p = locator(g)
            binding = Assignment(ISSUER, "synthetic-reviewer-1", reader.settings.user, p, now + 120)
            boundary = IdentityBoundary(
                anchor=TrustAnchor(ISSUER, AUDIENCE, issuer.jwks(), now + 120),
                assignments=[binding],
                connect=lambda role: reader.settings.connect(),
                skew=0,
            )
            nonce = "b5a-entry-probe-server-challenge-0001"
            token = issuer.token({"iat": now, "nbf": now, "exp": now + 60, "nonce": nonce})
            observed = boundary.check(token, p, nonce=nonce)
            with reader.request(binding) as value:
                dossier = value["dossier"]
                assert dossier["_artifacts"]["document"] == next(
                    a.raw for a in g.artifacts if a.kind == "DRAFT"
                )
                assert len(dossier["document"]["issues"]) == (1 if case == "404" else 0)
                assert len(dossier["evidence"]) == (6 if case == "404" else 3)
                records.append(
                    {
                        "case": case,
                        "identity": observed.authority,
                        "role": reader.settings.user,
                        "issues": len(dossier["document"]["issues"]),
                        "claims": len(dossier["evidence"]),
                        "source_sha256": dossier["origin"]["source_sha256"],
                        "read_original": True,
                    }
                )
        print(json.dumps({"status": "ACTUAL_REVIEWER_PUBLIC_API_PROBE_PASS", "records": records}))
        (lab.private / "result.json").write_text(json.dumps(records), encoding="utf-8")
    finally:
        lab.stop()


if __name__ == "__main__":
    main()
