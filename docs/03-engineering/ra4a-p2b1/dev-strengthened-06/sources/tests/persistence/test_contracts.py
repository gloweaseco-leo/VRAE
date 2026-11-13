"""Default-root tests are pure; real DB cases live in integration/ra4a."""

import hashlib

import pytest

from vrae.persistence import PersistenceError, admission_payload, production_port


@pytest.mark.parametrize("context", [None, {}, {"role": "OWNER", "verified": True}, "human"])
def test_production_ports_always_deny(context):
    with pytest.raises(
        PersistenceError, match="^RA4A_PRODUCTION_AUTH_OBJECT_REVIEW_NOT_IMPLEMENTED$"
    ):
        production_port(context)


@pytest.mark.parametrize(
    "ref,digest",
    [
        (True, "a" * 64),
        ("bad/url", "a" * 64),
        ("accepted-404", None),
        (None, "a" * 64),
        ("accepted-404", "x" * 64),
        ("accepted-404", True),
    ],
)
def test_reference_metadata_cannot_be_guessed_or_partially_bound(ref, digest):
    with pytest.raises(PersistenceError, match="RA4A_REFERENCE_INVALID"):
        admission_payload(ref, digest)


def test_payload_binds_exact_private_reference_without_actor_authority():
    raw, digest = admission_payload("accepted-404", "a" * 64)
    assert digest == hashlib.sha256(raw.encode()).hexdigest()
    assert "actor" not in raw and "tenant" not in raw and "APPROVE" not in raw
    assert admission_payload("accepted-200", "a" * 64)[1] != digest
