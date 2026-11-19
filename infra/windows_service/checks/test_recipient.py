"""Reader bridge cannot grant identity roles or accept an unbound grant."""
import hashlib
from types import SimpleNamespace
import pytest
from contracts.l2_launch.contract import Refused
from infra.windows_service import recipient


def test_bridge_requires_explicit_signed_delegation_and_verified_profile():
    for verified,document in ((False,{"recipient_authority":recipient.ASSURANCE}),(True,{})):
        app=SimpleNamespace(verified=verified,authority=SimpleNamespace(document=document))
        with pytest.raises(Refused):
            recipient.authorized(app)


def test_current_recipient_scope_change_is_denied():
    class Connection:
        def execute(self,*args):
            return self
        def fetchone(self):
            return ({"subject_ref":"subject-b"},)
    with pytest.raises(Refused):
        recipient.current(Connection(),{"tenant_id":"tenant-live"},{"audit_ref":"aref-test",
            "cookie_sha256":"cookie","csrf_sha256":"csrf","scope":{"subject_ref":"subject-a"}})


def test_recipient_session_is_bound_to_exact_grant_and_token():
    sid="opaque-session";token="secret-directed-token"
    held=SimpleNamespace(grant_claims={"recipient_bridge":True,"grant_id":"grant-a",
        "grant_token_sha256":hashlib.sha256(token.encode()).hexdigest()})
    app=SimpleNamespace(directory=SimpleNamespace(sessions={hashlib.sha256(sid.encode()).digest():held}))
    recipient.check_grant(app,sid,{"X-Report-Grant":"grant-a","X-Report-Token":token})
    for headers in ({},{"X-Report-Grant":"grant-b","X-Report-Token":token},
                    {"X-Report-Grant":"grant-a","X-Report-Token":"other"}):
        with pytest.raises(Refused):
            recipient.check_grant(app,sid,headers)
