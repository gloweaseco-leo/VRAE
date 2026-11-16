"""Exact Owner-approved real Git blobs; original publication assertions unchanged."""
import importlib
from pathlib import Path
import subprocess

import pytest

publication = importlib.import_module('integration.ra4c_b5a.publication')
REPO = Path(__file__).resolve().parents[2]
PACK = 'vrae/evidence/pack.py'
APPROVED = '8d45d5882103323e62bc4bd61a4379899e759966'
ENTRY = '6257ad3acb09d046d954301117134f6992c02d84'
PIN_PATHS = ('vrae/identity/boundary.py', 'apps/operator_console/native.py',
             'apps/operator_console/targets.py', 'apps/operator_console/service.py',
             'apps/operator_console/proposal_views.py', 'vrae/persistence/private_bytes.py',
             'db/migrations/0001_ra4a_test_only.sql', 'db/migrations/0002_ra4a_private_bytes.sql',
             'db/migrations/0003_ra4a_test_review_cas.sql')
OTHER = ('docs/unrelated.md', 'vrae/old_runtime.py', 'vrae/evidence/pack.py.extra')


def original(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


# Read exact reviewed bytes; never replace the production pin with fixture hashes.
APPROVED_BYTES = original('cat-file', 'blob', APPROVED)
OLD_BYTES = original('show', ENTRY + ':' + PACK)
DOCUMENT_BYTES = {name: original('cat-file', 'blob', blob)
                  for name, blob in publication.OWNER_DOCUMENT_BLOBS.items()}


@pytest.fixture
def history(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=tmp_path).decode().strip()

    git('init', '-q')
    git('config', 'user.name', 'TEST_ONLY')
    git('config', 'user.email', 'test-only@example.invalid')
    git('config', 'core.autocrlf', 'false')
    for name in (*PIN_PATHS, *OTHER, *DOCUMENT_BYTES, PACK):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(OLD_BYTES if name == PACK else b'original fixture bytes\n')
    git('add', '.')
    git('commit', '-qm', 'isolated original entry')
    entry = git('rev-parse', 'HEAD')
    for name, raw in DOCUMENT_BYTES.items():
        (tmp_path / name).write_bytes(raw)
    (tmp_path / PACK).write_bytes(APPROVED_BYTES)
    git('add', '.')
    git('commit', '-qm', 'exact approved pack and document blobs')
    assert git('rev-parse', 'HEAD:' + PACK) == APPROVED
    monkeypatch.setattr(publication, 'ROOT', tmp_path)
    monkeypatch.setattr(publication, 'ENTRY', entry)
    return tmp_path, git, entry


def test_exact_pack_and_five_document_blobs_allowed_and_audited(history):
    _, _, entry = history
    snapshot = publication.source()
    assert publication.OWNER_EVIDENCE_PACK_BLOB == APPROVED
    assert snapshot['accepted_entry'] == entry
    assert snapshot['accepted_files_modified'] == sorted([PACK, *DOCUMENT_BYTES])
    assert snapshot['owner_accepted_document_blobs'] == publication.OWNER_DOCUMENT_BLOBS
    assert set(snapshot['accepted_interface_pins']) == set(PIN_PATHS)


def test_same_pack_filename_different_committed_blob_rejected(history):
    root, git, _ = history
    (root / PACK).write_bytes(APPROVED_BYTES + b'\n# not approved\n')
    git('add', PACK)
    git('commit', '-qm', 'unapproved pack blob')
    with pytest.raises(AssertionError, match='OWNER_EVIDENCE_PACK_BASELINE_CHANGED'):
        publication.source()


@pytest.mark.parametrize('kind', ['unstaged', 'staged', 'deleted', 'restore_entry', 'staged_entry'])
def test_dirty_approved_pack_rejected(history, kind):
    root, git, _ = history
    if kind == 'deleted':
        (root / PACK).unlink()
    elif kind in ('restore_entry', 'staged_entry'):
        (root / PACK).write_bytes(OLD_BYTES)
    else:
        (root / PACK).write_bytes(APPROVED_BYTES + b'\n# dirty\n')
    if kind in ('staged', 'staged_entry'):
        git('add', PACK)
    with pytest.raises(AssertionError, match='OWNER_EVIDENCE_PACK_WORKTREE_CHANGED'):
        publication.source()


def test_wrong_head_cannot_hide_by_restoring_original_entry_in_worktree(history):
    root, git, _ = history
    (root / PACK).write_bytes(b'unapproved committed blob\n')
    git('add', PACK)
    git('commit', '-qm', 'unapproved pack head')
    (root / PACK).write_bytes(OLD_BYTES)
    with pytest.raises(AssertionError, match='OWNER_EVIDENCE_PACK_BASELINE_CHANGED'):
        publication.source()


def test_untouched_original_pack_needs_no_new_blob_exception(history):
    root, git, _ = history
    (root / PACK).write_bytes(OLD_BYTES)
    git('add', PACK)
    git('commit', '-qm', 'original pack bytes unchanged from entry')
    assert publication.source()['accepted_files_modified'] == sorted(DOCUMENT_BYTES)


@pytest.mark.parametrize('name', [*PIN_PATHS, *OTHER])
def test_unlisted_original_identity_sql_runtime_and_document_rejected(history, name):
    root, _, _ = history
    (root / name).write_bytes(b'not authorized\n')
    with pytest.raises(AssertionError, match='ACCEPTED_SOURCE_CHANGED'):
        publication.source()


@pytest.mark.parametrize('name', list(DOCUMENT_BYTES))
@pytest.mark.parametrize('committed', [False, True])
def test_original_five_documents_still_exact_and_clean(history, name, committed):
    root, git, _ = history
    (root / name).write_bytes(b'not approved document bytes\n')
    if committed:
        git('add', name)
        git('commit', '-qm', 'unauthorized document revision')
    reason = 'OWNER_DOCUMENT_BASELINE_CHANGED' if committed else 'OWNER_DOCUMENT_WORKTREE_CHANGED'
    with pytest.raises(AssertionError, match=reason):
        publication.source()
