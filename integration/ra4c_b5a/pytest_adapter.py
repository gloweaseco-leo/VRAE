"""Redirect only original STATE constants, not fixtures, SQL or assertions."""

import os
from pathlib import Path
import sys

from .lab import ROOT

state = Path(os.environ["B5A_LEGACY_STATE"]).resolve()
assert state.is_relative_to(ROOT / "integration/ra4c_b5a/.runtime")
for name in ("support", "p2a_support", "p2b1_support"):
    __import__("integration.ra4a." + name)


def redirect():
    for module in list(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if file and Path(file).resolve().is_relative_to(ROOT / "integration/ra4a"):
            value = getattr(module, "STATE", None)
            if isinstance(value, Path):
                module.STATE = state


redirect()


def pytest_collection_modifyitems():
    redirect()
