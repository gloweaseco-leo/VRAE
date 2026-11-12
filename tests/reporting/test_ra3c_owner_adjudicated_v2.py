"""Ordinary discovery of the exact frozen 64+54 Owner-adjudicated V2 suite.

The superseded V1 source is retained for explicit historical RED replay.
This module imports original test/fixture objects; it does not wrap their oracles.
"""
import hashlib
import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT = _ROOT/'docs/03-engineering/ra3c-independent-qa/phase-c-main-integration/collection_contract.py'
assert hashlib.sha256(_CONTRACT.read_bytes().replace(b'\r\n',b'\n')).hexdigest() == \
    '6282c12175ba5dc0d6fd409994fd9f17bd59f57faae4521f037631d659b21022', 'OWNER_V2_COLLECTION_TRANSPORT_INTEGRITY'
_spec = importlib.util.spec_from_file_location('owner_ra3c_v2_collection_contract',_CONTRACT)
_contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_contract)
_suite = _contract.load_frozen_suite()

# Exact function/fixture identity, original parametrization and IDs are retained.
subject = _suite.subject
test_owner_adjudicated_business_objective = _suite.test_owner_adjudicated_business_objective
test_companion_original_invalid_request_denial = _suite.test_companion_original_invalid_request_denial


@pytest.fixture(scope='module',autouse=True)
def _actual_owner_collection_receipt(request):
    with _contract.actual_collection_receipt(request,_suite):
        yield
