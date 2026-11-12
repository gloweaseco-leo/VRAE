"""Buyer-task report acceptance and adversarial replay; no external services."""
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json

import pytest

from scripts.verify_ra3c import load_case, replay
from vrae.domain.contracts import validate_contract
from vrae.domain.reviews import report_content_hash
from vrae.evidence import EvidencePack
from vrae.findings import FindingPackage
from vrae.interpretation import validate as validate_claims
from vrae.reporting import ReportDraft, ReportError, build_draft, render
from vrae.reporting.common import digest
from .synthetic import inputs, source_pins, PRODUCT


@pytest.fixture(scope='module')
def baseline():
    return load_case(404)


def build(data):
    p, f, g, m, k, *_ = data
    return build_draft(p, f, g, m, **k)


def repin_guards(p, f, guards, pins):
    for b in guards:
        for binding in b['bindings']:
            binding['binding_ref'] = 'cb-' + digest({k: v for k, v in binding.items() if k != 'binding_ref'})
        b['guard'] = validate_claims(b['interpretation'], b['bindings'], p, f,
                                     **source_pins(p, f)).document
    pins['expected_guard_refs'] = [b['guard']['guard_ref'] for b in guards]


@pytest.mark.parametrize('mode,issues', [(404, 1), (410, 1), (200, 0), (403, 0), (500, 0),
    ('robots', 0), ('unretained', 0), ('waf', 0)])
