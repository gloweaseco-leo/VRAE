"""Load accepted unmodified C3 evidence with independent literal caller pins."""
import base64
import json
from pathlib import Path

from vrae.evidence import EvidencePack
from vrae.findings import FindingPackage

ROOT = Path(__file__).resolve().parents[2]
PIN = dict(expected_pack_ref='ep-0d8c47039d18a69016272c6be4749adc2730bbe20251bb1d952480b50f0bc438',
    expected_execution_ref='rx-bd53d5ac4072084fde99bb98713873936c53be40ef6e079cb37086b28c851c92',
    expected_package_ref='fp-9bb9b6e0d0ba9f7d79545c5d7a6f73f33f31f9e7303e70cb7d925db9668bbf9a',
    expected_evaluator_version='ra2b6-1.0.0', expected_builder_version='ra2c3-1.0.0')


def accepted_input():
    data = json.loads((ROOT / 'tests/findings/fixtures/ra2c3-private-packages.json').read_text(encoding='utf-8'))
    case = data['cases'][0]
    assert all(case[k] == value for k, value in PIN.items())
    pack = EvidencePack.load(case['document'], {k: base64.b64decode(v, validate=True)
        for k, v in case['objects_base64'].items()}, expected_ref=PIN['expected_pack_ref'])
    package = FindingPackage.load(case['finding_package'], pack, **PIN)
    return pack, package.document['rule_execution'], package
