"""Narrow control pipe to ORIGINAL current PG readers/receipt function."""
import json
from pathlib import Path
import sys
sys.path.insert(0,'/work')
request=json.load(sys.stdin)
ready=json.loads(Path('/evidence/live-ready.json').read_bytes())
b,job=ready['binding'],ready['job']
from integration.authorized_targets.current_authority import CurrentCommittedAuthority
from integration.authorized_targets.delivery import committed_input
from integration.authorized_targets.store import connect
from psycopg.types.json import Jsonb
action=request['action']
if action=='identity':
    result={'tenant_id':b['tenant_id'],'job_id':job}
elif action=='snapshot':
    result=CurrentCommittedAuthority(b,job).check_current()
elif action=='base':
    with committed_input(b,job,purpose='POST_COMMIT_AI_INPUT') as value:
        result=value
elif action=='record':
    authority=CurrentCommittedAuthority(b,job)
    authority.check_current()
    receipt=request['receipt']
    with connect(b) as c,c.transaction():
        c.execute('SELECT target_v1.ai_record(%s,%s,%s,%s)',
                  (b['tenant_id'],job,receipt['operation_id'],Jsonb(receipt)))
    result={'recorded':True}
elif action=='done':
    Path('/evidence/live-done.json').write_text('{}')
    result={'resumed':True}
else:
    raise ValueError('NARROW_ACTION_REQUIRED')
print(json.dumps(result,sort_keys=True,separators=(',',':')))
