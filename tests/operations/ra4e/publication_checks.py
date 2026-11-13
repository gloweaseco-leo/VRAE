"""Explicit B7-only checks; run after its isolated PG dependencies are installed."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from integration.ra4e.lab import RecoveryDenied
from integration.ra4e.run import artifact, public_junit


def fixture(tmp_path):
    output, private = tmp_path / 'output', tmp_path / 'private'
    output.mkdir()
    private.mkdir()
    (private / 'scan-credentials.json').write_text(json.dumps(['private-sentinel-value']))
    return output, private


def test_junit_tracebacks_and_streams_never_exported():
    raw = b'<testsuites><testsuite hostname="private-host"><testcase name="test_denial"><error message="private-sentinel-value">private-sentinel-value</error><system-out>private-sentinel-value</system-out></testcase></testsuite></testsuites>'
    safe = public_junit(raw)
    assert b'private-sentinel-value' not in safe and b'private-host' not in safe
    case = ET.fromstring(safe).find('testcase')
    assert case.attrib['name'] == 'test_denial' and case.find('error') is not None


def test_unknown_files_catalog_and_raw_dumps_are_excluded(tmp_path):
    output, private = fixture(tmp_path)
    for name in ['source-catalog.json', 'raw.dump', 'stdout.log', 'unknown.json']:
        (output / name).write_text('private-sentinel-value')
    (output / 'receipt.json').write_text('{"status":"RED_OR_INCOMPLETE"}')
    destination = artifact(output, private)
    assert {p.name for p in destination.iterdir()} == {'receipt.json', 'classification.json', 'publication.json'}
    assert json.loads((destination / 'publication.json').read_text())['publication_allowed']


def test_credential_in_recognized_file_denies_publication(tmp_path):
    output, private = fixture(tmp_path)
    (output / 'receipt.json').write_text('{"status":"private-sentinel-value"}')
    with pytest.raises(RecoveryDenied, match='PUBLICATION_SECRET_OR_RAW_ARCHIVE_DENIED'):
        artifact(output, private)
    assert not json.loads((output / 'public-artifact/publication.json').read_text())['publication_allowed']


def test_missing_actual_credential_inventory_fails_closed(tmp_path):
    output, private = fixture(tmp_path)
    (private / 'scan-credentials.json').unlink()
    with pytest.raises(RecoveryDenied, match='ARTIFACT_CREDENTIAL_INVENTORY_MISSING'):
        artifact(output, private)
    assert not (output / 'public-artifact/publication.json').exists()


def test_token_pattern_denies_even_without_exact_credential_match(tmp_path):
    output, private = fixture(tmp_path)
    (output / 'receipt.json').write_text(json.dumps({'status': 'ghp_' + 'x' * 36}))
    with pytest.raises(RecoveryDenied, match='PUBLICATION_SECRET_OR_RAW_ARCHIVE_DENIED'):
        artifact(output, private)


def test_source_code_cannot_add_workflow_upload_glob():
    workflow = Path('.github/workflows/ra4e-b7p0-restore.yml').read_text()
    assert 'path: docs/03-engineering/ra4e-b7p0-restore/hosted-${{ matrix.python-version }}/public-artifact/' in workflow
    assert "steps.publication.outcome == 'success'" in workflow
