"""Fresh per-job raw captures, accepted six rules, DISC Guard and private draft."""

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import fixture
from vrae.application.ra4b_p2.producer import (
    AUTHORITY,
    CandidateDenied,
    GeneratedCandidate,
    LeaseContext,
    capture_digest,
    encode,
    generate,
)
from vrae.collection.collector import Collector
from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.manifest import document_hash
from vrae.collection.policy import SourceAccess

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


def fresh(status):
    audit, policy = fixture("AuditRequest"), fixture("SourcePolicy")
    audit["tenant_id"] = policy["tenant_id"] = "tenant-test"
    policy["expires_at"] = (NOW + timedelta(days=1)).isoformat()
    policy["revoked_at"] = None
    access = SourceAccess(
        audit, lambda: policy, terms_reference="s2-offline-synthetic", now=lambda: NOW
    )
    ids = [str(uuid4()) for _ in range(4)]
    home = b'<html><body><nav><a href="/category/s2-parts">Synthetic S2 category</a></nav></body></html>'
    transport = SyntheticTransport(
        {
            "https://example.org/robots.txt": (
                200,
                {"content-type": "text/plain"},
                b"User-agent: *\nDisallow:\n",
            ),
            "https://example.org/": (200, {"content-type": "text/html"}, home),
            "https://example.org/category/s2-parts": (
                status,
                {"content-type": "text/html"},
                b"<html>S2 parts</html>",
            ),
        }
    )
    capture = asyncio.run(
        Collector(SafeFetcher(FixedDNS(), transport)).capture(
            ids[1], access, limits=Limits(max_pages=5, interval_seconds=0.01), retain_raw_html=True
        )
    )
    context = LeaseContext(
        audit["tenant_id"],
        ids[0],
        ids[1],
        ids[2],
        "ra4b_test_a_worker",
        ids[3],
        1,
        (NOW + timedelta(seconds=30)).isoformat(),
        1,
        "raw-s2-offline-input",
        "1" * 64,
        capture_digest(capture),
        policy["policy_id"],
        policy["policy_version"],
        document_hash(policy),
        NOW.isoformat(),
    )
    return capture, access, context, policy


@pytest.fixture(scope="module")
def candidate():
    capture, access, context, policy = fresh(404)
    return capture, access, context, policy, generate(capture, access, context, now=NOW)


def test_new_raw_capture_generates_same_job_six_rule_disc_candidate(candidate):
    capture, access, context, _, result = candidate
    doc = result.private_document
    assert doc["authority"] == AUTHORITY and doc["committed"] is False
    assert doc["scope"]["run_id"] == context.run_id
    assert doc["binding"]["job_id"] == context.job_id
    assert doc["report"]["metadata"]["report_id"] == "job-" + context.job_id
    assert len(doc["report"]["issues"]) == 1
    assert doc["report"]["issues"][0]["fact_claim"]["fact"]["rule_id"] == "DISC-01"
    assert doc["versions"]["guard"] == "ra3b-disc-1.0.0"
    assert doc["versions"]["evaluator"] == "ra2b6-1.0.0"
    assert (
        doc["commit_receipt"]
        is doc["reviewer_assignment"]
        is doc["native_approval"]
        is doc["share_grant"]
        is None
    )
    assert context.lease_token not in result._payload.decode() and context.lease_token not in repr(
        context
    )
    assert result.verify(capture, access, context, now=NOW).ref == result.ref


def test_fresh_success_capture_never_copies_old_404_result():
    capture, access, context, _ = fresh(200)
    doc = generate(capture, access, context, now=NOW).private_document
    assert doc["report"]["issues"] == []
    assert doc["scope"]["run_id"] == capture.manifest["run_id"] == context.run_id


@pytest.mark.parametrize(
    "field,value",
    [
        ("worker", "ra4b_test_b_worker"),
        ("tenant_id", "tenant-beta"),
        ("lease_seq", 0),
        ("lease_seq", True),
        ("origin_epoch", 0),
        ("lease_until", NOW.isoformat()),
        ("lease_until", (NOW + timedelta(seconds=31)).isoformat()),
        ("job_id", "not-a-job"),
    ],
)
def test_invalid_lease_context_denies_before_generation(candidate, field, value):
    capture, access, context, _, _ = candidate
    with pytest.raises(CandidateDenied, match="S2_LEASE_CONTEXT_DENIED"):
        generate(capture, access, replace(context, **{field: value}), now=NOW)


@pytest.mark.parametrize(
    "mutation", ["job_id", "origin_epoch", "source_ref", "guard_version", "committed", "html"]
)
def test_candidate_replay_denies_forged_result_or_other_job(candidate, mutation):
    capture, access, context, _, result = candidate
    doc = result.private_document
    html = result._html
    if mutation in ("job_id", "origin_epoch", "source_ref"):
        doc["binding"][mutation] = "foreign" if mutation != "origin_epoch" else 2
    elif mutation == "guard_version":
        doc["versions"]["guard"] = "ra3b-1.0.0"
    elif mutation == "committed":
        doc["committed"] = True
    else:
        html += b"forged"
    with pytest.raises(CandidateDenied, match="S2_CANDIDATE_REPLAY_MISMATCH"):
        GeneratedCandidate(encode(doc), html).verify(capture, access, context, now=NOW)


def test_source_policy_scope_and_raw_digest_mutation_deny(candidate):
    capture, access, context, _, _ = candidate
    with pytest.raises(CandidateDenied, match="S2_AUTHORIZED_INPUT_MISMATCH"):
        generate(capture, access, replace(context, input_sha256="0" * 64), now=NOW)
    with pytest.raises(CandidateDenied, match="S2_AUTHORIZED_INPUT_MISMATCH"):
        generate(capture, access, replace(context, run_id=str(uuid4())), now=NOW)


def test_live_policy_revocation_denies_fresh_generation():
    capture, access, context, policy = fresh(404)
    policy["revoked_at"] = NOW.isoformat()
    with pytest.raises(CollectionError):
        generate(capture, access, context, now=NOW)


def test_no_public_persistence_or_reviewer_api_in_candidate(candidate):
    *_, result = candidate
    assert not any(
        hasattr(result, k) for k in ("commit", "approve", "share", "reviewer_view", "persist")
    )
    detached = result.private_document
    detached["committed"] = True
    assert result.private_document["committed"] is False
    assert json.loads(result._payload)["authority"] == AUTHORITY


def test_closed_candidate_contract_never_accepts_commit_claim_or_token(candidate):
    *_, result = candidate
    schema = json.loads(
        (
            Path(__file__).resolve().parents[2] / "contracts/ra4b_p2/GeneratedCandidate.schema.json"
        ).read_bytes()
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    validator.validate(result.private_document)
    for field, value in [("committed", True), ("share_grant", {}), ("lease_token", "untrusted")]:
        document = result.private_document
        document[field] = value
        with pytest.raises(ValidationError):
            validator.validate(document)
