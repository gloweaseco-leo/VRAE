"""Rerun immutable V1 with new externally held versions; never calls V1 GREEN."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ra3c_legacy_v1_native_transport',HERE.parent/'phase-b-native-v1/adapter.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


class LegacyAdapter(legacy.Adapter):
    def __init__(self,reporting):
        self.production_module = reporting
        self.rejection_types = (reporting.ReportError,)
        self.origins = legacy.Origins(deepcopy(legacy.shapes.JSON_ORIGINS))
        self.digest_recipe = deepcopy(legacy.shapes.DIGEST_RECIPE)
        self.requests = json.loads((HERE/'fixtures/candidate-binding.json').read_text(encoding='utf-8'))['requests']
        self.held_requests = {}


def bind(reporting):
    return LegacyAdapter(reporting)
