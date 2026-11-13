"""Use original PG tests without changing their protected files or assertions."""
import os
from pathlib import Path
import sys
from integration.ra4c3.lab import ROOT, bounded, wire

wire(os.environ['RA4C3_STATE'])


def pytest_collection_modifyitems():
    # Pytest can load this namespace as ra4a.* as well as integration.ra4a.*.
    # Redirect only exact original configuration constants after collection;
    # the original fixture, tests, SQL and security assertions remain intact.
    state = bounded(os.environ['RA4C3_STATE'])
    old = ROOT / 'infra/ra4a/.venv/lab-state.json'
    for module in list(sys.modules.values()):
        file = getattr(module, '__file__', None)
        if file and Path(file).resolve().is_relative_to(ROOT / 'integration/ra4a'):
            value = getattr(module, 'STATE', None)
            if isinstance(value, Path) and value in (old, state):
                module.STATE = state
