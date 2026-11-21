"""Offline collection contracts; additive namespace leaves the RA-0 schemas intact."""
import json
from pathlib import Path
from types import MappingProxyType
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2] / "contracts/v1/collection"
NAMES = {"SafeFetchRequest", "FetchResponse", "RedirectTrace", "PageInventory",
         "CaptureManifest", "CollectionError"}
# Deployment-owned additive contracts are pinned as immutable bytes for this
# process, like validator code. They are never re-read underneath an existing
# EvidencePack proof; changing the deployment starts a new verification process.
_EXTENSIONS = MappingProxyType({name: (ROOT / 'extensions' / (name+'.schema.json')).read_bytes()
                               for name in ('HttpMeasurement', 'AdaptiveInvestigation')})


def validate_document(name: str, payload: dict):
    if name not in NAMES:
        raise ValueError("Unknown collection contract")
    json.dumps(payload, allow_nan=False)
    schema = json.loads((ROOT / (name + ".schema.json")).read_text(encoding="utf-8"))
    # The accepted base contracts remain byte-for-byte frozen. New producer
    # metadata is validated by explicit, closed additive extension contracts.
    if name == 'FetchResponse' and isinstance(payload, dict) and 'measurement' in payload:
        schema['properties']['measurement'] = json.loads(_EXTENSIONS['HttpMeasurement'])
    if name == 'CaptureManifest' and isinstance(payload, dict):
        pages = payload.get('pages')
        if isinstance(pages, list) and any('http_measurement' in page for page in pages if isinstance(page, dict)):
            schema['properties']['pages']['items']['properties']['http_measurement'] = json.loads(
                _EXTENSIONS['HttpMeasurement'])
        if 'adaptive_investigation' in payload:
            schema['properties']['adaptive_investigation'] = json.loads(
                _EXTENSIONS['AdaptiveInvestigation'])
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
