import json
from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from vrae.collection.contracts import ROOT, validate_document
from vrae.domain.contracts import validate_contract
from .test_pipeline import collect


@pytest.mark.parametrize("path", sorted(ROOT.glob("*.schema.json")), ids=lambda p:p.stem)
def test_collection_schema_meta(path):
    Draft202012Validator.check_schema(json.loads(path.read_text()))


def test_manifest_compatible_with_original_snapshot_and_evidence():
    bundle, _ = collect(retain_raw_html=True)
    validate_document("CaptureManifest", bundle.manifest)
    for page in bundle.manifest["pages"]:
        validate_contract("PageSnapshot", page["snapshot"])
        validate_contract("Evidence", page["evidence"])
    for key in bundle.manifest:
        bad = deepcopy(bundle.manifest)
        del bad[key]
        with pytest.raises(ValidationError):
            validate_document("CaptureManifest", bad)


def test_error_manifest_has_no_observed_fabrication():
    bundle, _ = collect({"https://example.org/": (403, {"content-type":"text/html"}, b"Denied")})
    validate_document("CaptureManifest", bundle.manifest)
    assert bundle.manifest["pages"][0]["evidence"] is None
