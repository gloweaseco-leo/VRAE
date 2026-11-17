"""Diagnostics must never publish private log text or inspect an unsafe context."""
import json

import pytest

from .ci_build_diagnostic import FILES, diagnose


def setup(root, extra=False):
    context = root/'docs/03-engineering/ra4b-p1/.runtime/m1-build-313/build'
    context.mkdir(parents=True)
    for name, original in FILES.items():
        p = root/original
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'public-pinned-dependency')
        (context/name).write_bytes(p.read_bytes())
    if extra:
        (context/'private-profile.json').write_bytes(b'PRIVATE_BAIT')
    folder = root/'docs/03-engineering/ra4b-p1/.runtime/owner-review/m1-build-313'
    folder.mkdir(parents=True)
    (folder/'build.stdout.log').write_bytes(b'PRIVATE_BAIT_NO_RAW_PUBLICATION')
    (folder/'build.stderr.log').write_bytes(b'ERROR: failed to resolve: 429 Too Many Requests PRIVATE_BAIT')


def test_only_allowlisted_public_build_can_be_classified_without_raw_text(tmp_path):
    setup(tmp_path)
    result = diagnose('313', 'failure', tmp_path)
    assert result['context_verified'] and result['error_kinds'] == ['REGISTRY_RATE_LIMIT']
    assert 'PRIVATE_BAIT' not in json.dumps(result)
    assert not result['raw_build_log_published']


def test_private_or_modified_context_is_not_inspected(tmp_path):
    setup(tmp_path, extra=True)
    result = diagnose('313', 'failure', tmp_path)
    assert not result['context_verified'] and result['error_kinds'] == ['UNKNOWN']
    assert 'build.stderr.log' not in result


def test_success_or_invalid_scope_cannot_become_an_application_pass(tmp_path):
    assert diagnose('313', 'success', tmp_path)['error_kinds'] == ['BUILD_NOT_FAILED_NO_RUNTIME_DIAGNOSIS']
    with pytest.raises(ValueError):
        diagnose('../private', 'failure', tmp_path)
