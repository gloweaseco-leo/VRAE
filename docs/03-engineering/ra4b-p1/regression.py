"""Run accepted suites unchanged with all state/output relocated to B4 paths."""

import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))


def stage(name, state, out):
    spec = importlib.util.spec_from_file_location("accepted_b2_runner", ROOT / "docs/03-engineering/ra4a-p2b2a/run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.HERE, runner.ROOT, runner.STATE = HERE, ROOT, state
    return runner.stage(name, out)


if __name__ == "__main__":
    raise SystemExit(stage(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])))
