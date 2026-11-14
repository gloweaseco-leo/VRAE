import os
import uuid
import pytest
from .support import Runtime
from .lab import Lab
from integration.b3_p0.support import bootstrap


@pytest.fixture(scope="session")
def shared():
    value = Lab(os.environ.get("B5P0_LABEL", "dev") + "-security-" + uuid.uuid4().hex[:8])
    try:
        value.start()
        bootstrap(value)
        yield value
    finally:
        value.stop()


@pytest.fixture
def runtime(shared, request):
    r = Runtime("case-" + uuid.uuid4().hex[:10], shared=shared)
    r.case_id = request.node.name
    try:
        r.start()
        yield r
    finally:
        r.stop()
