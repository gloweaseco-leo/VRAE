"""Record separately pinned own synthetic scenarios on an isolated candidate."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

parser = argparse.ArgumentParser()
parser.add_argument('root', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.root.resolve()))
from tests.findings import test_ra2c3_independent_adversarial as qa  # noqa: E402

records = {}
for case in ('positive', 'contact_404', 'contact_410', 'contact_403', 'contact_500'):
    pack, execution = qa.site(case)
    package = qa.build(pack, execution)
    doc = package.document
    assert qa.package_load(doc, pack, execution).ref == package.ref
    row = qa.trust_row(execution)
    records[case] = dict(pack_ref=pack.ref, execution_ref=execution['execution_ref'], package_ref=package.ref,
        trust_result=row['observation']['result'],
        group_counts={k: len(v) for k, v in doc.items() if k.startswith('checked_')},
        private=doc['private'], approval_status=doc['approval_status'], shareable=doc['shareable'],
        defects=[dict(rule_id=i['rule_id'], outcome=i['outcome'], source_page=i['provenance']['source_page'],
                      target_response=i['provenance']['target_response'],
                      native_evidence_ids=i['finding']['evidence_ids'])
                 for i in doc['items'] if i['finding']['kind'] == 'OBSERVATION'])
assert records['positive']['trust_result'] == 'PASS' and not records['positive']['defects']
for case in ('contact_404', 'contact_410'):
    assert records[case]['trust_result'] == 'UNKNOWN'
    assert len(records[case]['defects']) == 1 and records[case]['defects'][0]['rule_id'] == 'CTA-02'
args.output.write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: {f: v[f] for f in ('pack_ref', 'trust_result')} for k, v in records.items()}, indent=2))