def test_fixed_business_matrix(mode, issues):
    d = replay(mode)
    doc = d.document
    assert len(doc['issues']) == issues and doc['private'] is True and doc['shareable'] is False
    assert doc['approval_status'] == 'NOT_APPROVED' and doc['semantic_approval'] is False
    assert hashlib.sha256(d.html_bytes).hexdigest() == doc['html_sha256']
    if issues:
        native = doc['native_report_version']
        validate_contract('ReportVersion', native)
        assert native['status'] == 'REVIEW_REQUIRED' and native['approved_by'] is native['approved_at'] is None
        assert native['content_hash'] == report_content_hash(native, [i['finding'] for i in doc['issues']])
        assert doc['issues'][0]['target_response']['http_status'] == mode
        assert doc['issues'][0]['native_bridge']['kind'] == 'EXACT_NATIVE_HTTP_ID_MAPPING'
        assert next(t for t in doc['buyer_journey'] if t['task'] == 'TRUST')['observations'][0]['result'] == 'UNKNOWN'
        assert all(c['status'] == 'HUMAN_REVIEW_REQUIRED' for c in doc['issues'][0]['proposals'].values())
    else:
        assert doc['native_report_version'] is None and doc['kind'] == 'PRIVATE_COVERAGE_SUMMARY'
        assert '0 项可报告问题'.encode() in d.html_bytes


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.tags, self.handlers, self.assets = [], [], [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'a':
            self.links.append(a.get('href'))
        self.handlers.extend(k for k in a if k.startswith('on'))
        self.assets.extend(k for k in a if k in ('src', 'srcset', 'action', 'formaction'))


def test_standalone_private_html_has_only_resolved_internal_evidence(baseline):
    d = build(baseline)
    html = d.html_bytes.decode()
    parsed = Structure()
    parsed.feed(html)
    assert 'lang="zh-CN"' in html and 'Content-Security-Policy' in html
    assert len(parsed.ids) == len(set(parsed.ids))
    assert all(h and h.startswith('#') and h[1:] in parsed.ids for h in parsed.links)
    assert not parsed.handlers and not parsed.assets
    assert not {'script', 'iframe', 'form', 'img', 'video', 'object', 'embed', 'link'} & set(parsed.tags)
    assert 'NOT_APPROVED' in html and '不可客户外发' in html and 'aria-disabled="true"' in html
    for label in ('观察到的事实', '可能影响', '候选动作', '如何重新验证', '字节区间', 'EvidencePack', 'native_bridge'):
        assert label in html


@pytest.mark.parametrize('path,value', [
    (('approval_status',), 'APPROVED'), (('private',), False), (('shareable',), True),
    (('semantic_approval',), True), (('renderer_version',), 'new-layout'),
    (('renderer_asset_sha256',), '0' * 64), (('reporting_version',), 'future'),
    (('metadata', 'version'), 2), (('metadata', 'created_at'), '2027-01-01T00:00:00Z'),
    (('issues', 0, 'target_response', 'http_status'), 200),
    (('issues', 0, 'fact_claim', 'text'), 'This is a certified factory.'),
    (('issues', 0, 'proposals', 'impact', 'text'), 'Google rank dropped and sales were lost.'),
    (('issues', 0, 'fact_claim', 'status'), 'APPROVED'),
    (('native_report_version', 'approved_by'), 'forged-owner'),
    (('native_report_version', 'status'), 'APPROVED'),
    (('scope', 'tenant_id'), 'tenant-other'), (('scope', 'policy_version'), True),
])
def test_resealed_document_edits_never_render_or_gain_authority(baseline, path, value):
    p, f, g, m, k, _ = baseline
    d = build(baseline)
    doc = d.document
    node = doc
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    doc['draft_ref'] = 'rd-' + digest({key: v for key, v in doc.items() if key != 'draft_ref'})
    with pytest.raises(ReportError, match='REPORT_REPLAY_MISMATCH'):
        render(doc, d.html_bytes, p, f, g, m, expected_draft_ref=doc['draft_ref'], **k)


@pytest.mark.parametrize('addition', ['share_grant', 'review_decision', 'approved_by'])
def test_forged_review_or_share_grant_is_not_a_report_input(baseline, addition):
    p, f, g, m, k, _ = baseline
    d = build(baseline)
    doc = d.document
    doc[addition] = {'status': 'APPROVED', 'owner': 'forged'}
    with pytest.raises(ReportError):
        ReportDraft.load(doc, d.html_bytes, p, f, g, m, expected_draft_ref=d.ref, **k)
    with pytest.raises(ReportError):
        build_draft(p, f, g, {**m, addition: True}, **k)


@pytest.mark.parametrize('edit', [b'<script>window.PWNED=1</script>', b'<img src="https://trap.invalid" onerror="alert(1)">',
    b'<a href="javascript:alert(1)">share</a>', b'<img src="data:image/svg+xml,evil">', b'changed layout'])
def test_edited_output_bytes_fail_even_with_recomputed_html_hash(baseline, edit):
    p, f, g, m, k, _ = baseline
    d = build(baseline)
    html = d.html_bytes + edit
    doc = d.document
    doc['html_sha256'] = hashlib.sha256(html).hexdigest()
    doc['draft_ref'] = 'rd-' + digest({key: v for key, v in doc.items() if key != 'draft_ref'})
    with pytest.raises(ReportError):
        ReportDraft.load(doc, html, p, f, g, m, expected_draft_ref=doc['draft_ref'], **k)


@pytest.mark.parametrize('text', ['Google rank is first.', 'We are a legally registered certified factory.',
    'This contact form is deliverable.', 'Conversion is 30%; lost sales are $100000.',
    '<script>window.PWNED=1</script>', '<img src="https://trap.invalid/pixel" onerror="window.PWNED=1">',
    'See javascript:alert(1)', 'data:text/html,<script>alert(1)</script>'])
def test_valid_source_ids_and_human_guard_are_not_unrestricted_report_copy(baseline, text):
    p, f, oldg, m, oldk, _ = baseline
    g, k = deepcopy(oldg), deepcopy(oldk)
    target = g[1]
    target['interpretation']['hypotheses'][0] = text
    target['bindings'][0]['text'] = text
    repin_guards(p, f, g, k)
    assert g[1]['guard']['claims'][0]['status'] == 'HUMAN_REVIEW_REQUIRED'
    with pytest.raises(ReportError, match='REPORT_UNSUPPORTED_PROSE'):
        build_draft(p, f, g, m, **k)


@pytest.mark.parametrize('field', ['expected_pack_ref', 'expected_execution_ref', 'expected_package_ref',
    'expected_builder_version', 'expected_evaluator_version', 'expected_guard_version',
    'expected_reporting_version', 'expected_renderer_version', 'expected_metadata_sha256',
    'tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_caller_held_scope_versions_and_hashes_fail_closed(baseline, field):
    p, f, g, m, original, _ = baseline
    k = deepcopy(original)
    if field in k:
        k[field] += 'x'
    else:
        k['expected_scope'][field] = str(k['expected_scope'][field]) + 'x'
    with pytest.raises(ReportError):
        build_draft(p, f, g, m, **k)


@pytest.mark.parametrize('mode', [200, 410, 403])
def test_swapped_capture_cannot_contribute_facts_or_guards(baseline, mode):
    p, f, g, m, k, _ = baseline
    op, of, og, om, ok, _ = load_case(mode)
    assert p.ref != op.ref
    with pytest.raises(ReportError):
        build_draft(op, f, g, m, **k)
    with pytest.raises(ReportError):
        build_draft(p, f, og, m, **k)
    with pytest.raises(ReportError):
        build_draft(p, of, g, m, **k)


def test_guard_corruption_and_duplicate_envelopes_fail(baseline):
    p, f, original, m, k, _ = baseline
    g = deepcopy(original)
    g[0]['guard']['claims'][0]['status'] = 'HUMAN_REVIEW_REQUIRED'
    with pytest.raises(ReportError):
        build_draft(p, f, g, m, **k)
    with pytest.raises(ReportError):
        build_draft(p, f, original * 2, m,
                    **{**k, 'expected_guard_refs': k['expected_guard_refs'] * 2})


def test_guard_not_run_and_provider_metadata_never_become_a_report(baseline):
    p, f, original, m, oldk, _ = baseline
    g, k = deepcopy(original), deepcopy(oldk)
    g[0]['interpretation']['model_id'] = 'unreviewed-provider'
    repin_guards(p, f, g, k)
    with pytest.raises(ReportError, match='REPORT_SYNTHETIC_MODEL_MODE'):
        build_draft(p, f, g, m, **k)
    g = deepcopy(original)
    g[0]['interpretation']['status'] = 'REJECTED'
    repin_guards(p, f, g, k)
    with pytest.raises(ReportError):
        build_draft(p, f, g, m, **k)


def test_corrupt_source_bytes_and_unknown_promoted_to_fail_are_rejected(baseline):
    p, f, g, m, k, _ = baseline
    objects = dict(p.objects)
    key = next(iter(objects))
    objects[key] += b'forged'
    with pytest.raises(ReportError):
        build_draft(EvidencePack(p._payload, tuple(sorted(objects.items()))), f, g, m, **k)
    doc = f.document
    next(i for i in doc['items'] if i['outcome'] == 'UNKNOWN')['outcome'] = 'FAIL_WITH_EVIDENCE'
    with pytest.raises(ReportError):
        build_draft(p, FindingPackage(json.dumps(doc).encode()), g, m, **k)


def test_metadata_duplicate_and_excess_selections_are_rejected(baseline):
    p, f, g, old, k, _ = baseline
    finding = build(baseline).document['issues'][0]['finding']['finding_id']
    for selection in ([finding, finding], [finding] * 4, ['invented-finding'], []):
        m = {**old, 'finding_selection': selection}
        with pytest.raises(ReportError):
            build_draft(p, f, g, m, **{**k, 'expected_metadata_sha256': digest(m)})


def test_report_replay_returns_detached_immutable_content(baseline):
    p, f, g, m, k, _ = baseline
    d = build(baseline)
    doc = d.document
    doc['approval_status'] = 'APPROVED'
    assert d.document['approval_status'] == 'NOT_APPROVED'
    assert render(d.document, d.html_bytes, p, f, g, m, expected_draft_ref=d.ref, **k) == d.html_bytes


def test_bidi_and_oversized_inputs_fail_without_reflecting_text(baseline):
    p, f, oldg, m, k, _ = baseline
    for text in ('\u202eprivate-marker', 'private-marker' * 700000, '\ud800'):
        g = deepcopy(oldg)
        g[0]['bindings'][0]['text'] = text
        with pytest.raises(ReportError) as exc:
            build_draft(p, f, g, m, **k)
        assert 'private-marker' not in str(exc.value)


def test_multi_target_evidence_selects_at_most_three_without_padding():
    p, f, g, m, k = inputs(404, use_accepted=False, contacts=4)
    d = build_draft(p, f, g, m, **k)
    assert len(d.document['issues']) == 3 and d.document['omitted_eligible_issues'] == 1
    assert len({i['target_response']['url'] for i in d.document['issues']}) == 3


def test_repeated_links_to_one_endpoint_remain_one_issue():
    p, f, g, m, k = inputs(404, use_accepted=False, product=PRODUCT.replace('LINKS', 'LINKSLINKS'))
    failures = [i for i in f.document['items'] if i['outcome'] == 'FAIL_WITH_EVIDENCE']
    assert len(failures) == 2
    d = build_draft(p, f, g, m, **k)
    assert len(d.document['issues']) == 1
    m = {**m, 'finding_selection': [i['finding']['finding_id'] for i in failures]}
    with pytest.raises(ReportError, match='REPORT_DUPLICATE_ISSUE'):
        build_draft(p, f, g, m, **{**k, 'expected_metadata_sha256': digest(m)})


def test_source_xss_is_escaped_as_source_data():
    product = PRODUCT.replace('HM-40 linear actuator component',
        '&lt;img src=&quot;https://trap.invalid/pixel&quot; onerror=&quot;window.PWNED=1&quot;&gt;')
    p, f, g, m, k = inputs(404, use_accepted=False, product=product)
    d = build_draft(p, f, g, m, **k)
    html = d.html_bytes.decode()
    assert '&lt;img' in html and 'trap.invalid' in html
    parser = Structure()
    parser.feed(html)
    assert 'img' not in parser.tags and not parser.handlers and not parser.assets


def test_bidi_from_decoded_source_is_not_displayed():
    product = PRODUCT.replace('HM-40 linear actuator component', 'Part &#x202e; misleading')
    p, f, g, m, k = inputs(404, use_accepted=False, product=product)
    with pytest.raises(ReportError, match='REPORT_DISPLAY_TEXT'):
        build_draft(p, f, g, m, **k)


def test_version_two_changes_hash_without_overwriting_version_one(baseline):
    p, f, g, m, k, _ = baseline
    first = build(baseline)
    second_meta = {**m, 'version': 2, 'created_at': '2026-11-12T03:00:00Z'}
    second_pins = {**k, 'expected_metadata_sha256': digest(second_meta)}
    second = build_draft(p, f, g, second_meta, **second_pins)
    assert first.ref != second.ref and first.document['html_sha256'] != second.document['html_sha256']
    assert first.document['native_report_version']['version'] == 1
    assert second.document['native_report_version']['version'] == 2
    assert ReportDraft.load(first.document, first.html_bytes, p, f, g, m,
                             expected_draft_ref=first.ref, **k).ref == first.ref
    with pytest.raises(ReportError):
        ReportDraft.load(first.document, first.html_bytes, p, f, g, second_meta,
                         expected_draft_ref=first.ref, **second_pins)


def test_actual_active_tags_in_captured_page_never_enter_the_report_dom():
    product = PRODUCT.replace('LINKS', '<script>window.PWNED=1</script>'
        '<a href="/contact" onclick="window.PWNED=1">Contact</a>'
        '<img src="https://trap.invalid/pixel" onerror="window.PWNED=1">')
    p, f, g, m, k = inputs(404, use_accepted=False, product=product)
    d = build_draft(p, f, g, m, **k)
    assert len(d.document['issues']) == 1
    parser = Structure()
    parser.feed(d.html_bytes.decode())
    assert not {'script', 'img'} & set(parser.tags) and not parser.handlers and not parser.assets
    assert '&lt;a href=' in d.html_bytes.decode()
