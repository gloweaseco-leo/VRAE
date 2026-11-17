"""Contract negatives use explicitly synthetic DOM/PNG, not browser proof."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json

import pytest

from tests.evidence.synthetic import browser, http
from vrae.collection.manifest import document_hash, sha256
from vrae.evidence import build_pack, EvidenceError, EvidencePack
from vrae.rules.s2_ux import BrowserPins, project_browser


def fixture(elements=None, *, status='OBSERVED', extension=None):
    bundle = browser(True)
    item = bundle.manifest['observations'][0]
    dom = {'title': 'Synthetic', 'url': item['url'], 'elements': elements or []}
    dom.update(extension or {})
    raw = json.dumps(dom, ensure_ascii=False).encode()
    del bundle.objects[item['dom_ref']]
    bundle.objects[sha256(raw)] = raw
    item['dom_ref'] = sha256(raw)
    item['status'] = status
    if status != 'OBSERVED':
        item['errors'] = ['SOURCE_NOT_ALLOWED']
    bundle.manifest['sha256'] = document_hash({k: v for k, v in bundle.manifest.items()
                                             if k != 'sha256'})
    pack = build_pack([bundle])
    return pack, pins(pack)


def pins(pack):
    doc = pack.document
    at = datetime.fromisoformat(doc['sources'][0]['document']['observations'][0]['observed_at'])
    return BrowserPins(doc['tenant_id'], doc['run_id'], doc['policy_id'], doc['policy_version'],
                       pack.ref, tuple(s['source_ref'] for s in doc['sources']),
                       at - timedelta(seconds=1), at + timedelta(seconds=1))


def test_original_references_and_text_candidates_are_not_findings():
    pack, held = fixture([{'tag': 'A', 'visible': True, 'text': 'Contact 联系我们'},
                          {'tag': 'H1', 'visible': True, 'text': 'P40 Pump'}])
    projection = project_browser(pack, held=held)
    doc = projection.document
    row = next(r for r in doc['rows'] if r['status'] == 'OBSERVED')
    assert {c['kind'] for c in row['candidates']} == {
        'CTA_TEXT_ONLY', 'LANGUAGE_TEXT_REVIEW', 'HEADING_OR_IMAGE_TAG_ONLY'}
    for c in row['candidates']:
        original = pack.resolve(c['evidence_ref'], expected_pack_ref=pack.ref)
        assert json.loads(original['content'])['elements'][int(c['json_pointer'].split('/')[-1])]['text'] == c['text']
        assert c['review'] == 'HUMAN_REVIEW_REQUIRED'
    assert {r['result'] for r in row['rules']} == {'UNKNOWN'}
    assert doc['coverage'] == {'unit': 'SELECTED_URL_VIEWPORT', 'selected': 2,
                               'observed': 1, 'usable_dom': 1, 'not_visited': 1}
    assert 'NOT_RULE_EXECUTION' in doc['limitations']
    doc['rows'].clear()
    assert projection.document['rows']  # detached result, no mutable alias


@pytest.mark.parametrize('field,value', [
    ('tenant_id', 'other'), ('run_id', 'other'), ('policy_id', 'other'),
    ('policy_version', 2), ('pack_ref', 'ep-' + '0' * 64),
    ('source_refs', ('src-' + '0' * 64,)), ('source_refs', ()),
    ('observed_after', datetime(2099, 1, 1, tzinfo=timezone.utc)),
    ('observed_before', datetime(2000, 1, 1, tzinfo=timezone.utc)),
    ('observed_after', datetime(2000, 1, 1)),
])
def test_wrong_scope_stale_time_and_missing_selection_rejected(field, value):
    pack, held = fixture()
    with pytest.raises(EvidenceError):
        project_browser(pack, held=replace(held, **{field: value}))


@pytest.mark.parametrize('element', [
    {'tag': 'A', 'visible': True, 'text': 'RFQ', 'href': '/rfq'},
    {'tag': 'IMG', 'visible': True, 'text': '', 'alt': 'Pump'},
    {'tag': 'BUTTON', 'visible': True, 'text': 'Quote', 'hit_test': True},
    {'tag': 'A', 'visible': 'true', 'text': 'Contact'},
    {'tag': 'A', 'visible': True, 'text': 'x' * 161},
])
def test_resealed_extra_dom_fields_cannot_confer_new_measurement_authority(element):
    pack, held = fixture([element])
    rows = project_browser(pack, held=held).document['rows']
    observed = next(r for r in rows if r['status'] == 'OBSERVED')
    assert not observed['candidates']
    assert not observed['evidence_refs']
    assert not observed['dom_usable']
    assert {r['reason'] for r in observed['rules']} == {'DOM_PRODUCER_UNSUPPORTED_OR_AMBIGUOUS'}


def test_forged_geometry_extension_not_accepted():
    pack, held = fixture(extension={'scrollWidth': 900, 'clientWidth': 390})
    assert all(not r['candidates'] for r in project_browser(pack, held=held).document['rows'])


@pytest.mark.parametrize('status', ['ACCESS_BLOCKED', 'UNKNOWN'])
def test_incomplete_or_forbidden_subresource_is_not_website_failure(status):
    pack, held = fixture([{'tag': 'A', 'visible': True, 'text': 'Contact'}], status=status)
    row = next(r for r in project_browser(pack, held=held).document['rows']
               if r['status'] != 'NOT_VISITED')
    assert not row['candidates'] and not row['evidence_refs']
    assert {r['result'] for r in row['rules']} == {status}


def test_http_only_cannot_masquerade_as_browser_source():
    pack, held = fixture()
    other = build_pack([http()])
    with pytest.raises(EvidenceError):
        project_browser(other, held=replace(held, pack_ref=other.ref,
            source_refs=tuple(s['source_ref'] for s in other.document['sources'])))


def test_mutated_blob_and_forged_pack_subclass_rejected():
    pack, held = fixture()
    objects = tuple((k, v + b'tamper') for k, v in pack._blobs)
    with pytest.raises(EvidenceError):
        project_browser(EvidencePack(pack._payload, objects), held=held)
    class Forged(EvidencePack):
        def verify(self, **kwargs):
            pass
    with pytest.raises(EvidenceError):
        project_browser(Forged(pack._payload, pack._blobs), held=held)


def test_old_source_ref_cannot_be_reused_with_new_pack():
    old, old_pins = fixture()
    new, new_pins = fixture([{'tag': 'A', 'visible': False, 'text': 'RFQ'}])
    with pytest.raises(EvidenceError):
        project_browser(new, held=replace(new_pins, source_refs=old_pins.source_refs))
    assert old.ref != new.ref
