"""Mandatory S2 suite; retain the original default regression inventory unchanged."""
import asyncio
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from tests.collection.test_pipeline import FixedDNS, SyntheticTransport
from tests.collection.test_security import access
from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.limits import Limits
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError, build_pack
from vrae.rules.s2 import evaluate_s2, verify_s2_projection

VERSION = 's2-projection-1.1.0'


def scope(pack):
    return {key: pack.document[key] for key in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}


def git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def fixture(*, status=200, retain=True, application=None, product=None):
    app = application if application is not None else (
        '<html><body><a href="/products/p40">泵 P40</a></body></html>')
    prod = product if product is not None else (
        '<html><body><p>P40 rated flow 12 m3/h</p>'
        '<a href="/products/v25">V25 details</a></body></html>')
    bodies = {'/': '<html><body><a href="/applications/water">Water</a></body></html>',
              '/applications/water': app, '/products/p40': prod,
              '/products/v25': '<html><body>V25</body></html>',
              '/robots.txt': 'User-agent: *\nDisallow:\n'}
    routes = {'https://example.org' + path: (
        status if path == '/products/p40' else 200,
        {'content-type': 'text/plain' if path == '/robots.txt' else 'text/html'},
        body.encode()) for path, body in bodies.items()}
    collector = Collector(SafeFetcher(FixedDNS(), SyntheticTransport(routes)))
    bundle = asyncio.run(collector.capture('run-synthetic', access(),
        limits=Limits(max_pages=5, interval_seconds=0.01), retain_raw_html=retain))
    return build_pack([bundle])


def evaluate(pack):
    return evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
                       projection_version=VERSION)


def rows(out, rule):
    return [r for r in out['static_projection']['rows'] if r['observation']['rule_id'] == rule]


def test_three_bounded_rules_and_byte_citations_replay():
    pack = fixture()
    out = evaluate(pack)
    assert out['projection_version'] == VERSION
    for rule in ('DISC-03', 'SEO-02', 'TECH-01'):
        assert any(r['observation']['result'] == 'PASS' for r in rows(out, rule))
    for row in out['static_projection']['rows']:
        for cite in row['citations']:
            raw = pack.resolve(cite['evidence_ref'], expected_pack_ref=pack.ref)['content']
            assert raw[cite['byte_start']:cite['byte_end']].decode() == cite['quote']
            assert hashlib.sha256(raw).hexdigest() == cite['content_sha256']
    verify_s2_projection(out, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
        expected_projection_ref=out['projection_ref'], expected_projection_version=VERSION)
    assert out['static_projection']['authority'] == 'READ_ONLY_CANDIDATES_NOT_FINDINGS'
    assert out['projection_ref'].startswith('s2p-')
    assert len(out['s2_capabilities']) == 16
    assert sum(r['enabled'] for r in out['baseline_execution']['executions']) == 6


@pytest.mark.parametrize('status', [403, 404, 410, 500])
def test_metadata_only_never_invents_refs_or_defect_observation(status):
    pack = fixture(status=status)
    out = evaluate(pack)
    row = next(r for r in rows(out, 'TECH-01') if r['response']['http_status'] == status)
    assert row['observation']['result'] == ('ACCESS_BLOCKED' if status == 403 else 'UNKNOWN')
    assert row['observation']['evidence_ids'] == row['citations'] == []
    assert 'evidence_ref' not in row['response']
    assert row['response']['locator'].startswith('/pages/')
    assert row['response']['source_ref'].startswith('src-')
    disc = rows(out, 'DISC-03')
    assert not any(r['observation']['result'] in ('PASS', 'FAIL_WITH_EVIDENCE') for r in disc)


@pytest.mark.parametrize('markup', [
    '<html><body><script>"<a href=\'/products/p40\'>P40</a>"</script></body></html>',
    '<html><body><template><a href="/products/p40">P40</a></template></body></html>',
    '<html><body><base href="https://other.invalid/"><a href="/products/p40">P40</a></body></html>',
    '<html><body><a href="/products/p40" href="/products/v25">P40</a></body></html>',
    '<html><body><a href="https://other.invalid/products/p40">P40</a></body></html>',
    '<html><body><a href="javascript:void(0)">P40</a></body></html>',
    '<html><body><a href="/products/p40"><span>P40</a></body></html>',
])
def test_unsupported_application_paths_never_pass(markup):
    out = evaluate(fixture(application=markup))
    assert {r['observation']['result'] for r in rows(out, 'DISC-03')} == {'UNKNOWN'}


@pytest.mark.parametrize('markup', [
    '<html><body><script>P40 full description</script></body></html>',
    '<html><body><a href="/products/v25">Details</a></body></html>',
    '<html><body><p>P40</p><a href="#">Details</a></body></html>',
    '<html><body><p hidden>P40 description</p><a href="/products/v25">Details</a></body></html>',
])
def test_product_shell_or_unsupported_href_is_unknown(markup):
    out = evaluate(fixture(product=markup))
    row = next(r for r in rows(out, 'SEO-02') if r['response']['url'].endswith('/p40'))
    assert row['observation']['result'] == 'UNKNOWN'


