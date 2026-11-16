from copy import copy, deepcopy
from dataclasses import replace
import json
import multiprocessing
import os
from pathlib import Path
import pickle

import pytest

import vrae.evidence.pack as module
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError, EvidencePack, build_pack
from tests.evidence.synthetic import http, browser


@pytest.fixture
def pack():
    return build_pack([http(), browser(observed=True)])


def spy(monkeypatch):
    calls = []
    original = module._project

    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, '_project', counted)
    return calls


def test_first_full_then_same_exact_instance_reuses_only_consistency(pack, monkeypatch):
    calls = spy(monkeypatch)
    fresh = EvidencePack(pack._payload, pack._blobs)
    fresh.verify(expected_ref=pack.ref)
    assert len(calls) == 1
    for _ in range(8):
        fresh.verify(expected_ref=pack.ref)
    assert len(calls) == 1
    assert not hasattr(fresh, '__dict__')


def test_each_wrong_ref_rejected_and_failed_proof_not_retained(pack, monkeypatch):
    calls = spy(monkeypatch)
    for _ in range(2):
        with pytest.raises(EvidenceError):
            pack.verify(expected_ref='ep-' + '0' * 64)
    pack.verify(expected_ref=pack.ref)
    assert len(calls) == 1


@pytest.mark.parametrize('factory', [copy, deepcopy, lambda p: pickle.loads(pickle.dumps(p)), replace])
def test_new_copy_pickle_replace_must_first_fully_verify(pack, monkeypatch, factory):
    calls = spy(monkeypatch)
    new = factory(pack)
    assert new is not pack
    new.verify(expected_ref=pack.ref)
    assert len(calls) == 1


def test_new_load_cannot_inherit_other_instances_proof(pack, monkeypatch):
    calls = spy(monkeypatch)
    other = EvidencePack.load(pack.document, pack.objects, expected_ref=pack.ref)
    assert len(calls) == 1
    other.verify(expected_ref=pack.ref)
    assert len(calls) == 1


def test_stolen_slot_proof_is_bound_to_owner(pack, monkeypatch):
    other = EvidencePack(pack._payload, pack._blobs)
    object.__setattr__(other, '_EvidencePack__verification', pack._EvidencePack__verification)
    calls = spy(monkeypatch)
    other.verify(expected_ref=pack.ref)
    assert len(calls) == 1


@pytest.mark.parametrize('field', ['tenant_id', 'run_id', 'policy_version'])
def test_rehashed_cross_scope_payload_never_inherits_valid_proof(pack, field):
    doc = pack.document
    doc[field] = 99 if field == 'policy_version' else 'other-scope'
    doc['pack_ref'] = 'ep-' + document_hash({k: v for k, v in doc.items() if k != 'pack_ref'})
    object.__setattr__(pack, '_payload', module._encode(doc))
    with pytest.raises(EvidenceError):
        pack.verify(expected_ref=doc['pack_ref'])


@pytest.mark.parametrize('mutation', ['corrupt', 'orphan', 'duplicate', 'mutable_outer', 'mutable_pair', 'payload_type'])
def test_corruption_type_and_structure_change_never_reuses(pack, mutation):
    blobs = list(pack._blobs)
    if mutation == 'corrupt':
        blobs[0] = (blobs[0][0], b'corrupted')
    elif mutation == 'orphan':
        blobs.append(('0' * 64, b'orphan'))
    elif mutation == 'duplicate':
        blobs.append(blobs[0])
    elif mutation == 'mutable_pair':
        blobs[0] = list(blobs[0])
    elif mutation == 'payload_type':
        object.__setattr__(pack, '_payload', bytearray(pack._payload))
    if mutation != 'payload_type':
        object.__setattr__(pack, '_blobs', blobs if mutation == 'mutable_outer' else tuple(blobs))
    with pytest.raises(EvidenceError):
        pack.verify()


@pytest.mark.parametrize('kind', ['instance', 'payload', 'outer_tuple', 'pair', 'key', 'body'])
def test_subclasses_not_cached(pack, monkeypatch, kind):
    class SubPack(EvidencePack):
        pass

    class SubBytes(bytes):
        pass

    class SubTuple(tuple):
        pass

    class SubStr(str):
        pass

    payload, blobs = pack._payload, pack._blobs
    if kind == 'payload':
        payload = SubBytes(payload)
    elif kind == 'outer_tuple':
        blobs = SubTuple(blobs)
    elif kind in ('pair', 'key', 'body'):
        key, body = blobs[0]
        pair = SubTuple((key, body)) if kind == 'pair' else (SubStr(key), body) if kind == 'key' else (key, SubBytes(body))
        blobs = (pair,) + blobs[1:]
    new = (SubPack if kind == 'instance' else EvidencePack)(payload, blobs)
    calls = spy(monkeypatch)
    new.verify(expected_ref=pack.ref)
    new.verify(expected_ref=pack.ref)
    assert len(calls) == 2


