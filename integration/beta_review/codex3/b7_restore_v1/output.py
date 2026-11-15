"""Scoped test-output group access and closed, credential-free diagnostics."""
import json
import os
from pathlib import Path
import subprocess

from integration.ra4e.lab import ROOT

PRIVATE = Path(__file__).resolve().parent / '.private'
PREFIX = 'B7RV1_SAFE_FAILURE='
STAGES = {'OUTPUT_ACCESS', 'PROVISION_CONFIG', 'SPAWN_WORKER', 'WAIT_LEASE',
          'SIGKILL_WORKER', 'WAIT_COMPLETION', 'PUBLISH_RESULT'}
EXCEPTIONS = {'PermissionError', 'FileNotFoundError', 'TimeoutExpired',
              'CalledProcessError', 'AssertionError', 'OSError', 'Other'}


def prepare_output(path):
    """Accepted B4 mechanism, restricted to this package's fresh private output."""
    path = Path(path)
    assert PRIVATE.resolve().is_relative_to(ROOT.resolve())
    assert path.resolve().is_relative_to(PRIVATE.resolve()) and path.is_dir() and not path.is_symlink()
    assert not any(path.iterdir()), 'FRESH_EMPTY_OUTPUT_REQUIRED'
    info = path.stat()
    if hasattr(os, 'getuid'):
        assert info.st_uid == os.getuid(), 'OUTPUT_MUST_BE_OWNED_BY_RUNNER'
    gid = info.st_gid
    assert type(gid) is int and (gid == 0 or 1000 <= gid < 2**31)
    path.chmod(0o770)
    return ['--group-add', str(gid)]


def failure_record(stage, exc, child=None):
    assert stage in STAGES
    classes = (PermissionError, FileNotFoundError, subprocess.TimeoutExpired,
               subprocess.CalledProcessError, AssertionError, OSError)
    kind = next((cls.__name__ for cls in classes if isinstance(exc, cls)), 'Other')
    error_number = getattr(exc, 'errno', None)
    if type(error_number) is not int or not 0 <= error_number <= 4095:
        error_number = None
    return {'stage': stage, 'exception': kind, 'errno': error_number,
            'native_child_exit': child.poll() if child is not None else None}


def decode_failure(raw):
    for line in raw.splitlines():
        if not line.startswith(PREFIX.encode()):
            continue
        value = json.loads(line[len(PREFIX):])
        assert set(value) == {'stage', 'exception', 'errno', 'native_child_exit'}
        assert value['stage'] in STAGES and value['exception'] in EXCEPTIONS
        assert value['errno'] is None or (type(value['errno']) is int and 0 <= value['errno'] <= 4095)
        assert value['native_child_exit'] is None or (type(value['native_child_exit']) is int and -255 <= value['native_child_exit'] <= 255)
        return value
    return {'stage': 'UNCLASSIFIED', 'exception': 'Other', 'errno': None,
            'native_child_exit': None}
