"""Explicit offline threat cases; no test in this file may create a socket."""
import asyncio
import socket
from dataclasses import replace
from datetime import timedelta

import pytest

from tests.collection.test_security import NOW, access, fixture
from vrae.collection.errors import CollectionError
from vrae.collection.http_transport import PinnedTransport
from vrae.collection.limits import Budget, Limits
from vrae.collection.policy import SourceAccess

from .adapter import (
    ConnectionFence,
    FencedAccess,
    RecordedResolver,
    RecordedTransport,
    capture_live,
)
from .fixtures import permit, pins, routes, worker


@pytest.fixture(autouse=True)
def no_sockets(monkeypatch):
    # Leave asyncio's own local socketpair plumbing intact on Windows.
    def refused(*args, **kwargs):
        raise AssertionError('OFFLINE_TEST_ATTEMPTED_NETWORK')
    monkeypatch.setattr(asyncio.BaseEventLoop, 'sock_connect', refused)
    monkeypatch.setattr(socket, 'create_connection', refused)
    monkeypatch.setattr(socket, 'getaddrinfo', refused)


def capture(w):
    return asyncio.run(w.capture(w.access.held.run_id))


@pytest.mark.parametrize('scenario', ['static', 'cms', 'spa', 'multi-sku', 'multilingual', 'query-percent', 'dynamic-assets', 'redirect'])
def test_original_collector_saved_bytes_and_no_asset_or_js_expansion(scenario):
    w = worker(scenario)
    bundle = capture(w)
    bundle.verify()
    assert all(p['snapshot']['status'] == 'FETCHED' for p in bundle.manifest['pages'])
    assert len(bundle.manifest['pages']) <= 8
    assert all('?' not in c[0] and '%' not in c[0] and c[1] == 'GET' for c in w.fetcher.transport.transport.calls)
    assert not any(c[0].endswith(('.js', '.png', '/submit')) for c in w.fetcher.transport.transport.calls)
    assert {r['stage'] for r in w.resolver.checks} == {'HOP_DNS', 'PRECONNECT_DNS'}


@pytest.mark.parametrize('scenario', ['403', '429', 'waf', 'robots'])
def test_restrictions_have_no_retained_page_bytes_or_guilty_finding(scenario):
    bundle = capture(worker(scenario))
    assert bundle.manifest['pages'][0]['snapshot']['status'] == 'ACCESS_BLOCKED'
    assert not bundle.objects and 'findings' not in bundle.manifest


@pytest.mark.parametrize('addresses', [(), ('127.0.0.1',), ('169.254.169.254',), ('::1',),
    ('93.184.216.20', '10.0.0.1'), ('93.184.216.20', '::ffff:93.184.216.20'), ('64:ff9b::808:808',)])
def test_all_a_and_aaaa_answers_must_be_safe_before_transport(addresses):
    transport = RecordedTransport(routes())
    w = worker(resolver=RecordedResolver((addresses,)), transport=transport)
    capture(w)
    assert not transport.calls


@pytest.mark.parametrize('second', [('127.0.0.1',), ('169.254.169.254',), ('93.184.216.21',),
    ('93.184.216.20', 'fc00::1')])
def test_rebinding_between_hop_dns_and_connect_has_zero_exchange(second):
    transport = RecordedTransport(routes())
    w = worker(resolver=RecordedResolver((('93.184.216.20',), second)), transport=transport)
    capture(w)
    assert not transport.calls


@pytest.mark.parametrize('location', ['https://other.test/', 'http://example.org/', 'http://127.0.0.1/',
    'http://169.254.169.254/', '/outside', '/a?submit=1', '/old%20path', 'https://example.org:8443/'])
def test_redirect_rejected_before_next_exchange(location):
    transport = RecordedTransport({'https://example.org/robots.txt': routes()['https://example.org/robots.txt'],
        'https://example.org/': (302, {'location': location}, b'')})
    bundle = capture(worker(transport=transport))
    assert len(transport.calls) == 2 and not bundle.objects


def test_loop_and_fake_peer_never_produce_retained_content():
    for kwargs in ({'peer': '93.184.216.21'}, {'peer': '127.0.0.1'}):
        transport = RecordedTransport(routes(), **kwargs)
        assert not capture(worker(transport=transport)).objects
    transport = RecordedTransport({**routes(), 'https://example.org/': (302, {'location': '/'}, b'')})
    assert not capture(worker(transport=transport)).objects
    assert len(transport.calls) == 2


