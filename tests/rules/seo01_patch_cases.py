"""Patch accepts source void-element syntax; legacy hashes remain replayable."""
from copy import deepcopy

import pytest

from tests.rules.test_seo01 import seo_pack, seo, head
from vrae.rules import execute, verify_execution
from vrae.rules.seo01 import _signals
from vrae.findings import build_findings
from vrae.industry.l2_v1 import diagnose, load, verify
from vrae.interpretation import guard

HTML = head(b'<title>Export components</title><link rel="canonical" href="/"/>'
            b'<meta name="description" content="Source description"/>')


def test_patch_accepts_void_syntax_and_preserves_legacy_execution_and_guard():
    pack = seo_pack(HTML)
    old = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.0')
    new = execute(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.1')
    assert seo(old)['observations'][0]['observation']['result'] == 'UNKNOWN'
    assert seo(new)['observations'][0]['observation']['result'] == 'PASS'
    verify_execution(old, pack, expected_pack_ref=pack.ref)
    verify_execution(new, pack, expected_pack_ref=pack.ref)
    pins = dict(expected_pack_ref=pack.ref, expected_execution_ref=new['execution_ref'],
                expected_evaluator_version='ra2b6-1.0.1', expected_builder_version='ra2c3-1.0.1')
    package = build_findings(pack, new, **pins)
    gp = {**pins, 'expected_package_ref': package.ref, 'expected_guard_version': guard.VERSION,
          'expected_scope': {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}}
    facts = guard.catalog(pack, package, **gp)['facts']
    assert facts and all(f['rule_id'] == 'SEO-01' for f in facts)
    with pytest.raises(Exception):
        guard.catalog(pack, package, **{**gp, 'expected_evaluator_version': 'ra2b6-1.0.0'})
    for citation in seo(new)['observations'][0]['citations']:
        raw = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)['content'].decode()
        el = citation['element']
        assert raw[el['character_start']:el['character_end']] == el['raw_element']


@pytest.mark.parametrize('inner', [
    b'<title>A</title><meta name="description" content="D"/>',  # no canonical
    b'<title>A</title><link rel="canonical" href="https://foreign.example/"/>',
    b'<title>A</title><link rel="canonical" href="/" href="/other"/>',
    b'<title>A</title><link rel="canonical" href="/"/><link rel="canonical" href="/"/>',
    b'<title/><link rel="canonical" href="/"/>',
    b'<title>A</title></meta><link rel="canonical" href="/"/>',
    b'<base href="/"/><title>A</title><link rel="canonical" href="/"/>',
])
def test_patch_does_not_promote_missing_ambiguous_or_unsupported_evidence(inner):
    signals = _signals(head(inner).decode(), 'https://example.org/', compatible=True)
    assert signals['parse_issues'] or any(signals[k]['status'] != 'OBSERVED' for k in ('title', 'canonical'))


def test_both_diagnosis_versions_replay_and_relabeling_is_refused():
    pack = seo_pack(HTML)
    pins = dict(expected_pack_ref=pack.ref, expected_industry_ref=load(tenant_id=pack.document['tenant_id'])['industry_ref'])
    for version in ('l2-industrial-1.0.0', 'l2-industrial-1.0.1'):
        data = diagnose(pack, **pins, diagnostic_version=version)
        verify(data, pack, **pins, expected_result_ref=data['diagnosis_ref'])
        bad = deepcopy(data)
        bad['diagnostic_version'] = 'l2-industrial-1.0.1' if version.endswith('0') else 'l2-industrial-1.0.0'
        with pytest.raises(Exception):
            verify(bad, pack, **pins, expected_result_ref=data['diagnosis_ref'])


def test_live_legacy_paths_match_original_accepted_source_blobs():
    import importlib.util
    import json
    from pathlib import Path
    import sys
    root = Path(__file__).resolve().parents[2]
    hashes = json.loads((root / 'tests/interpretation/fixtures/preserved-history.json').read_text())['sha256']

    def original(path, name):
        archived = root / 'tests/interpretation/fixtures/accepted-source' / (hashes[path] + '.py')
        spec = importlib.util.spec_from_file_location(name, archived)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    old_execution = original('vrae/rules/execution.py', 'vrae.rules._accepted_execution')
    old_seo = original('vrae/rules/seo01.py', 'vrae.rules._accepted_seo')
    old_builder = original('vrae/findings/builder.py', 'vrae.findings._accepted_builder')
    for markup in (HTML, head(b'<title>A</title><link rel="canonical" href="/">'),
                   head(b'<title>A</title><meta name="description" content="D"/>')):
        pack = seo_pack(markup)
        pins = dict(expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.0')
        legacy = execute(pack, **pins)
        assert legacy == old_execution.execute(pack, **pins)
        assert _signals(markup.decode(), 'https://example.org/') == old_seo._signals(markup.decode(), 'https://example.org/')
        bp = dict(expected_pack_ref=pack.ref, expected_execution_ref=legacy['execution_ref'],
                  expected_evaluator_version='ra2b6-1.0.0', expected_builder_version='ra2c3-1.0.0')
        assert build_findings(pack, legacy, **bp).document == old_builder.build_findings(pack, legacy, **bp).document
