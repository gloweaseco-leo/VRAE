import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from vrae.browser.observation import seal, VIEWPORTS
from vrae.browser.broker import ResourceBroker
from vrae.collection.errors import CollectionError
from vrae.collection.limits import Budget, Limits
from vrae.collection.manifest import document_hash, sha256
from vrae.collection.policy import SourceAccess
from .test_broker import broker
from tests.collection.test_security import fixture, NOW


def bundle():
    b, _ = broker()
    data = b'{"title":"synthetic"}'
    digest = sha256(data)
    item = {'url': b.urls[0], 'viewport': dict(VIEWPORTS[0]), 'observed_at': NOW.isoformat(),
            'status': 'UNKNOWN', 'dom_ref': digest, 'screenshot_ref': None,
            'errors': ['TIMEOUT'], 'resources': []}
    return seal(b, 'run-test', 'Chrome/synthetic-contract-only', [item], {digest: data})


def test_browser_schema_valid_and_private():
    path = Path(__file__).parents[2] / 'contracts/v1/browser/BrowserObservation.schema.json'
    Draft202012Validator.check_schema(json.loads(path.read_text()))
    result = bundle()
    result.verify()
    assert result.manifest['private'] is True


@pytest.mark.parametrize('mutation', ['duplicate', 'scope', 'viewport', 'hash', 'success', 'orphan', 'private'])
def test_resealed_observation_contradictions_rejected(mutation):
    result = bundle()
    item = result.manifest['observations'][0]
    if mutation == 'duplicate':
        result.manifest['observations'].append(copy.deepcopy(item))
    elif mutation == 'scope':
        item['url'] = 'https://other.test/'
    elif mutation == 'viewport':
        item['viewport']['width'] = 999
    elif mutation == 'hash':
        result.objects[item['dom_ref']] = b'tampered'
    elif mutation == 'success':
        item['status'] = 'OBSERVED'
    elif mutation == 'orphan':
        result.objects['0'*64] = b'orphan'
    else:
        result.manifest['private'] = False
    result.manifest['sha256'] = document_hash({k:v for k,v in result.manifest.items() if k != 'sha256'})
    with pytest.raises((CollectionError, ValidationError)):
        result.verify()


@pytest.mark.parametrize('mode,urls', [('L0', ['https://example.org/']),
    ('L1', []), ('L1', ['https://example.org/']*4), ('L1', ['https://example.org/']*2)])
def test_browser_admission_caps_and_l0(mode, urls):
    request, policy = fixture('AuditRequest'), fixture('SourcePolicy')
    request['audit_mode'] = mode
    a = SourceAccess(request, lambda: policy, terms_reference='synthetic', now=lambda: NOW)
    b, _ = broker()
    with pytest.raises(CollectionError):
        ResourceBroker(b.fetcher, Budget(Limits(), a), urls)


def test_observed_without_fetched_document_rejected_even_with_artifacts():
    result = bundle()
    item = result.manifest['observations'][0]
    item.update(status='OBSERVED', errors=[], screenshot_ref=item['dom_ref'])
    result.manifest['sha256'] = document_hash({k:v for k,v in result.manifest.items() if k != 'sha256'})
    with pytest.raises(CollectionError):
        result.verify()
