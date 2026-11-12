"""Actual native proposal validation, not human acceptance."""

from apps.operator_console.proposals import ProposalPreview
from apps.operator_console.fixtures import make_fixture
from apps.operator_console.contracts import ConsoleError
from apps.operator_console.interface import ConsoleInterface
from apps.operator_console.ports import Scope
from apps.operator_console.proposal_views import composer
from vrae.reviewing import ReviewCommandProposal, CoverageAcknowledgementProposal, ReviewError
from vrae.reviewing.canonical import canonical
from copy import deepcopy
from urllib.parse import urlencode
import pytest


@pytest.fixture(scope="module")
def sample():
    s, c = make_fixture()
    return s, c, ProposalPreview(s, c, test_only=True, synthetic_fixtures=True)


def form(sample, case="404"):
    s, c, _ = sample
    task = s.detail(c, "task-" + case)
    _, d = s.review(c, task["task_id"], 1, task["report_pins"]["expected_draft_ref"])
    v = d["review_target"]
    t = v["target"]
    f = {
        "version": "1",
        "draft": t["draft_ref"],
        "target": v["target_digest"],
        "action": "APPROVE_CANDIDATE" if case == "404" else "SIMULATED_INTERNAL_SCOPE_ACK",
        "reason": "",
    }
    for i, claim in enumerate(t["claims"]):
        f.update(
            {
                f"guard.{i}": claim["guard_ref"],
                f"binding.{i}": claim["binding_ref"],
                f"pointer.{i}": claim["pointer"],
                f"disposition.{i}": claim["allowed_acceptance"],
            }
        )
    f.update({"section." + section: v["target_digest"] for section in t["required_sections"]})
    return task, d, f


def call(sample, f, case="404", context=None):
    _, c, p = sample
    return p.validate(
        c if context is None else context,
        "task-" + case,
        urlencode(f).encode(),
        "application/x-www-form-urlencoded",
    )


def test_preview_requires_explicit_fixture_mode():
    s, c = make_fixture()
    with pytest.raises(ValueError):
        ProposalPreview(s, c, test_only=False, synthetic_fixtures=True)


@pytest.mark.parametrize(
    "case,kind", [("404", ReviewCommandProposal), ("200", CoverageAcknowledgementProposal)]
)
def test_actual_native_validator_and_replay(sample, case, kind, monkeypatch):
    import apps.operator_console.proposals as module
    import vrae.reviewing.target as native

    original = module.validate_proposal
    calls = []
    loads = []
    native._replay_bytes.cache_clear()
    load = native.ReportDraft.load

    def real_load(*a, **kw):
        loads.append(kw["expected_draft_ref"])
        return load(*a, **kw)

    def real_validate(proposal, target):
        calls.append((type(proposal), proposal.document, target.document))
        return original(proposal, target)

    monkeypatch.setattr(native.ReportDraft, "load", real_load)
    monkeypatch.setattr(module, "validate_proposal", real_validate)
    _, d, f = form(sample, case)
    task, d, command, outcome = call(sample, f, case)
    assert outcome == "CONTRACT_VALID_ONLY" and calls[-1][0] is kind and loads
    assert len(command["dispositions"]) == len(d["review_target"]["target"]["claims"])
    assert len(command["sections"]) == 4
    assert (d["review_target"]["native_h0"] is None) == (case == "200")
    for claim, ev in zip(d["review_target"]["target"]["claims"], d["evidence"]):
        assert ev["body"].encode()[claim["byte_start"] : claim["byte_end"]] == ev["quote"].encode()
    assert task["stage"] in ("REVIEW_REQUIRED", "COVERAGE_ONLY")
    assert "decision" not in command and "APPROVED" not in outcome


@pytest.mark.parametrize(
    "action,disposition", [("REQUEST_CHANGES", "CHANGE_REQUESTED"), ("REJECT", "REJECTED")]
)
def test_located_reason_and_no_native_decision(sample, action, disposition):
    _, _, f = form(sample)
    f.update(action=action, reason="第 2 项影响假设需补充采购商路径研究。")
    f["disposition.1"] = disposition
    result = call(sample, f)
    assert result[-1] == "CONTRACT_VALID_ONLY"
    assert result[2]["dispositions"][1]["disposition"] == disposition
    assert sample[0].detail(sample[1], "task-404")["stage"] == "REVIEW_REQUIRED"
    with pytest.raises(ConsoleError, match="NOT_IMPLEMENTED"):
        sample[0].mutate(sample[1], "approve", result[2])


