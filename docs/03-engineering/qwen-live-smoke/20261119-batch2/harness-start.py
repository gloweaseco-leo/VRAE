"""Pause the original controlled drill at its C1 hook. No model or key here."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,'/work')
from integration.qwen_provider import pg_check
from integration.authorized_targets.checks.delivery_drill import Drill

migrate=Drill.migrate
def migrate_v3(self,admin):
    migrate(self,admin)
    admin.execute(Path('/work/infra/authorized_targets/003_api.sql').read_text())
Drill.migrate=migrate_v3

original = pg_check.verify
def pause(binding, job, admin, check):
    path=Path('/evidence/live-ready.json')
    path.write_text(json.dumps({'binding':binding,'job':str(job)}))
    path.chmod(0o600)
    deadline=time.monotonic()+900
    while not Path('/evidence/live-done.json').exists():
        if time.monotonic()>deadline:
            raise RuntimeError('OWNED_LIVE_HANDOFF_TIMEOUT')
        time.sleep(.2)
    original(binding,job,admin,check)
pg_check.verify=pause
from integration.authorized_targets import lab
lab.main()
