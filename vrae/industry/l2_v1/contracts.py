"""Offline schema resolution using original native contracts, never HTTP refs."""

from functools import lru_cache
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .pack import ROOT


@lru_cache(maxsize=1)
def validator():
    registry = Registry()
    for name in ("IndustryPack", "Observation", "Finding", "AIInterpretation"):
        doc = json.loads((ROOT / "contracts/v1" / (name + ".schema.json")).read_text(encoding="utf-8"))
        registry = registry.with_resource(doc["$id"], Resource.from_contents(doc))
    schema = json.loads((ROOT / "contracts/v1/industry/BuyerDiagnosis.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=registry)


def validate_export(document):
    validator().validate(document)