@pytest.mark.parametrize(
    "change,code",
    [
        ("missing-section", "D_SECTION_INCOMPLETE"),
        ("section-pin", "D_SECTION_INCOMPLETE"),
        ("foreign-claim", "D_CLAIM_INCOMPLETE"),
        ("duplicate-claim", "D_CLAIM_INCOMPLETE"),
        ("escalate", "D_CLAIM_CEILING"),
        ("empty-disposition", "D_CLAIM_CEILING"),
        ("reject-without-location", "D_REASON_LOCATION"),
        ("changes-without-location", "D_REASON_LOCATION"),
        ("no-reason", "D_REASON_REQUIRED"),
        ("space-reason", "D_UNTRUSTED_TEXT"),
        ("long-reason", "D_UNTRUSTED_TEXT"),
        ("control", "D_UNTRUSTED_TEXT"),
        ("bidi", "D_UNTRUSTED_TEXT"),
        ("unknown-action", "D_ACTION"),
        ("approve-with-change", "D_CLAIM_CEILING"),
    ],
)
def test_native_refusals_on_bound_forms(sample, change, code, monkeypatch):
    import apps.operator_console.proposals as module

    original = module.validate_proposal
    calls = []

    def real(*a):
        calls.append(a)
        return original(*a)

    monkeypatch.setattr(module, "validate_proposal", real)
    _, _, f = form(sample)
    if change == "missing-section":
        del f["section.coverage.v1"]
    elif change == "section-pin":
        f["section.coverage.v1"] = "0" * 64
    elif change == "foreign-claim":
        f["binding.0"] = "cb-" + "0" * 64
    elif change == "duplicate-claim":
        for k in ("guard", "binding", "pointer"):
            f[k + ".1"] = f[k + ".0"]
    elif change == "escalate":
        f["disposition.1"] = "ACK_LITERAL_FACT"
    elif change == "empty-disposition":
        f["disposition.0"] = ""
    elif change == "unknown-action":
        f["action"] = "APPROVED"
    elif change == "approve-with-change":
        f["disposition.1"] = "CHANGE_REQUESTED"
    elif change in ("reject-without-location", "changes-without-location"):
        f.update(
            action="REJECT" if change.startswith("reject") else "REQUEST_CHANGES",
            reason="请补充研究",
        )
    else:
        f.update(action="REJECT")
        f["disposition.1"] = "REJECTED"
        f["reason"] = {
            "no-reason": "",
            "space-reason": "   ",
            "long-reason": "原" * 2001,
            "control": "原\x01因",
            "bidi": "原\u202e因",
        }[change]
    result = call(sample, f)
    assert result[-1] == code and len(calls) == 1


@pytest.mark.parametrize(
    "extra",
    [
        "verified",
        "trusted",
        "owner",
        "actor",
        "tenant_id",
        "expected_review_seq",
        "idempotency_key",
        "production_adapter",
        "url",
        "section.extra",
        "disposition.99",
    ],
)
def test_caller_cannot_supply_authority_or_extra_fields(sample, extra):
    _, _, f = form(sample)
    f[extra] = "https://evil.example/?secret=private"
    with pytest.raises(ConsoleError, match="INVALID_INPUT"):
        call(sample, f)


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "target",
        "draft",
        "switch",
        "missing-claim",
        "malformed",
        "duplicate",
        "body",
        "type",
    ],
)
def test_transport_and_pin_refusals(sample, change):
    _, c, p = sample
    _, _, f = form(sample)
    if change == "version":
        f["version"] = "2"
    elif change == "target":
        f["target"] = "0" * 64
    elif change == "draft":
        f["draft"] = "draft-fake"
    elif change == "switch":
        f["target"] = form(sample, "200")[2]["target"]
    elif change == "missing-claim":
        del f["binding.0"]
    raw = urlencode(f).encode()
    if change == "malformed":
        raw += b"&bad=%ZZ"
    if change == "duplicate":
        raw += b"&action=APPROVED"
    if change == "body":
        raw = b"a" * 24577
    with pytest.raises(ConsoleError):
        p.validate(
            c,
            "task-404",
            raw,
            "application/json" if change == "type" else "application/x-www-form-urlencoded",
        )


@pytest.mark.parametrize("actor", [None, {}, {"role": "OWNER", "verified": True}, object()])
def test_untrusted_context_cannot_read_source(sample, actor, monkeypatch):
    s, _, p = sample
    monkeypatch.setattr(
        s.repository, "report_source", lambda _: pytest.fail("Must deny before source read")
    )
    with pytest.raises(ConsoleError, match="UNAUTHORIZED"):
        p.validate(actor, "task-404", b"", "application/x-www-form-urlencoded")


