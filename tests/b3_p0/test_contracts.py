import pytest

from vrae.b3_p0.contracts import Command, Denied, production_review_port, production_share_port
from tests.reviewing.synthetic import command, inputs
from vrae.reviewing.canonical import canonical


@pytest.mark.parametrize("port", [production_review_port, production_share_port])
def test_production_ports_are_unconditional_deny(port):
    with pytest.raises(Denied):
        port(verified=True, authority="APPROVED")


@pytest.mark.parametrize("kind", ["404", "200"])
def test_canonical_accepted_proposal(kind):
    cmd = command(inputs(kind).target)
    assert Command(cmd.payload).proposal().document == cmd.document


def test_noncanonical_and_forged_authority_denied():
    cmd = command(inputs().target).document
    with pytest.raises(Denied):
        Command(canonical(cmd) + b" ").proposal()
    with pytest.raises(Denied):
        Command(b'{"kind":"ReviewDecision","authority":"APPROVED"}').proposal()
