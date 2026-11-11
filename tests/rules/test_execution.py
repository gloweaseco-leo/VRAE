from copy import deepcopy
import base64
import json
from pathlib import Path

import pytest

from vrae.rules import execute, verify_execution
from vrae.evidence import EvidenceError
from vrae.evidence import EvidencePack, build_pack
from vrae.collection.manifest import document_hash
from vrae.domain.contracts import validate_contract
from .synthetic import site


def discover(output):
    return next(e for e in output['executions'] if e['rule_id'] == 'DISC-01')['observations']


@pytest.mark.parametrize('status,expected', [(200, 'PASS'), (404, 'FAIL_WITH_EVIDENCE'),
    (410, 'FAIL_WITH_EVIDENCE'), (403, 'ACCESS_BLOCKED'), (503, 'ACCESS_BLOCKED'),
    (500, 'UNKNOWN')])
def test_real_href_and_captured_response(status, expected):
    pack = site(status)
    output = execute(pack, expected_pack_ref=pack.ref)
    row = discover(output)[0]
    assert row['observation']['result'] == expected
    validate_contract('Observation', row['observation'])
    if expected in ('PASS', 'FAIL_WITH_EVIDENCE'):
        assert row['observation']['evidence_ids']
        assert row['citations'][0]['raw_href'] == '/category/valves'
        assert row['target_response']['http_status'] == status
    else:
        assert row['observation']['evidence_ids'] == []
    verify_execution(output, pack, expected_pack_ref=pack.ref)
    assert output == execute(pack, expected_pack_ref=pack.ref)


@pytest.mark.parametrize('kwargs', [{'retained': False}, {'linked': False}, {'target': False}])
def test_missing_content_or_unvisited_target_is_unknown(kwargs):
    pack = site(**kwargs)
    assert {r['observation']['result'] for r in discover(
        execute(pack, expected_pack_ref=pack.ref))} == {'UNKNOWN'}


def test_all_five_tasks_and_frozen_catalog_without_fake_disabled_facts():
    pack = site()
    output = execute(pack, expected_pack_ref=pack.ref)
    assert len(output['executions']) == 16
    assert {r['buyer_task'] for r in output['executions']} == {
        'DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL'}
    for execution in output['executions']:
        assert execution['rule_version'] == '1.0.0'
        for row in execution['observations']:
            validate_contract('Observation', row['observation'])
            if execution['rule_id'] != 'DISC-01':
                assert row['observation']['result'] == 'UNKNOWN'
                assert row['observation']['evidence_ids'] == []


@pytest.mark.parametrize('mutation', ['statement', 'result', 'citation', 'scope', 'version', 'coverage'])
def test_independent_replay_rejects_fabricated_assertions(mutation):
    pack = site()
    output = deepcopy(execute(pack, expected_pack_ref=pack.ref))
    row = discover(output)[0]
    if mutation == 'statement':
        row['observation']['statement'] = 'All categories work on mobile'
    elif mutation == 'result':
        row['observation']['result'] = 'FAIL_WITH_EVIDENCE'
    elif mutation == 'citation':
        row['citations'][0]['raw_href'] = '/invented'
    elif mutation == 'scope':
        row['observation']['tenant_id'] = 'other-tenant'
    elif mutation == 'version':
        output['executions'][0]['rule_version'] = '2.0.0'
    else:
        row['observation']['coverage_note'] = 'Whole website'
    with pytest.raises(EvidenceError):
        verify_execution(output, pack, expected_pack_ref=pack.ref)


def test_trusted_pin_required_before_execution_or_replay():
    pack = site()
    with pytest.raises(EvidenceError):
        execute(pack, expected_pack_ref='ep-' + '0' * 64)
    other = site(404)
    with pytest.raises(EvidenceError):
        verify_execution(execute(pack, expected_pack_ref=pack.ref), other,
                         expected_pack_ref=pack.ref)


@pytest.mark.parametrize('pin', [None, '', 'ep-invalid'])
def test_optional_or_untrusted_pin_is_not_accepted(pin):
    with pytest.raises(EvidenceError):
        execute(site(), expected_pack_ref=pin)


@pytest.mark.parametrize('markup', [
    b'<html><base href="https://unrelated.example/"><nav><a href="/category/valves">Catalog</a></nav></html>',
    b'<html><nav><a href="/category/valves" href="/different">Catalog</a></nav></html>',
    b'<html><nav><template><a href="/category/valves">Catalog</a></template></nav></html>',
    b'<html><nav><a href="https://unrelated.example/category/valves">Catalog</a></nav></html>',
    b'<html><a href="/category/valves">Outside explicit nav</a></html>',
    b'<html><nav><a href="#">Products</a></nav><script>/* dynamic menu */</script></html>',
    b'<html><nav><a hidden href="/category/valves">Hidden</a></nav></html>',
])
def test_incomplete_ambiguous_or_unsupported_navigation_never_becomes_failure(markup):
    pack = site(markup=markup)
    rows = discover(execute(pack, expected_pack_ref=pack.ref))
    assert {r['observation']['result'] for r in rows} == {'UNKNOWN'}