@pytest.mark.parametrize(
    "scope",
    [
        Scope("tenant-other", "ops-synthetic", frozenset({"task-404"}), "SYNTHETIC_TEST_ONLY"),
        Scope("tenant-test", "forged-owner", frozenset({"task-404"}), "SYNTHETIC_TEST_ONLY"),
        Scope("tenant-test", "ops-synthetic", frozenset(), "SYNTHETIC_TEST_ONLY"),
        Scope("tenant-test", "ops-synthetic", frozenset({"task-404"}), "PRODUCTION"),
    ],
)
def test_scoped_fixture_not_human_authority(scope, monkeypatch):
    s, c = make_fixture()
    foreign = s.authority.issue(scope)
    if scope.source_kind == "PRODUCTION":
        with pytest.raises(ConsoleError):
            ProposalPreview(s, foreign, test_only=True, synthetic_fixtures=True)
        return
    p = ProposalPreview(s, foreign, test_only=True, synthetic_fixtures=True)
    monkeypatch.setattr(
        s.repository, "report_source", lambda _: pytest.fail("No existence/source disclosure")
    )
    with pytest.raises(ConsoleError, match="UNAUTHORIZED"):
        p.validate(foreign, "task-404", b"", "application/x-www-form-urlencoded")


@pytest.mark.parametrize("case", ["403", "robots", "unknown", "invalid", "running"])
def test_neutral_not_submittable(sample, case):
    _, c, p = sample
    with pytest.raises(ConsoleError):
        p.read(c, "task-" + case, 1, "fake", "0" * 64)


def test_200_cannot_request_approval_or_changes(sample):
    _, _, f = form(sample, "200")
    f["action"] = "APPROVE_CANDIDATE"
    with pytest.raises(ConsoleError):
        call(sample, f, "200")
    f["action"] = "SIMULATED_INTERNAL_SCOPE_ACK"
    f["disposition.0"] = "CHANGE_REQUESTED"
    assert call(sample, f, "200")[-1] == "D_CLAIM_CEILING"


@pytest.mark.parametrize(
    "tamper", ["source", "quote", "byte", "guard", "policy", "dto-case", "version"]
)
def test_changed_target_while_form_open_fails_closed(sample, tamper):
    _, _, f = form(sample)
    s, c = make_fixture()
    p = ProposalPreview(s, c, test_only=True, synthetic_fixtures=True)
    if tamper == "version":
        s.repository.tasks["task-404"]["report_version"] = 2
    elif tamper == "dto-case":
        replacement = deepcopy(s.repository.tasks["task-200"])
        replacement["task_id"] = "task-404"
        s.repository.tasks["task-404"] = replacement
    else:
        src = s.repository.sources["404"]
        if tamper == "policy":
            src["pack"]["policy_version"] = 2
        elif tamper == "guard":
            src["guard_inputs"][0]["guard"]["guard_ref"] = "cg-" + "0" * 64
        else:
            source = src["guard_inputs"][0]["bindings"][0]["fact"]["source"]
            if tamper == "byte":
                source["byte_end"] += 1
            else:
                source["quote"] = "伪造原始证据"
    with pytest.raises(ConsoleError):
        call((s, c, p), f)


def test_ui_escaping_no_saved_state_and_no_network(sample, monkeypatch):
    import socket
    import urllib.request

    def deny(*a, **kw):
        pytest.fail("Outbound network prohibited")

    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    monkeypatch.setattr(urllib.request, "urlopen", deny)
    _, _, f = form(sample)
    f.update(action="REJECT", reason='<script>fetch("https://evil.example")</script>')
    f["disposition.1"] = "REJECTED"
    t, d, cmd, outcome = call(sample, f)
    body = composer("/", t, d, cmd, outcome)
    assert "<script>" not in body and "&lt;script&gt;" in body
    assert "CONTRACT_VALID_ONLY" in body and "PRIVATE_NOT_APPROVED" in body
    fresh = composer("/", t, d)
    assert "data-outcome=" not in fresh and " checked" not in fresh and " selected" not in fresh
    assert "localStorage" not in fresh and "sessionStorage" not in fresh
    assert len(cmd["dispositions"]) == 6


def test_route_segregation_and_original_production_deny(sample):
    s, c, p = sample
    t, d, f = form(sample)
    route = "/tasks/task-404/proposal?" + urlencode(
        {k: f[k] for k in ("version", "draft", "target")}
    )
    assert ConsoleInterface(s).dispatch(c, "GET", route).status != 200
    ui = ConsoleInterface(s, proposal_preview=p)
    assert ui.dispatch(c, "GET", route).status == 200
    for path in (
        route,
        "/tasks/task-404/proposal-preview",
        "/approve",
        "/reject",
        "/share",
        "/export",
        "/download",
    ):
        assert ui.dispatch(c, "POST", path).status == 501
    from apps.operator_console.targets import FutureRealReviewAdapter

    with pytest.raises(ReviewError):
        FutureRealReviewAdapter().prepare({"role": "OWNER", "verified": True})
    assert canonical(d["review_target"]["target"])
