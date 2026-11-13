"""Pure native boundary negatives, separately counted from live SQL cases."""
import pytest

from tests.reviewing.synthetic import command, inputs
from vrae.persistence.contracts import PersistenceError
from vrae.persistence.review_cas import AUTHORITY, STATUSES, production_review_port
from vrae.reviewing import ReviewError, validate_proposal
from vrae.reviewing.canonical import canonical


@pytest.mark.parametrize("fake", ({"actor":{"verified":True}}, {"role":"REVIEWER"}, {"cookie":"approved"}, {"oidc":"unsigned"}))
def test_p2b1_production_never_accepts_untrusted_authority(fake):
    with pytest.raises(PersistenceError, match="P2B1_REAL_IDENTITY_NATIVE_REVIEW_SHARE_DENIED"):
        production_review_port(**fake)


@pytest.mark.parametrize("case", ("404", "200"))
def test_p2b1_native_target_does_not_become_native_approval(case):
    i=inputs(case)
    proposal=command(i.target)
    digest=validate_proposal(proposal,i.target)
    assert len(digest)==64
    assert "native_approval" not in proposal.document
    assert i.target.document["kind"] == ("L1_NATIVE" if case=="404" else "COVERAGE_ONLY")
    assert AUTHORITY=="TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL"
    assert all(s.startswith("SIMULATED_") for s in STATUSES)


@pytest.mark.parametrize("attack", ("approved", "actor", "hypothesis", "zero-review"))
def test_p2b1_native_contract_refuses_elevation(attack):
    target=inputs("200" if attack=="zero-review" else "404").target
    p=command(target)
    d=p.document
    if attack=="approved": d["native_approval"]="APPROVED"
    if attack=="actor": d["actor"]={"verified":True}
    if attack=="hypothesis":
        next(x for x in d["dispositions"] if x["disposition"]=="ACCEPT_AS_HYPOTHESIS")["disposition"]="ACCEPT_AS_FACT"
    if attack=="zero-review": d["kind"]="REVIEW_COMMAND_PROPOSAL"
    with pytest.raises(ReviewError): validate_proposal(type(p)(canonical(d,limit=131072)),target)
