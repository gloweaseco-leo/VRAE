"""Offline P1 regressions: internally valid sources must describe one audited host."""
import json
import base64
from pathlib import Path

import pytest

from vrae.collection.manifest import document_hash, sha256
from vrae.evidence import EvidenceError, EvidencePack, build_pack
from .synthetic import browser, http


def seal(source):
    field = 'manifest_sha256' if 'pages' in source.manifest else 'sha256'
    source.manifest[field] = document_hash({
        k: v for k, v in source.manifest.items() if k != field})
    source.verify()
    return source


def relocate_browser(observed):
    source = browser(observed)
    # Rewrite every URL and retained DOM, preserving source-internal consistency.
    source.manifest = json.loads(json.dumps(source.manifest).replace(
        'https://example.org', 'https://unrelated.example'))
    if observed:
        item = source.manifest['observations'][0]
        raw = source.objects.pop(item['dom_ref']).replace(
            b'https://example.org', b'https://unrelated.example')
        item['dom_ref'] = sha256(raw)
        source.objects[sha256(raw)] = raw
    else:
        source.manifest['observations'] = []
        source.objects = {}
    return seal(source)


@pytest.mark.parametrize('observed', [False, True])
@pytest.mark.parametrize('reverse', [False, True])
def test_wrong_site_mixed_sources_rejected(observed, reverse):
    sources = [http(), relocate_browser(observed)]
    for source in sources:
        source.verify()
    with pytest.raises(EvidenceError, match='^EVIDENCE_INTEGRITY$'):
        build_pack(sources[::-1] if reverse else sources)


@pytest.mark.parametrize('field', ['inventory', 'final_url'])
def test_http_only_wrong_site_rejected(field):
    source = http()
    if field == 'inventory':
        source.manifest['inventory'].append({
            'url': 'https://unrelated.example/products', 'role': 'CATALOG',
            'discovered_from': 'https://example.org/'})
    else:
        page = source.manifest['pages'][0]
        page['snapshot']['final_url'] = 'https://unrelated.example/'
        hop = page['redirect_trace'][0]
        hop.update(status=302, location='https://unrelated.example/')
        page['redirect_trace'].append({**hop, 'url': 'https://unrelated.example/',
                                      'status': 200, 'location': None})
    seal(source)
    with pytest.raises(EvidenceError):
        build_pack([source])


def test_browser_only_wrong_site_approved_inventory_rejected():
    source = browser(True)
    source.manifest['approved_urls'].append('https://sub.example.org/products')
    seal(source)
    with pytest.raises(EvidenceError):
        build_pack([source])


def test_independent_replay_rejects_pre_fix_wrong_site_pack():
    data = json.loads((Path(__file__).parents[1] /
        'fixtures/evidence/wrong-site-legacy.json').read_text(encoding='utf-8'))
    with pytest.raises(EvidenceError):
        EvidencePack.load(data['document'], {
            k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()})


def test_same_site_with_cdn_subresource_remains_valid_and_pinned():
    source = browser(True)
    item = source.manifest['observations'][0]
    item['resources'].append({**item['resources'][0],
        'url': 'https://cdn.example/image.png', 'resource_type': 'Image',
        'redirect_trace': [{**item['resources'][0]['redirect_trace'][0],
                            'url': 'https://cdn.example/image.png'}]})
    seal(source)
    old = build_pack([http(), source])
    old.verify(expected_ref=old.ref)
    assert old.ref == build_pack([source, http()]).ref
    source.manifest['observations'][0]['observed_at'] = '2026-11-10T12:01:00+00:00'
    seal(source)
    future = build_pack([http(), source])
    assert future.ref != old.ref
    with pytest.raises(EvidenceError):
        future.verify(expected_ref=old.ref)
    doc = old.document
    doc['schema_version'] = '2.0'
    with pytest.raises(EvidenceError):
        EvidencePack.load(doc, old.objects)
