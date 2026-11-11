"""Negative cases address provenance edges, not natural-language website claims."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import base64

import pytest

from vrae.collection.manifest import document_hash
from vrae.evidence import EvidencePack, EvidenceError, build_pack
from tests.collection.test_pipeline import collect
from .synthetic import http, browser


def reseal(doc):
    doc['pack_ref'] = 'ep-' + document_hash({k: v for k, v in doc.items() if k != 'pack_ref'})
    return doc


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_mixed_scope_rejected(field):
    other = browser()
    other.manifest[field] = 2 if field == 'policy_version' else 'other-value'
    other.manifest['sha256'] = document_hash({k: v for k, v in other.manifest.items() if k != 'sha256'})
    with pytest.raises(EvidenceError):
        build_pack([http(), other])


@pytest.mark.parametrize('mutation', ['locator', 'excerpt', 'capture_mode'])
def test_source_locator_gap_closed_without_changing_capture_verifier(mutation):
    source = http()
    if mutation == 'locator':
        source.manifest['pages'][0]['evidence']['locator'] = 'different-page#fabrication'
    elif mutation == 'excerpt':
        source.manifest['pages'][0]['evidence']['excerpt'] = 'Unsupported synthetic business claim'
    else:
        source.manifest['pages'][0]['snapshot']['capture_mode'] = 'BROWSER'
    source.manifest['manifest_sha256'] = document_hash({
        k: v for k, v in source.manifest.items() if k != 'manifest_sha256'})
    source.verify()  # Existing contract accepts free-text locators; adapter must narrow them.
    with pytest.raises(EvidenceError):
        build_pack([source])


@pytest.mark.parametrize('mutation', ['source', 'missing-source', 'duplicate-source', 'pointer',
    'hash', 'duplicate-evidence', 'snapshot', 'scope', 'coverage', 'status', 'old-version',
    'content-ref', 'limitation', 'unsupported-na', 'object', 'orphan'])
def test_recomputed_outer_hash_does_not_hide_broken_edges(mutation):
    pack = build_pack([http(), browser()])
    doc, objects = pack.document, dict(pack.objects)
    item = doc['evidence'][0]
    if mutation == 'source':
        doc['sources'][0]['document']['run_id'] = 'other-run'
    elif mutation == 'missing-source':
        doc['sources'] = doc['sources'][1:]
    elif mutation == 'duplicate-source':
        doc['sources'].append(deepcopy(doc['sources'][0]))
    elif mutation == 'pointer':
        item['locator'] = '/pages/999/snapshot'
    elif mutation == 'hash':
        item['content_sha256'] = '0' * 64
    elif mutation == 'duplicate-evidence':
        doc['evidence'].append(deepcopy(item))
    elif mutation == 'snapshot':
        item['snapshot_ref'] = 'page-' + '0' * 64
    elif mutation == 'scope':
        doc['tenant_id'] = 'other-tenant'
    elif mutation == 'coverage':
        doc['coverage'].pop()
    elif mutation == 'status':
        next(i for i in doc['evidence'] if i['status'] != 'OBSERVED')['status'] = 'OBSERVED'
    elif mutation == 'old-version':
        item['source_ref'] = 'src-' + '0' * 64
    elif mutation == 'content-ref':
        item['blob_ref'] = '0' * 64
    elif mutation == 'limitation':
        doc['integrity']['limitations'] = []
    elif mutation == 'unsupported-na':
        doc['coverage'][0]['status'] = 'NOT_APPLICABLE'
    elif mutation == 'object':
        objects[next(iter(objects))] = b'tampered'
    else:
        objects['0' * 64] = b'orphan'
    with pytest.raises(EvidenceError):
        EvidencePack.load(reseal(doc), objects)


@pytest.mark.parametrize('sources', [[], [http(), http()]])
def test_empty_or_repeated_source_rejected(sources):
    with pytest.raises(EvidenceError):
        build_pack(sources)


def test_changed_source_creates_new_reference_and_cannot_alias_old_version():
    original = http()
    old = build_pack([original])
    changed = deepcopy(original)
    changed.manifest['pages'][0]['snapshot']['captured_at'] = '2026-11-10T12:01:00+00:00'
    changed.manifest['pages'][0]['evidence']['observed_at'] = '2026-11-10T12:01:00+00:00'
    changed.manifest['manifest_sha256'] = document_hash({
        k: v for k, v in changed.manifest.items() if k != 'manifest_sha256'})
    new = build_pack([changed])
    assert old.ref != new.ref
    assert old.document['evidence'][0]['evidence_ref'] != new.document['evidence'][0]['evidence_ref']
    with pytest.raises(EvidenceError):
        build_pack([original, changed])
    with pytest.raises(EvidenceError):
        new.resolve(old.document['evidence'][0]['evidence_ref'], expected_pack_ref=old.ref)


def test_immutable_copy_and_order_independent_reproducibility():
    source, other = http(), browser()
    pack = build_pack([source, other])
    assert pack.ref == build_pack([other, source]).ref
    before = pack.document
    pack.document['evidence'].clear()
    source.manifest['pages'].clear()
    source.objects.clear()
    assert pack.document == before
    pack.verify()
    with pytest.raises((FrozenInstanceError, AttributeError)):
        pack._payload = b'changed'
    with pytest.raises(TypeError):
        pack.objects['bad'] = b'mutation'


def test_missing_raw_preserves_metadata_but_cannot_return_body():
    pack = build_pack([http(False)])
    item = pack.document['evidence'][0]
    assert item['status'] == 'OBSERVED' and item['blob_ref'] is None
    assert 'RAW_BODY_NOT_RETAINED' in item['limitations']
    assert item['content_verification'] == 'NOT_RECOMPUTABLE'
    assert pack.resolve(item['evidence_ref'], expected_pack_ref=pack.ref)['content'] is None


@pytest.mark.parametrize('status', [403, 503])
def test_blocked_is_not_business_fact(status):
    source, _ = collect({'https://example.org/': (status, {'content-type': 'text/html'}, b'blocked')})
    pack = build_pack([source])
    assert not pack.document['evidence']
    assert pack.document['snapshots'][0]['status'] == 'ACCESS_BLOCKED'
    assert all(c['status'] != 'OBSERVED' for c in pack.document['coverage'])


def test_browser_incomplete_keeps_unknown_and_missing_viewport_not_visited():
    pack = build_pack([browser()])
    assert pack.document['evidence'][0]['status'] == 'UNKNOWN'
    assert {'UNKNOWN', 'NOT_VISITED'} <= {c['status'] for c in pack.document['coverage']}
    with pytest.raises(EvidenceError):
        pack.resolve(pack.document['evidence'][0]['evidence_ref'], expected_pack_ref=pack.ref)


def test_serialization_roundtrip_requires_pinned_identity():
    pack = build_pack([http(), browser()])
    cloned = EvidencePack.load(json.loads(json.dumps(pack.document)), dict(pack.objects), expected_ref=pack.ref)
    assert cloned.document == pack.document
    with pytest.raises(EvidenceError):
        cloned.verify(expected_ref='ep-' + '0' * 64)


@pytest.mark.parametrize('mode', ['HTTP', 'BROWSER', 'JOINT'])
def test_positive_sources_resolve_exact_records(mode):
    sources = {'HTTP': [http()], 'BROWSER': [browser(True)], 'JOINT': [http(), browser(True)]}[mode]
    pack = build_pack(sources)
    for ev in pack.document['evidence']:
        result = pack.resolve(ev['evidence_ref'], expected_pack_ref=pack.ref)
        assert result['content'] is not None
        assert ev['content_verification'] == 'HASH_VERIFIED'
        assert result['snapshot']['status'] == 'OBSERVED'
        assert result['evidence']['source_ref'] in {s['source_ref'] for s in pack.document['sources']}
    assert len(pack.document['evidence']) == {'HTTP': 1, 'BROWSER': 2, 'JOINT': 3}[mode]


def test_inventory_not_visited_does_not_become_absence():
    source = http()
    source.manifest['inventory'].append({'url': 'https://example.org/products', 'role': 'CATALOG',
                                         'discovered_from': 'https://example.org/'})
    source.manifest['manifest_sha256'] = document_hash({k: v for k, v in source.manifest.items() if k != 'manifest_sha256'})
    pack = build_pack([source])
    assert any(c['status'] == 'NOT_VISITED' and c['url'].endswith('/products') for c in pack.document['coverage'])
    assert any(c['status'] == 'UNKNOWN' and c['role'] == 'PRODUCT' for c in pack.document['coverage'])


@pytest.mark.parametrize('kind', ['DOM_URL', 'PNG_DIMENSIONS', 'PNG_TYPE'])
def test_rehashed_cross_page_browser_artifacts_are_rejected(kind):
    source = browser(True)
    item = source.manifest['observations'][0]
    field = 'dom_ref' if kind == 'DOM_URL' else 'screenshot_ref'
    old = source.objects.pop(item[field])
    if kind == 'DOM_URL':
        doc = json.loads(old)
        doc['url'] = 'https://example.org/unrelated'
        raw = json.dumps(doc).encode()
    elif kind == 'PNG_DIMENSIONS':
        raw = old[:16] + (1).to_bytes(4, 'big') + old[20:]
    else:
        raw = b'not-png'
    from vrae.collection.manifest import sha256
    item[field] = sha256(raw)
    source.objects[sha256(raw)] = raw
    source.manifest['sha256'] = document_hash({k: v for k, v in source.manifest.items() if k != 'sha256'})
    source.verify()  # Hashes alone do not locate DOM/PNG within a specific viewport.
    with pytest.raises(EvidenceError):
        build_pack([source])


def test_robots_denied_is_blocked():
    source, _ = collect({'https://example.org/robots.txt':
        (200, {'content-type': 'text/plain'}, b'User-agent: *\nDisallow: /\n')})
    pack = build_pack([source])
    assert not pack.document['evidence']
    assert pack.document['snapshots'][0]['status'] == 'ACCESS_BLOCKED'


def test_empty_browser_capture_is_not_visited():
    source = browser()
    source.manifest['observations'] = []
    source.objects = {}
    source.manifest['sha256'] = document_hash({k: v for k, v in source.manifest.items() if k != 'sha256'})
    pack = build_pack([source])
    assert not pack.document['evidence'] and not pack.document['snapshots']
    assert all(c['status'] == 'NOT_VISITED' for c in pack.document['coverage'])


def test_checked_in_example_independently_replays():
    example = json.loads((Path(__file__).parents[1] / 'fixtures/evidence/combined.json').read_text())
    pack = EvidencePack.load(example['document'], {
        k: base64.b64decode(v, validate=True) for k, v in example['objects_base64'].items()
    }, expected_ref=example['expected_pack_ref'])
    assert pack.ref == build_pack([http(), browser(True)]).ref
    assert len(pack.document['evidence']) == 3


def test_unretained_source_hash_cannot_be_silently_changed():
    source = http(False)
    old = build_pack([source])
    # No retained raw HTML means a consistent rewritten source cannot be authenticated.
    # It MUST acquire new references and fail against the previously pinned identity.
    source.manifest['pages'][0]['snapshot']['sha256'] = '0' * 64
    source.manifest['pages'][0]['evidence']['checksum'] = '0' * 64
    source.manifest['manifest_sha256'] = document_hash({
        k: v for k, v in source.manifest.items() if k != 'manifest_sha256'})
    new = build_pack([source])
    assert new.ref != old.ref
    with pytest.raises(EvidenceError):
        new.verify(expected_ref=old.ref)


@pytest.mark.parametrize('payload,blobs', [(bytearray(b'{}'), ()), (b'{}', []),
                                        (b'{}', (('ref', bytearray(b'body')),))])
def test_mutable_constructor_state_is_rejected(payload, blobs):
    with pytest.raises(EvidenceError):
        EvidencePack(payload, blobs)


def test_waf_without_business_findings():
    source, _ = collect({'https://example.org/':
        (200, {'content-type': 'text/html'}, b'<html>Verify you are human</html>')})
    pack = build_pack([source])
    assert pack.document['snapshots'][0]['status'] == 'ACCESS_BLOCKED'
    assert not pack.document['evidence']
    assert 'findings' not in pack.document