def test_two_links_keep_separate_scopes_not_whole_site_fail():
    from tests.collection.test_pipeline import collect
    source, _ = collect({
        'https://example.org/': (200, {'content-type': 'text/html'},
            b'<html><nav><a href="/category/valves">Valves</a>'
            b'<a href="/category/pumps">Pumps</a></nav></html>'),
        'https://example.org/category/pumps': (404, {'content-type': 'text/html'}, b'<html>404</html>')
    }, retain_raw_html=True)
    pack = build_pack([source])
    rows = discover(execute(pack, expected_pack_ref=pack.ref))
    assert {r['observation']['result'] for r in rows} == {'PASS', 'FAIL_WITH_EVIDENCE'}
    assert len({r['observation']['observation_id'] for r in rows}) == 2
    for row in rows:
        assert row['homepage']['url'] == 'https://example.org/'
        assert len(row['citations']) == 1
        assert row['target_response']['url'].startswith('https://example.org/category/')


def test_browser_dom_without_href_cannot_support_navigation_or_visible_cta():
    from tests.evidence.synthetic import browser
    pack = build_pack([browser(True)])
    output = execute(pack, expected_pack_ref=pack.ref)
    assert all(row['observation']['result'] == 'UNKNOWN'
               for e in output['executions'] for row in e['observations'])


def test_homepage_blocked_never_becomes_category_absence():
    from tests.collection.test_pipeline import collect
    source, _ = collect({'https://example.org/':
        (403, {'content-type': 'text/html'}, b'blocked')})
    pack = build_pack([source])
    assert discover(execute(pack, expected_pack_ref=pack.ref))[0]['observation']['result'] == 'ACCESS_BLOCKED'


@pytest.mark.parametrize('mutation', ['blob', 'scope', 'cross-site'])
def test_source_tampering_rejected_before_rule_judgment(mutation):
    pack = site()
    doc, objects = pack.document, dict(pack.objects)
    if mutation == 'blob':
        objects[next(iter(objects))] = b'invented raw HTML'
    elif mutation == 'scope':
        doc['tenant_id'] = 'other-tenant'
    else:
        from tests.evidence.test_site_coherence import relocate_browser
        from tests.evidence.synthetic import http
        with pytest.raises(EvidenceError):
            build_pack([http(), relocate_browser(True)])
        return
    doc['pack_ref'] = 'ep-' + document_hash({k: v for k, v in doc.items() if k != 'pack_ref'})
    with pytest.raises(EvidenceError):
        EvidencePack.load(doc, objects)
    tampered = EvidencePack(json.dumps(doc).encode(), tuple(sorted(objects.items())))
    with pytest.raises(EvidenceError):
        execute(tampered, expected_pack_ref=doc['pack_ref'])


def test_no_independent_applicability_evidence_means_no_not_applicable():
    # Industrial pack's short applicable_rule_ids list is not proof that other
    # buyer tasks are inapplicable. No NA or factual claim is inferred from it.
    pack = site(linked=False)
    output = execute(pack, expected_pack_ref=pack.ref)
    assert all(row['observation']['result'] == 'UNKNOWN'
               for e in output['executions'] for row in e['observations'])


def test_checked_in_industrial_example_replays_all_assertions():
    data = json.loads((Path(__file__).parents[1] /
        'fixtures/rules/industrial-navigation.json').read_text(encoding='utf-8'))
    pack = EvidencePack.load(data['document'], {
        k: base64.b64decode(v, validate=True) for k, v in data['objects_base64'].items()
    }, expected_ref=data['expected_pack_ref'])
    verify_execution(data['expected_execution'], pack, expected_pack_ref=data['expected_pack_ref'])
    rows = discover(data['expected_execution'])
    assert {row['observation']['result'] for row in rows} == {'PASS', 'FAIL_WITH_EVIDENCE'}
    for row in rows:
        for ref in row['observation']['evidence_ids']:
            resolved = pack.resolve(ref, expected_pack_ref=data['expected_pack_ref'])
            assert resolved['content'] is not None
            assert resolved['snapshot']['capture_mode'] == 'HTTP'


def test_category_path_redirecting_to_other_role_stays_unknown():
    from tests.collection.test_pipeline import collect
    source, _ = collect({
        'https://example.org/': (200, {'content-type': 'text/html'},
            b'<html><nav><a href="/category/valves">Valves</a></nav></html>'),
        'https://example.org/category/valves': (302, {'location': '/landing'}, b''),
        'https://example.org/landing': (200, {'content-type': 'text/html'}, b'<html>Landing</html>'),
    }, retain_raw_html=True)
    pack = build_pack([source])
    assert discover(execute(pack, expected_pack_ref=pack.ref))[0]['observation']['result'] == 'UNKNOWN'
