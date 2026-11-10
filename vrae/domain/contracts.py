"""Contract loading/validation. JSON Schemas are structural authority."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2] / "contracts" / "v1"


def load_schema(name: str) -> dict[str, Any]:
    if not name.isidentifier():
        raise ValueError("Invalid schema name")
    return json.loads((ROOT / (name + ".schema.json")).read_text(encoding="utf-8"))


def validate_contract(name: str, payload: dict[str, Any]) -> None:
    Draft202012Validator(load_schema(name), format_checker=FormatChecker()).validate(payload)
