import os
import uuid
import pytest
from .lab import Lab
from .support import Runtime


@pytest.fixture(scope="session")
def owner():
    lab=Lab(os.environ.get("B6_LABEL","dev")+"-pg-"+uuid.uuid4().hex[:8])
    try:
        lab.start()
        yield lab
    finally:
        lab.stop()


@pytest.fixture
def runtime(owner,request):
    value=Runtime(owner,request.node.name)
    try:
        value.start()
        yield value
    finally:
        value.stop()
