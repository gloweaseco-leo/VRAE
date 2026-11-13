"""Pure independent provenance/refusal checks; no PostgreSQL or driver required."""

from dataclasses import replace
import json
import pytest

from tests.reviewing.synthetic import inputs
from vrae.persistence.contracts import PersistenceError
from vrae.persistence.private_bytes import (
    Artifact,
    assemble,
    descriptors,
    production_store_port,
    verify,
)
from vrae.reviewing.canonical import canonical, SOURCE_LIMIT


def accepted(case="404"):
    i = inputs(case)
    return assemble("accepted-" + case, i.document, i.html, i.source, trust=i.trust)


@pytest.mark.parametrize("case", ["404", "200"])
def test_p2a_complete_original_byte_graph(case):
    g = accepted(case)
    assert verify(g, provenance=g) == g
    assert {
        "DRAFT",
        "HTML",
        "SOURCE",
        "PACK",
        "PACKAGE",
        "GUARD",
        "METADATA",
        "CSS",
        "TARGET",
        "SOURCE_OBJECT",
    } == {a.kind for a in g.artifacts}


@pytest.mark.parametrize(
    "kind", ["DRAFT", "HTML", "SOURCE", "GUARD", "CSS", "SOURCE_OBJECT", "TARGET"]
)
def test_p2a_recalculated_hash_does_not_replace_independent_bytes(kind):
    g = accepted()
    items = tuple(
        Artifact(a.kind, a.key, a.raw + b" ") if a.kind == kind else a for a in g.artifacts
    )
    bad = replace(g, artifacts=items, manifest=canonical(descriptors(items), limit=SOURCE_LIMIT))
    with pytest.raises(PersistenceError):
        verify(bad, provenance=g)


@pytest.mark.parametrize(
    "actor", [None, {"role": "ADMIN"}, {"approved": True}, {"token": "not-identity"}]
)
def test_p2a_production_session_store_and_approval_always_deny(actor):
    with pytest.raises(PersistenceError, match="P2A_PRODUCTION_IDENTITY_OBJECT_REVIEW_DENIED"):
        production_store_port(actor=actor, operation="SHARE_OR_APPROVE")


def test_p2a_zero_issue_keeps_native_null_and_private():
    g = accepted("200")
    d = json.loads(next(a.raw for a in g.artifacts if a.kind == "DRAFT"))
    assert d["native_report_version"] is None and not d["issues"]
    assert d["private"] and not d["shareable"] and d["approval_status"] == "NOT_APPROVED"
