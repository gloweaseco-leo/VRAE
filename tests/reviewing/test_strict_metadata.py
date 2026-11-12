"""Regression for independently reproduced initial-candidate type confusion."""

from dataclasses import replace
import json

from vrae.reviewing import build_target
from vrae.reviewing.canonical import SOURCE_LIMIT, canonical, parse, sha
from .synthetic import inputs
from .test_offline_contract import denial


def test_boolean_policy_version_is_not_integer_one():
    i = inputs()
    policy = parse(i.trust.policy)
    policy["scope"]["policy_version"] = True
    with denial("D_POLICY_UNTRUSTED"):
        build_target(i.document, i.html, i.source, trust=replace(i.trust, policy=canonical(policy)))


def test_boolean_expected_count_is_not_integer_one():
    i = inputs()
    held = parse(i.trust.held)
    held["expected_issue_count"] = True
    with denial("D_TRUST_INPUT_REQUIRED"):
        build_target(i.document, i.html, i.source, trust=replace(i.trust, held=canonical(held)))


def test_unknown_source_fields_rejected_even_after_outer_rehash():
    i = inputs()
    source = json.loads(i.source)
    source["trusted_human"] = "Owner"
    raw = canonical(source, limit=SOURCE_LIMIT)
    held = parse(i.trust.held)
    held["expected_source_sha256"] = sha(raw)
    with denial("D_SOURCE_SHAPE"):
        build_target(i.document, i.html, raw, trust=replace(i.trust, held=canonical(held)))


def test_safe_error_suppresses_underlying_context():
    i = inputs()
    with denial("D_ARTIFACT_TAMPER") as caught:
        build_target(i.document, i.html + b"secret-untrusted-text", i.source, trust=i.trust)
    assert "secret-untrusted-text" not in str(caught.value)
    assert caught.value.__suppress_context__ is True
