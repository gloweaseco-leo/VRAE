"""Explicit host-only proof: real Git and the unchanged B5A detector.

Run this module explicitly in the bounded focused acceptance. It needs Git and
the original integration module, which the frozen isolated HTTP images do not
ship. Default discovery/46 DISC IDs stay unchanged; B5A's real CI runs its actual
detector and signed PG/HTTP/browser suites independently.
"""
import hashlib
from pathlib import Path
import subprocess

import pytest

from tests.interpretation.synthetic import proposal, source
from tests.reporting.beta_disc_report.synthetic import inputs
from tests.reporting.beta_disc_report.test_native import source_pins
from vrae.interpretation import guard as legacy
from vrae.interpretation.disc_report_v1 import GuardError, GuardResult, VERSION, validate

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / 'vrae/interpretation/guard.py'
LEGACY_BLOB = '3c068f86c5d553468e14941a0fa944d15a8240f7'
LEGACY_SHA256 = '181f948bc6cb3a3428a067f3fad9b6f5047c0d81c23d8673179b181bcde3abdf'


def test_original_legacy_bytes_mode_and_no_dynamic_dispatch():
    raw = LEGACY.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == LEGACY_SHA256
    assert raw == subprocess.check_output(['git', 'cat-file', 'blob', LEGACY_BLOB], cwd=ROOT)
    entry = subprocess.check_output(['git', 'ls-tree', 'HEAD', '--', 'vrae/interpretation/guard.py'], cwd=ROOT).decode()
    assert entry.startswith('100644 blob '+LEGACY_BLOB+'\t')
    assert legacy.VERSION == 'ra3b-1.0.0' and VERSION == 'ra3b-disc-1.0.0'
    assert not hasattr(legacy, '_DISC_GUARD_VERSION')
    assert not hasattr(legacy, '_catalog_for_version')
    held = legacy.catalog, legacy._project, legacy.validate, legacy.FIELDS.copy()
    p, f, bundles, _, pins = inputs('DISC-01', 404)
    b = bundles[0]
    assert validate(b['interpretation'], b['bindings'], p, f, **source_pins(pins)).ref == b['guard']['guard_ref']
    assert held == (legacy.catalog, legacy._project, legacy.validate, legacy.FIELDS)
    assert LEGACY.read_bytes() == raw


def test_unmodified_b5a_source_has_all_original_pins():
    from integration.ra4c_b5a.publication import source as original_detector

    result = original_detector()
    assert result['accepted_files_modified'] == []
    assert len(result['accepted_interface_pins']) == 9


def test_unmodified_b5a_detector_rejects_tampered_disposable_legacy_copy(tmp_path, monkeypatch):
    from integration.ra4c_b5a import publication

    raw = LEGACY.read_bytes()
    sandbox = tmp_path / 'isolated-source'
    hooks = tmp_path / 'empty-hooks'
    hooks.mkdir()
    subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.hooksPath='+str(hooks),
                    'clone', '--shared', '--no-checkout', str(ROOT), str(sandbox)],
                   cwd=ROOT, check=True, capture_output=True)
    subprocess.run(['git', '-C', str(sandbox), '-c', 'core.autocrlf=false',
                    '-c', 'core.hooksPath='+str(hooks), 'checkout', '--detach', publication.ENTRY],
                   check=True, capture_output=True)
    copied = sandbox / 'vrae/interpretation/guard.py'
    assert copied.resolve().is_relative_to(sandbox.resolve())
    assert not copied.samefile(LEGACY)
    with monkeypatch.context() as patch:
        # Route the unchanged detector to a complete disposable ENTRY checkout.
        # No legacy Guard module/global or real source file is changed.
        patch.setattr(publication, 'ROOT', sandbox)
        assert publication.source()['accepted_files_modified'] == []
        copied.write_bytes(copied.read_bytes()+b'\n# Deliberate isolated tamper\n')
        with pytest.raises(AssertionError, match='^ACCEPTED_SOURCE_CHANGED$'):
            publication.source()
    assert LEGACY.read_bytes() == raw
    assert publication.source()['accepted_files_modified'] == []


def test_old_and_disc_guard_results_cannot_cross_version_authority():
    p, f, bundles, _, pins = inputs('DISC-02', 410)
    b = bundles[0]
    with pytest.raises(GuardError, match='^VERSION_MISMATCH$'):
        legacy.GuardResult.load(b['guard'], b['interpretation'], b['bindings'], p, f,
                               expected_guard_ref=b['guard']['guard_ref'], **source_pins(pins))
    old_pack, old_package, old_pins = source(404)
    interpretation, bindings = proposal(old_pack, old_package, old_pins)
    old = legacy.validate(interpretation, bindings, old_pack, old_package, **old_pins)
    with pytest.raises(GuardError, match='^VERSION_MISMATCH$'):
        GuardResult.load(old.document, interpretation, bindings, old_pack, old_package,
                         expected_guard_ref=old.ref, **old_pins)
    with pytest.raises(GuardError, match='^GUARD_INTEGRITY$'):
        GuardResult.load(old.document, interpretation, bindings, old_pack, old_package,
                         expected_guard_ref=old.ref, **{**old_pins, 'expected_guard_version': VERSION})