@pytest.mark.parametrize('field', ['tenant_id', 'request_id', 'policy_id', 'policy_version', 'policy_sha256'])
def test_wrong_server_scope_or_policy_fingerprint_denies(field):
    original = access()
    held = replace(pins(original), **{field: 99 if field == 'policy_version' else 'foreign'})
    with pytest.raises(CollectionError):
        worker(original=original, held=held)


def test_wrong_run_and_midflight_policy_revocation_deny():
    w = worker()
    with pytest.raises(CollectionError):
        asyncio.run(w.capture('run-foreign'))
    policy = fixture('SourcePolicy')
    original = SourceAccess(fixture('AuditRequest'), lambda: policy, terms_reference='terms-test', now=lambda: NOW)
    w = worker(original=original)
    policy['revoked_at'] = NOW.isoformat()
    with pytest.raises(CollectionError, match='POLICY_REVOKED'):
        asyncio.run(w.capture(w.access.held.run_id))


@pytest.mark.parametrize('grant', [replace(permit(), expires_at=NOW),
    replace(permit(), not_before=NOW+timedelta(seconds=1)), replace(permit(), origin='https://other.test'),
    replace(permit(), exact_paths=('/',)), replace(permit(), exact_paths=('/', '/robots.txt', '/x?token=1'))])
def test_expired_not_yet_valid_or_invalid_scope_permit_denied(grant):
    with pytest.raises(CollectionError):
        worker(grant=grant)


@pytest.mark.parametrize('mode', ['L0', 'L1'])
def test_original_five_eight_page_caps_remain(mode):
    audit = fixture('AuditRequest')
    audit['audit_mode'] = mode
    original = SourceAccess(audit, lambda: fixture('SourcePolicy'), terms_reference='terms-test', now=lambda: NOW)
    budget = Budget(Limits(max_pages=8), FencedAccess(original, held=pins(original), permit=permit()))
    for _ in range(5 if mode == 'L0' else 8):
        budget.page()
    with pytest.raises(CollectionError, match='LIMIT_EXCEEDED'):
        budget.page()


def test_l2_is_not_disguised_as_l1_and_live_flags_cannot_enable_network(monkeypatch):
    audit, policy = fixture('AuditRequest'), fixture('SourcePolicy')
    audit['audit_mode'] = 'L2'
    policy.update(mode='OWNER_AUTHORIZED_DEEP', authorization_reference='owner-synthetic', expires_at=(NOW+timedelta(seconds=120)).isoformat())
    with pytest.raises(CollectionError, match='SOURCE_NOT_ALLOWED'):
        SourceAccess(audit, lambda: policy, terms_reference='terms-test', now=lambda: NOW)
    monkeypatch.setenv('LIVE_CAPTURE_ENABLED', '1')
    with pytest.raises(PermissionError, match='LIVE_CAPTURE_DISABLED'):
        capture_live(approved=True, secret='synthetic-not-a-secret')
    with pytest.raises(CollectionError):
        ConnectionFence(None, PinnedTransport())


@pytest.mark.parametrize('error', ['TIMEOUT', 'TLS_FAILED', 'NETWORK_ERROR'])
def test_unavailable_or_untrusted_transport_stays_unknown(error):
    bundle = capture(worker(transport=RecordedTransport(routes(), error=error)))
    assert bundle.manifest['pages'][0]['snapshot']['status'] == 'UNKNOWN' and not bundle.objects


@pytest.mark.parametrize('kind', ['post', 'foreign-run'])
def test_direct_fetch_cannot_bypass_method_or_run_fence(kind):
    w = worker()
    budget = Budget(Limits(), w.access)
    budget.run_id = 'run-foreign' if kind == 'foreign-run' else w.access.held.run_id
    with pytest.raises(CollectionError):
        asyncio.run(w.fetcher.fetch(w.access.start_url, 'POST' if kind == 'post' else 'GET', budget))
    assert not w.fetcher.transport.transport.calls


@pytest.mark.parametrize('change', [{'audit_mode': 'L2'}, {'site_url': 'https://example.org/products'}])
def test_initialized_audit_cannot_be_rewritten_even_with_owner_mode_policy(change):
    policy = fixture('SourcePolicy')
    policy.update(mode='OWNER_AUTHORIZED_DEEP', authorization_reference='owner-synthetic',
                  expires_at=(NOW+timedelta(seconds=120)).isoformat())
    original = SourceAccess(fixture('AuditRequest'), lambda: policy, terms_reference='terms-test', now=lambda: NOW)
    w = worker(original=original)
    w.access.audit.update(change)
    with pytest.raises(CollectionError, match='SOURCE_NOT_ALLOWED'):
        asyncio.run(w.capture(w.access.held.run_id))
    assert not w.fetcher.transport.transport.calls
