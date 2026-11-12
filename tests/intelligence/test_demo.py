import asyncio
import importlib.util
import json
from pathlib import Path


def test_offline_demo_matches_sealed_source_pins_usage_and_failure_cases():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('ra3a_demo', root / 'scripts/verify_ra3a.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = asyncio.run(module.demonstrate())
    expected = json.loads((root / 'tests/intelligence/fixtures/ra3a-offline-demo.json').read_text(encoding='utf-8'))
    assert result == expected
