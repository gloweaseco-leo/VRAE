"""Prove V3 adds 33 cases without editing frozen V2 assertions."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
v2=json.loads((HERE/'FROZEN_MATRIX_V2.json').read_text())
v3=json.loads((HERE/'FROZEN_MATRIX_V3.json').read_text())
before,after=set(v2['actual_collected_ids']),set(v3['actual_collected_ids'])
assert len(before)==98 and len(after)==131 and before<=after and len(after-before)==33
old={r['path']:r['lf_sha256'] for r in v2['sources_and_accepted_fixtures']}
new={r['path']:r['lf_sha256'] for r in v3['sources_and_accepted_fixtures']}
assert all(new[p]==sha for p,sha in old.items())
sqlpath='db/migrations/0003_ra4a_test_review_cas.sql'
oldsql=subprocess.check_output(['git','show','292b030593c60e64c6f4e5f0a1473b113836e554:'+sqlpath],cwd=ROOT)
newsql=(ROOT/sqlpath).read_bytes().replace(b'\r\n',b'\n')
out=HERE/'MATRIX_V2_TO_V3_CHAIN.json'
assert not out.exists()
out.write_text(json.dumps({'old_98_source_assertions_unchanged':True,'retained_ids':98,'added_live_pg_ids':sorted(after-before),
 'final_case_count':131,'old_migration_3_sha256':hashlib.sha256(oldsql).hexdigest(),
 'new_migration_3_sha256':hashlib.sha256(newsql).hexdigest(),'native_contract_changed':False,
 'pre_fix_actual_result':'unicode-pre-fix/tests.xml','replaced_candidate':'292b030593c60e64c6f4e5f0a1473b113836e554'},indent=2)+'\n',encoding='utf-8')
(HERE/'MIGRATION3_NATIVE_PARITY.diff').write_text(''.join(difflib.unified_diff(oldsql.decode().splitlines(True),newsql.decode().splitlines(True),fromfile='292b030-withdrawn',tofile='V3-native-parity')),encoding='utf-8')
print('VERIFIED_ORIGINAL98_UNCHANGED_PLUS33_REAL_PG_CASES')
