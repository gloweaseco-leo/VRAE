"""Temporary external health credentials cannot reach business/report routes."""
from datetime import datetime, UTC, timedelta
from types import SimpleNamespace
import pytest
from contracts.l2_launch.contract import Refused
from integration.authorized_targets.transport import bind_peer


def binding(port=None, delta=600):
    return {"port":port,"health_probe":{"expires_at":
        (datetime.now(UTC)+timedelta(seconds=delta)).isoformat()}}


@pytest.mark.parametrize("port,path",[(None,"/health/ready"),("REVIEW","/v1/report-authority/health")])
def test_probe_has_only_exact_current_health_route(port,path):
    bind_peer(SimpleNamespace(command="GET",path=path),binding(port),{"mtls":False})


@pytest.mark.parametrize("method,path",[("POST","/v1/invitation-session"),
    ("POST","/v1/target-applications"),("GET","/v1/openapi.json"),
    ("POST","/v1/report-authority/challenge"),("GET","/health/ready?scope=all")])
def test_probe_cannot_access_other_routes(method,path):
    with pytest.raises(Refused):
        bind_peer(SimpleNamespace(command=method,path=path),binding(),{"mtls":False})


@pytest.mark.parametrize("probe",[{"expires_at":"2020-01-01T00:00:00+00:00"},
    {"expires_at":"2099-01-01T00:00:00"},{"expires_at":"invalid"},{},False])
def test_probe_expiry_is_fail_closed(probe):
    with pytest.raises(Refused):
        bind_peer(SimpleNamespace(command="GET",path="/health/ready"),
                  {"health_probe":probe},{"mtls":False})


def test_health_scope_does_not_bypass_certificate_binding():
    h=SimpleNamespace(command="GET",path="/health/ready",connection=
        SimpleNamespace(getpeercert=lambda **kw:b"wrong-certificate"))
    with pytest.raises(Refused):
        bind_peer(h,{**binding(),"client_certificate_sha256":"0"*64},{"mtls":True})
