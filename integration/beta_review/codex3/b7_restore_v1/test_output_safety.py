"""Security boundaries of the new fixture output and failure-export repair."""
import json
import os
from pathlib import Path
import tempfile

import pytest

from .output import PRIVATE, PREFIX, decode_failure, failure_record, prepare_output


def test_private_exception_contents_never_enter_public_record():
    secret = 'TEST_ONLY_PRIVATE_SENTINEL_v1'
    original = PermissionError(13, secret, '/private/' + secret)
    record = failure_record('SPAWN_WORKER', original)
    raw = json.dumps(record).encode()
    assert secret.encode() not in raw and b'/private/' not in raw
    assert decode_failure(PREFIX.encode() + raw) == record
    assert record['exception'] == 'PermissionError' and record['errno'] == 13


def test_extra_diagnostic_fields_are_rejected_before_export():
    value = failure_record('SPAWN_WORKER', PermissionError(13, 'private'))
    value['password'] = 'TEST_ONLY_PRIVATE_SENTINEL_v1'
    with pytest.raises(AssertionError):
        decode_failure(PREFIX.encode() + json.dumps(value).encode())


def test_output_outside_new_private_root_keeps_original_mode(tmp_path):
    before = tmp_path.stat().st_mode
    with pytest.raises(AssertionError):
        prepare_output(tmp_path)
    assert tmp_path.stat().st_mode == before


def test_only_fresh_private_output_receives_its_own_group():
    PRIVATE.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='output-unit-', dir=PRIVATE) as name:
        path = Path(name)
        original = path.stat()
        group = prepare_output(path)
        assert group == ['--group-add', str(original.st_gid)]
        assert path.stat().st_uid == original.st_uid and path.stat().st_gid == original.st_gid
        if os.name != 'nt':
            assert path.stat().st_mode & 0o777 == 0o770


def test_existing_private_contents_are_not_given_new_group_access():
    PRIVATE.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='output-unit-', dir=PRIVATE) as name:
        path = Path(name)
        assert path.resolve().is_relative_to(PRIVATE.resolve())
        held = path / 'held-state.txt'
        held.write_text('TEST_ONLY_PRIVATE_SENTINEL_v1')
        before = path.stat().st_mode
        with pytest.raises(AssertionError):
            prepare_output(path)
        assert path.stat().st_mode == before and held.read_text() == 'TEST_ONLY_PRIVATE_SENTINEL_v1'