def test_unretained_pages_and_missing_application_scope_are_unknown():
    out = evaluate(fixture(retain=False))
    assert {r['observation']['result'] for r in out['static_projection']['rows']} == {'UNKNOWN'}
    from tests.rules.synthetic import site
    out = evaluate(site())
    assert rows(out, 'DISC-03')[0]['observation']['result'] == 'UNKNOWN'
    assert 'NOT_APPLICABLE' not in {r['observation']['result'] for r in rows(out, 'DISC-03')}


@pytest.mark.parametrize('field', ['citation', 'response', 'result', 'capability'])
def test_self_rehash_cannot_change_replayed_candidates(field):
    pack = fixture()
    out = deepcopy(evaluate(pack))
    row = next(r for r in rows(out, 'SEO-02') if r['citations'])
    if field == 'citation':
        row['citations'][0]['byte_start'] += 1
    elif field == 'response':
        row['response']['http_status'] = 404
    elif field == 'result':
        row['observation']['result'] = 'FAIL_WITH_EVIDENCE'
    else:
        out['s2_capabilities'][0]['implementation'] = 'FULLY_IMPLEMENTED'
    out['projection_ref'] = 's2p-' + document_hash({k: v for k, v in out.items() if k != 'projection_ref'})
    with pytest.raises(EvidenceError):
        verify_s2_projection(out, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
            expected_projection_ref=out['projection_ref'], expected_projection_version=VERSION)


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_id', 'policy_version'])
def test_foreign_scope_is_rejected(field):
    pack = fixture()
    bad = {**scope(pack), field: 999 if field == 'policy_version' else 'foreign'}
    with pytest.raises(EvidenceError):
        evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=bad, projection_version=VERSION)


def test_frozen_boundaries():
    for path, expected in (
        ('vrae/rules/execution.py', 'c183970fd90ec69729221a4174c38d193f4b054b'),
        ('vrae/evidence/pack.py', '8d45d5882103323e62bc4bd61a4379899e759966')):
        # The unchanged minimal HTTP image intentionally has neither Git nor history.
        assert git_blob(Path(path).read_bytes().replace(b'\r\n', b'\n')) == expected


def test_candidate_evidence_cannot_be_used_in_another_pack_or_run():
    pack = fixture()
    other = fixture(product='<html><body>Different model</body></html>')
    out = evaluate(pack)
    with pytest.raises(EvidenceError):
        verify_s2_projection(out, other, expected_pack_ref=other.ref, trusted_scope=scope(other),
            expected_projection_ref=out['projection_ref'], expected_projection_version=VERSION)
    with pytest.raises(EvidenceError):
        evaluate_s2(pack, expected_pack_ref=other.ref, trusted_scope=scope(pack), projection_version=VERSION)


def test_p1_never_enters_native_findings_or_execution():
    from vrae.findings import build_findings, FindingError
    from vrae.rules import verify_execution
    pack = fixture()
    out = evaluate(pack)
    with pytest.raises(EvidenceError):
        verify_execution(out, pack, expected_pack_ref=pack.ref, expected_evaluator_version=VERSION)
    with pytest.raises(FindingError):
        build_findings(pack, out, expected_pack_ref=pack.ref,
            expected_execution_ref=out['projection_ref'], expected_evaluator_version=VERSION,
            expected_builder_version='ra2c3-1.0.0')


def test_default_p0_version_cannot_verify_p1_and_unknown_version_is_rejected():
    pack = fixture()
    out = evaluate(pack)
    with pytest.raises(EvidenceError):
        verify_s2_projection(out, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
            expected_projection_ref=out['projection_ref'])
    with pytest.raises(EvidenceError):
        evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack), projection_version='fake')


def test_default_p0_output_bytes_equal_accepted_main(tmp_path):
    # Exact git-show bytes from accepted a5b8c30, pinned by its original Git blob.
    # This oracle works in shallow CI and in the unchanged image without .git.
    raw = (Path(__file__).parent / 'fixtures/accepted-p0-contract.txt').read_bytes()
    assert git_blob(raw) == '3df95cb5cefb1840ad3b145d1eade2d8cb4fd067'
    path = tmp_path / 'accepted_contract.py'
    path.write_bytes(raw)
    spec = importlib.util.spec_from_file_location('vrae.rules.s2._accepted_p0', path)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    pack = fixture()
    pins = {'expected_pack_ref': pack.ref, 'trusted_scope': scope(pack)}
    def encoded(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(',', ':'), allow_nan=False).encode()
    assert encoded(evaluate_s2(pack, **pins)) == encoded(original.evaluate_s2(pack, **pins))
