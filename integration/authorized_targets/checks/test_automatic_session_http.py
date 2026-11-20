"""HTTP contract boundary only; live PG isolation is in test_automatic_pg."""
from datetime import datetime, UTC, timedelta
from http.client import HTTPMessage
from types import SimpleNamespace

import pytest

from contracts.l2_launch.contract import Refused
from integration.authorized_targets import http, transport
from integration.l2_launch.g1.http_server import MEDIA

EMPTY = object()


def handler(monkeypatch, body=EMPTY, *, change_binding=None, enabled=True, mtls=True, path='/v1/diagnosis-sessions'):
    binding = {'kind': 'APP', 'role': 'session-test-app', 'tenant_id': 'session-test-tenant', **(change_binding or {})}
    cfg = {'bindings': [binding], 'target_intake_enabled': enabled}
    monkeypatch.setattr(http, 'service_binding', lambda *a: binding)
    monkeypatch.setattr(transport, 'check_headers', lambda *a: {'mtls': mtls})
    monkeypatch.setattr(transport, 'bind_peer', lambda *a: None)
    calls = []
    def invoke(*args):
        calls.append(args)
        return {'expires_at': (datetime.now(UTC) + timedelta(minutes=30)).isoformat()}
    monkeypatch.setattr(http.store, 'invoke', invoke)
    h = object.__new__(http.Handler)
    h.server = SimpleNamespace(cfg=cfg)
    h.command, h.path = 'POST', path
    h.headers = HTTPMessage()
    h.headers['Accept'] = h.headers['Content-Type'] = MEDIA
    h.body = lambda: {} if body is EMPTY else body
    h.send = lambda status, result, headers: (status, result, dict(headers))
    return h, calls


def test_no_invitation_produces_private_cookie_and_csrf_for_the_original_ports(monkeypatch):
    h, calls = handler(monkeypatch)
    status, result, headers = h.route_target('POST')
    assert status == 200 and result == {'created': True}
    assert len(calls) == 1 and calls[0][1:3] == ('automatic_session', 'session-test-tenant')
    assert all(len(pin) == 64 for pin in calls[0][3:])
    cookie = headers['Set-Cookie']
    assert cookie.startswith('__Host-vrae-targets=')
    assert all(flag in cookie for flag in ('HttpOnly', 'Secure', 'SameSite=Strict', 'Path=/'))
    assert len(headers['X-CSRF-Token']) >= 40
    assert headers['X-CSRF-Token'] not in calls[0]


@pytest.mark.parametrize('kwargs', [
    {'body': {'subject_ref': 'forged'}}, {'body': {'tenant_id': 'forged'}},
    {'body': {'invitation_token': 'shared-preview-token'}}, {'body': {'authorized': True}},
    {'body': None}, {'body': []}, {'body': False},
    {'enabled': False}, {'mtls': False}, {'change_binding': {'port': 'AI'}},
    {'change_binding': {'port': 'REVIEW'}}, {'change_binding': {'kind': 'WORKER'}},
    {'change_binding': {'health_probe': {}}},
])
def test_cannot_select_subject_or_tenant_or_use_wrong_service_channel(monkeypatch, kwargs):
    h, calls = handler(monkeypatch, **kwargs)
    with pytest.raises(Refused):
        h.route_target('POST')
    assert calls == []


def test_legacy_invitation_path_remains_a_separate_one_use_exchange(monkeypatch):
    h, calls = handler(monkeypatch, {'invitation_token': 'legacy-one-use'}, path='/v1/invitation-session')
    status, result, _ = h.route_target('POST')
    assert status == 200 and result == {'restored': True}
    assert calls[0][1] == 'exchange'
