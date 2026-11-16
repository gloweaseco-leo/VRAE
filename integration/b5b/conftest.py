import os
import uuid
import pytest
from integration.b3_p0.support import bootstrap
from .support import Lab, Runtime


@pytest.fixture(scope="session")
def shared():
    lab = Lab(os.environ.get("B5B_LABEL", "dev") + "-pg-" + uuid.uuid4().hex[:8])
    try:
        lab.start()
        bootstrap(lab)
        yield lab
    finally:
        lab.stop()


@pytest.fixture
def runtime(shared, request):
    r = Runtime("case-" + uuid.uuid4().hex[:10], shared=shared)
    r.case_id = request.node.name
    try:
        r.start()
        yield r
    finally:
        r.stop()
