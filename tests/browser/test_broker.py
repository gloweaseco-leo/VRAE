import asyncio
import pytest

from vrae.browser.broker import ResourceBroker
from vrae.collection.errors import CollectionError
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Budget, Limits
from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access


def broker():
    a = access()
    transport = SyntheticTransport({'https://example.org/robots.txt':
        (200, {'content-type': 'text/plain'}, b'User-agent: *\nDisallow: /private')})
    return ResourceBroker(SafeFetcher(FixedDNS(), transport),
                          Budget(Limits(interval_seconds=0.01), a), ['https://example.org/']), transport


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE', 'CONNECT'])
def test_write_methods_do_not_reach_transport(method):
    b, transport = broker()
    with pytest.raises(CollectionError):
        asyncio.run(b.read('https://example.org/', method, 'Document'))
    assert not transport.calls


@pytest.mark.parametrize('url,kind', [
    ('http://127.0.0.1/', 'Image'), ('http://169.254.169.254/', 'Fetch'),
    ('https://cdn.test/a.js', 'Script'), ('file:///etc/passwd', 'Document'),
    ('https://example.org/private', 'Image'), ('https://example.org/unapproved', 'Document'),
    ('https://example.org/', 'WebSocket'), ('https://example.org/', 'Other'),
])
def test_resource_policy_fail_closed(url, kind):
    b, transport = broker()
    with pytest.raises(CollectionError):
        asyncio.run(b.read(url, 'GET', kind))
    assert all(c[0].endswith('/robots.txt') for c in transport.calls)


def test_document_is_brokered_without_cookies_or_remote_headers():
    b, transport = broker()
    result = asyncio.run(b.read('https://example.org/', 'GET', 'Document'))
    assert result['body'] and result['status'] == 200
    assert 'set-cookie' not in result['headers']
    assert b.trace[-1]['outcome'] == 'FETCHED'
    assert len(transport.calls) == 2
