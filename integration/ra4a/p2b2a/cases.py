"""Real local PG16 association and least-privilege denial evidence."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from integration.ra4a.p2b1_support import (
    connect, counts, fingerprint, graph, verify_migrations,
)
from tests.identity.issuer import AUDIENCE, ISSUER, NONCE, NOW, Issuer
from vrae.identity import Assignment, IdentityBoundary, IdentityDenied, TrustAnchor
from vrae.identity.boundary import production_port
from vrae.persistence.contracts import PersistenceError
from vrae.persistence.private_bytes import locator
from vrae.persistence.review_cas import production_review_port


def make(name, *, role="p2b1_test_a_reviewer", assignment=None, clock=None, **kwargs):
    issuer = Issuer()
    loc = locator(graph())
    policy = Assignment(ISSUER, "synthetic-reviewer-1", role, loc, NOW + 600)
    api = IdentityBoundary(
        anchor=TrustAnchor(ISSUER, AUDIENCE, issuer.jwks(), NOW + 600),
        assignments=(assignment or policy,), connect=lambda r: connect(r, dbname=name),
        clock=clock or (lambda: NOW), **kwargs,
    )
    return issuer, api, loc, policy


def test_valid_rotation_and_no_writes(isolated):
    name, admin = isolated
    before = fingerprint(admin)
    issuer, api, loc, _ = make(name)
    for kid in ("old", "new"):
        result = api.check(issuer.token(kid=kid), loc, nonce=NONCE)
        assert result.tenant == loc.tenant and result.report == loc.report
        assert result.version == loc.version
        assert result.authority == "TEST_ONLY_IDENTITY_OBSERVATION"
        assert result.native_decision is result.native_approval is result.share_grant is None
        assert result.external_visibility is False
        with pytest.raises(IdentityDenied):
            production_port(result)
        with pytest.raises(PersistenceError):
            production_review_port(result)
    assert fingerprint(admin) == before
    assert all(n == 0 for n in counts(admin).values())


@pytest.mark.parametrize("mutation", ["principal", "tenant-assignment", "report-assignment",
                                     "policy-revoked", "policy-expired"])
def test_current_db_authority(isolated, mutation):
    name, admin = isolated
    issuer, api, loc, _ = make(name)
    queries = {
        "principal": "UPDATE ra4a_private.principals SET enabled=false WHERE db_role='p2b1_test_a_reviewer'",
        "tenant-assignment": "UPDATE ra4a_private.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'",
        "report-assignment": "UPDATE ra4a_review_test.assignments SET active=false WHERE db_role='p2b1_test_a_reviewer'",
        "policy-revoked": "UPDATE ra4a.policies SET status='REVOKED'",
        "policy-expired": "UPDATE ra4a.policies SET expires_at=clock_timestamp()-interval '1 second'",
    }
    admin.execute(queries[mutation])
    before = fingerprint(admin)
    with pytest.raises(IdentityDenied):
        api.check(issuer.token(), loc, nonce=NONCE)
    assert fingerprint(admin) == before


@pytest.mark.parametrize("mutation", ["disabled", "expired", "revoked-subject", "tenant", "report",
                                     "version", "digest", "cross-db-role", "admin-db-role"])
def test_separately_held_policy(isolated, mutation):
    name, admin = isolated
    issuer, api, loc, policy = make(name)
    if mutation == "disabled":
        policy = replace(policy, active=False)
    elif mutation == "expired":
        policy = replace(policy, expires=NOW)
    elif mutation == "revoked-subject":
        api.assignments = ()
    elif mutation in ("tenant", "report", "version", "digest"):
        field = "target_digest" if mutation == "digest" else mutation
        loc = replace(loc, **{field: 2 if mutation == "version" else "other"})
    elif mutation == "cross-db-role":
        policy = replace(policy, db_role="p2b1_test_b_reviewer")
    else:
        policy = replace(policy, db_role="postgres")
    if mutation != "revoked-subject":
        api.assignments = (policy,)
    before = fingerprint(admin)
    with pytest.raises(IdentityDenied):
        api.check(issuer.token(), loc, nonce=NONCE)
    assert fingerprint(admin) == before


@pytest.mark.parametrize("sub", ["unassigned", "synthetic-reviewer-1"])
def test_client_authority_claims_have_no_power(isolated, sub):
    name, admin = isolated
    issuer, api, loc, _ = make(name)
    token = issuer.token({"sub": sub, "role": "postgres", "actor": "owner", "user": "admin",
                          "tenant": "tenant-beta", "tenant_id": "tenant-beta"})
    if sub == "unassigned":
        with pytest.raises(IdentityDenied):
            api.check(token, loc, nonce=NONCE)
    else:
        result = api.check(token, loc, nonce=NONCE)
        assert result.tenant == "tenant-test"
    assert all(n == 0 for n in counts(admin).values())


def test_guc_and_role_cannot_override_session(isolated):
    name, admin = isolated
    issuer, api, loc, _ = make(name, role="p2b1_test_b_reviewer")

    def spoof(role):
        c = connect(role, dbname=name)
        c.execute("SET vrae.tenant_id='tenant-test'")
        c.execute("SET vrae.actor='p2b1_test_a_reviewer'")
        return c

    api.connect = spoof
    with pytest.raises(IdentityDenied):
        api.check(issuer.token(), loc, nonce=NONCE)
    assert all(n == 0 for n in counts(admin).values())


def test_replay_concurrent_and_after_revocation(isolated):
    name, admin = isolated
    issuer, api, loc, _ = make(name)
    token = issuer.token()

    def attempt(_):
        try:
            api.check(token, loc, nonce=NONCE)
            return True
        except IdentityDenied:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(attempt, range(8))) == 1
    api.anchor = replace(api.anchor, revoked=frozenset({"old"}))
    with pytest.raises(IdentityDenied):
        api.check(issuer.token(), loc, nonce=NONCE)
    assert all(n == 0 for n in counts(admin).values())


@pytest.mark.parametrize("claim,offset,allowed", [
    ("nbf", 6, False), ("nbf", 5, True), ("iat", 6, False), ("iat", 5, True),
    ("exp", -4, True), ("exp", -5, False),
])
def test_bounded_clock_skew_with_pg(isolated, claim, offset, allowed):
    name, _ = isolated
    issuer, api, loc, _ = make(name)
    claims = {"iat": NOW - 100, "nbf": NOW - 100, "exp": NOW + 120}
    claims[claim] = NOW + offset
    if claim == "iat":
        claims["nbf"] = NOW + offset
    token = issuer.token(claims)
    if allowed:
        api.check(token, loc, nonce=NONCE)
    else:
        with pytest.raises(IdentityDenied):
            api.check(token, loc, nonce=NONCE)


def test_clock_rollback_capacity_and_duplicate_policy(isolated):
    name, _ = isolated
    clock = [NOW]
    issuer, api, loc, policy = make(name, clock=lambda: clock[0], replay_capacity=1)
    api.check(issuer.token(), loc, nonce=NONCE)
    with pytest.raises(IdentityDenied):
        api.check(issuer.token(), loc, nonce=NONCE)
    clock[0] -= 1
    with pytest.raises(IdentityDenied):
        api.check(issuer.token(), loc, nonce=NONCE)
    clock[0] = NOW
    issuer, api, loc, policy = make(name)
    api.assignments = (policy, policy)
    with pytest.raises(IdentityDenied):
        api.check(issuer.token(), loc, nonce=NONCE)


def test_db_unavailable_consumes_token_and_schema_unchanged(isolated):
    name, admin = isolated
    issuer, api, loc, _ = make(name)
    token = issuer.token()
    factory = api.connect

    def unavailable(role):
        raise ConnectionError("simulated unavailable factory; real PG tested separately")

    api.connect = unavailable
    with pytest.raises(IdentityDenied):
        api.check(token, loc, nonce=NONCE)
    api.connect = factory
    with pytest.raises(IdentityDenied):
        api.check(token, loc, nonce=NONCE)
    # Verify accepted source/catalog pins on the unmodified template.
    with connect() as template:
        verify_migrations(template)
    assert all(n == 0 for n in counts(admin).values())


def test_real_pg_evidence(isolated):
    name, admin = isolated
    issuer, api, loc, _ = make(name)
    api.check(issuer.token(), loc, nonce=NONCE)
    print(json.dumps({"server": admin.execute("SELECT version()").fetchone()[0],
                      "authority": "TEST_ONLY_IDENTITY_OBSERVATION", "writes": counts(admin)}))


def test_real_connection_refusal_and_replay(isolated):
    name, admin = isolated
    issuer, api, loc, _ = make(name)
    token = issuer.token()
    admin.execute("ALTER ROLE p2b1_test_a_reviewer NOLOGIN")
    try:
        with pytest.raises(IdentityDenied):
            api.check(token, loc, nonce=NONCE)
    finally:
        admin.execute("ALTER ROLE p2b1_test_a_reviewer LOGIN")
    with pytest.raises(IdentityDenied):
        api.check(token, loc, nonce=NONCE)


def test_stale_db_reference_after_new_version(isolated):
    from integration.ra4a.p2a_support import add_reference

    name, admin = isolated
    issuer, api, loc, _ = make(name)
    add_reference(admin, "404", 2)
    with pytest.raises(IdentityDenied):
        api.check(issuer.token(), loc, nonce=NONCE)
