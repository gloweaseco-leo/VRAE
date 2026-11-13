"""Finish only startup-05's label-verified cleanup; never start a resource."""
import json
from pathlib import Path

from integration.ra4c3.lab import cleanup_owned

HERE = Path(__file__).resolve().parent
receipt = HERE / 'evidence/startup-05-auto-cleanup/ownership.json'
cleanup_owned(json.loads(receipt.read_text(encoding='utf-8')),
              HERE / 'evidence/startup-05-auto-cleanup/recovered-cleanup')
