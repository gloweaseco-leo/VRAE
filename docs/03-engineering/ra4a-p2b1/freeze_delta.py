"""Preserve development V1 and stronger V2 without rewriting test history."""
import difflib
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
v1=json.loads((HERE/"FROZEN_MATRIX.json").read_text())
v2=json.loads((HERE/"FROZEN_MATRIX_V2.json").read_text())
assert v1["actual_collected_ids"]==v2["actual_collected_ids"]
p="integration/ra4a/p2b1/cases.py"
old=(HERE/"dev-p2b1-05/sources"/p).read_bytes().replace(b"\r\n",b"\n")
new=(ROOT/p).read_bytes().replace(b"\r\n",b"\n")
for version,raw in ((v1,old),(v2,new)):
    assert next(r["lf_sha256"] for r in version["sources_and_accepted_fixtures"] if r["path"]==p)==hashlib.sha256(raw).hexdigest()
(HERE/"MATRIX_V1_TO_V2.diff").write_text("".join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile="development-V1",tofile="frozen-V2")),encoding="utf-8")
(HERE/"MATRIX_VERSION_CHAIN.json").write_text(json.dumps({
 "same_98_node_ids":True,"assertions_removed":False,
 "reason":"Strengthen B01 exact one finding, B24 all three cases now execute real SQL refusal as well as production denial, B26 assert deferred commit error context.",
 "v1_tests_sha256":hashlib.sha256(old).hexdigest(),"v2_tests_sha256":hashlib.sha256(new).hexdigest(),
 "v1_source_snapshot":"dev-p2b1-05/sources/"+p,
 "v1_actual_result":"dev-p2b1-05/p2b1/tests.xml",
 "v1_live_database_cases":95,"v1_pure_integration_cases":3,"v2_live_database_cases":98,
 "final_gate":"FROZEN_MATRIX_V2.json",
 "shared_collection_log":"frozen-collection.stdout.log was regenerated for V2; it is not claimed as original V1 raw collection evidence. V1 executed source and complete JUnit remain preserved."
},indent=2)+"\n",encoding="utf-8")
print("VERIFIED_SAME_IDS_STRONGER_REAL_DB_V2")