def temporary_schemas(tmp_path, monkeypatch):
    import vrae.browser.observation as observation
    import vrae.collection.contracts as contracts
    original_root = Path(module.__file__).resolve().parents[2]
    for relative in ('evidence/EvidencePack.schema.json', 'collection/CaptureManifest.schema.json', 'browser/BrowserObservation.schema.json'):
        target = tmp_path / 'contracts/v1' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((original_root / 'contracts/v1' / relative).read_bytes())
    monkeypatch.setattr(module, '__file__', str(tmp_path / 'vrae/evidence/pack.py'))
    monkeypatch.setattr(observation, '__file__', str(tmp_path / 'vrae/browser/observation.py'))
    monkeypatch.setattr(contracts, 'ROOT', tmp_path / 'contracts/v1/collection')
    return tmp_path / 'contracts/v1'


@pytest.mark.parametrize('relative', ['evidence/EvidencePack.schema.json', 'collection/CaptureManifest.schema.json', 'browser/BrowserObservation.schema.json'])
def test_schema_content_change_same_size_same_mtime_invalidates(pack, tmp_path, monkeypatch, relative):
    root = temporary_schemas(tmp_path, monkeypatch)
    pack.verify(expected_ref=pack.ref)
    target = root / relative
    raw = target.read_bytes()
    changed = raw.replace(b'"type": "object"', b'"type": "string"', 1)
    assert len(raw) == len(changed) and changed != raw
    st = target.stat()
    target.write_bytes(changed)
    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))
    with pytest.raises(EvidenceError):
        pack.verify(expected_ref=pack.ref)
    target.write_bytes(raw)
    calls = spy(monkeypatch)
    pack.verify(expected_ref=pack.ref)
    assert len(calls) == 1


@pytest.mark.parametrize('reference', ['$ref', '$dynamicRef', '$recursiveRef'])
def test_unused_external_schema_graph_not_cached(pack, tmp_path, monkeypatch, reference):
    root = temporary_schemas(tmp_path, monkeypatch)
    target = root / 'evidence/EvidencePack.schema.json'
    schema = json.loads(target.read_bytes())
    schema.setdefault('$defs', {})['unreferenced'] = {reference: 'https://unresolved.invalid/schema'}
    target.write_text(json.dumps(schema), encoding='utf-8')
    calls = spy(monkeypatch)
    pack.verify(expected_ref=pack.ref)
    pack.verify(expected_ref=pack.ref)
    assert len(calls) == 2


def _process_child(pack, conn):
    import vrae.evidence.pack as implementation
    original = implementation._project
    calls = []

    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    implementation._project = counted
    pack.verify(expected_ref=pack.ref)
    conn.send({'project_calls': len(calls), 'pid': os.getpid()})
    conn.close()


def test_fork_or_spawn_process_cannot_reuse_parent_proof(pack):
    method = 'fork' if 'fork' in multiprocessing.get_all_start_methods() else 'spawn'
    context = multiprocessing.get_context(method)
    parent, child = context.Pipe()
    process = context.Process(target=_process_child, args=(pack, child))
    process.start()
    child.close()
    try:
        assert parent.poll(45)
        result = parent.recv()
        assert result['project_calls'] == 1 and result['pid'] != os.getpid()
        process.join(10)
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(10)
        parent.close()


def test_detached_mutable_views_do_not_mutate_verified_instance(pack, monkeypatch):
    doc = pack.document
    doc['evidence'].clear()
    calls = spy(monkeypatch)
    pack.verify(expected_ref=pack.ref)
    assert not calls and pack.document['evidence']


def test_process_marker_change_forces_full_verification(pack, monkeypatch):
    pid = os.getpid()
    monkeypatch.setattr(module.os, 'getpid', lambda: pid + 1)
    calls = spy(monkeypatch)
    pack.verify(expected_ref=pack.ref)
    assert len(calls) == 1


def test_equal_bytes_replacement_is_a_new_verification_boundary(pack, monkeypatch):
    payload = memoryview(pack._payload).tobytes()
    assert payload == pack._payload and payload is not pack._payload
    object.__setattr__(pack, '_payload', payload)
    calls = spy(monkeypatch)
    pack.verify(expected_ref=pack.ref)
    assert len(calls) == 1


def test_no_constructor_or_state_injection_of_cache(pack):
    with pytest.raises(TypeError):
        EvidencePack(pack._payload, pack._blobs, _EvidencePack__verification=True)
    new = EvidencePack.__new__(EvidencePack)
    new.__setstate__((pack._payload, pack._blobs))
    assert new._EvidencePack__verification is None


def test_expected_ref_subclass_cannot_supply_forged_equality(pack):
    class Forged(str):
        def __eq__(self, other):
            return True

    with pytest.raises(EvidenceError):
        pack.verify(expected_ref=Forged('wrong-ref'))
