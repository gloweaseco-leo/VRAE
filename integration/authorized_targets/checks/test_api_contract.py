"""Transport configuration and API docs; actual calls run in separate container."""

import pytest
from contracts.l2_launch.contract import Refused
from integration.authorized_targets.transport import endpoint, check_headers
from integration.authorized_targets.api_contract import openapi, error


def cfg():
    return {
        "bindings": [{"client_certificate_sha256": "1" * 64}],
        "transport": {
            "bind": "0.0.0.0",
            "port": 8769,
            "hosts": ["vrae-api:8769"],
            "origins": ["https://vrae-api:8769"],
            "mtls": True,
            "client_ca": "/operator/client-ca.pem",
        },
    }


def test_nonloopback_has_no_implicit_insecure_transport():
    d = cfg()
    assert endpoint(d)["mtls"] is True
    d["transport"]["mtls"] = False
    with pytest.raises(ValueError):
        endpoint(d)
    d = cfg()
    d["bindings"][0].pop("client_certificate_sha256")
    with pytest.raises(ValueError):
        endpoint(d)


def test_service_requests_do_not_require_browser_origin_but_keep_strict_host():
    class Handler:
        headers = {"Host": "vrae-api:8769"}

    assert check_headers(Handler(), cfg())["mtls"]
    Handler.headers = {"Host": "evil.example:8769"}
    with pytest.raises(Refused):
        check_headers(Handler(), cfg())
    Handler.headers = {"Host": "vrae-api:8769", "Origin": "https://evil.example"}
    with pytest.raises(Refused):
        check_headers(Handler(), cfg())


def test_error_contract_and_independent_resources():
    d = openapi()
    assert d["info"]["title"] == "VRAE Diagnosis API"
    assert "/health/live" in d["paths"] and "/health/ready" in d["paths"]
    assert "/v1/return-sessions" in d["paths"]
    assert error("UNAVAILABLE")["error"] == {
        "code": "UNAVAILABLE",
        "http_status": 503,
        "retryable": True,
    }
