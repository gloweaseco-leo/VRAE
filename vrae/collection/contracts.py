"""Offline collection contracts; additive namespace leaves the RA-0 schemas intact."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2] / "contracts/v1/collection"
NAMES = {"SafeFetchRequest", "FetchResponse", "RedirectTrace", "PageInventory",
         "CaptureManifest", "CollectionError"}


def validate_document(name: str, payload: dict):
    if name not in NAMES:
        raise ValueError("Unknown collection contract")
    json.dumps(payload, allow_nan=False)
    schema = json.loads((ROOT / (name + ".schema.json")).read_text(encoding="utf-8"))
    # The accepted base contracts remain byte-for-byte frozen. New producer
    # metadata is validated by explicit, closed additive extension contracts.
    if name in ('FetchResponse', 'CaptureManifest'):
        measurement = json.loads((ROOT / 'extensions/HttpMeasurement.schema.json').read_text(encoding='utf-8'))
        if name == 'FetchResponse':
            schema['properties']['measurement'] = measurement
        else:
            schema['properties']['pages']['items']['properties']['http_measurement'] = measurement
            schema['properties']['adaptive_investigation'] = json.loads(
                (ROOT / 'extensions/AdaptiveInvestigation.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
