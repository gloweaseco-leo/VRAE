"""Opt-in legacy output relocation only. No accepted assertion/SQL is replaced."""

import os
from pathlib import Path

if os.environ.get("B5A_C3_ROOT"):
    from integration.ra4c3 import lab

    original_root = lab.OWN.resolve()
    relocated = Path(os.environ["B5A_C3_ROOT"]).resolve()
    assert relocated.is_relative_to(lab.ROOT / "integration/ra4c_b5a/.runtime")
    lab.OWN = relocated
    original_bounded = lab.bounded

    def bounded(path):
        value = Path(path).resolve()
        if value.is_relative_to(original_root):
            value = relocated / value.relative_to(original_root)
        return original_bounded(value)

    lab.bounded = bounded
