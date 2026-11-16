"""Actual temp Git history: accepted doc revision must not unfreeze old code."""
import importlib
import subprocess

import pytest

publication = importlib.import_module("integration.ra4c_b5a.publication")

ORIGINALS = ('vrae/identity/boundary.py', 'apps/operator_console/native.py',
             'apps/operator_console/targets.py', 'apps/operator_console/service.py',
             'apps/operator_console/proposal_views.py', 'vrae/persistence/private_bytes.py',
             'db/migrations/0001_ra4a_test_only.sql', 'db/migrations/0002_ra4a_private_bytes.sql',
             'db/migrations/0003_ra4a_test_review_cas.sql', 'docs/unrelated.md')


@pytest.fixture
def history(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=tmp_path, text=True).strip()

    git('init', '-q')
    git('config', 'user.name', 'TEST_ONLY')
    git('config', 'user.email', 'test-only@example.invalid')
    doc_paths = tuple(publication.OWNER_DOCUMENT_BLOBS)
    for name in (*ORIGINALS, *doc_paths):
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('original fixture bytes\n', encoding='utf-8')
    git('add', '.')
    git('commit', '-qm', 'fixture original')
    original = git('rev-parse', 'HEAD')
    for name in doc_paths:
        (tmp_path / name).write_text('explicit owner accepted documentation fixture\n', encoding='utf-8')
    git('add', '.')
    git('commit', '-qm', 'fixture accepted docs')
    blobs = {name: git('rev-parse', 'HEAD:' + name) for name in doc_paths}
    monkeypatch.setattr(publication, 'ROOT', tmp_path)
    monkeypatch.setattr(publication, 'ENTRY', original)
    monkeypatch.setattr(publication, 'OWNER_DOCUMENT_BLOBS', blobs)
    return tmp_path, git, doc_paths


def test_exact_accepted_docs_are_audited_without_blanket_exemption(history):
    _, _, docs = history
    snapshot = publication.source()
    assert snapshot['accepted_files_modified'] == sorted(docs)
    assert snapshot['owner_accepted_document_blobs'] == publication.OWNER_DOCUMENT_BLOBS


@pytest.mark.parametrize('name', ['vrae/identity/boundary.py', 'db/migrations/0001_ra4a_test_only.sql', 'docs/unrelated.md'])
def test_old_identity_sql_and_unlisted_document_remain_frozen(history, name):
    root, _, _ = history
    (root / name).write_text('tampered fixture\n', encoding='utf-8')
    with pytest.raises(AssertionError, match='ACCEPTED_SOURCE_CHANGED'):
        publication.source()


def test_accepted_filename_with_wrong_committed_blob_is_refused(history):
    root, git, docs = history
    (root / docs[0]).write_text('different committed document\n', encoding='utf-8')
    git('add', docs[0])
    git('commit', '-qm', 'fixture unauthorized doc change')
    with pytest.raises(AssertionError, match='OWNER_DOCUMENT_BASELINE_CHANGED'):
        publication.source()


def test_accepted_head_with_dirty_worktree_is_refused(history):
    root, _, docs = history
    (root / docs[0]).write_text('uncommitted tamper\n', encoding='utf-8')
    with pytest.raises(AssertionError, match='OWNER_DOCUMENT_WORKTREE_CHANGED'):
        publication.source()
