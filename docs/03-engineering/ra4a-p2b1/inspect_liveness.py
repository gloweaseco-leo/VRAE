"""Read-only local lab liveness, never output connection passwords."""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from integration.ra4a.support import connect

with connect() as c:
    print(c.execute("SELECT datname,state,wait_event,left(query,180) FROM pg_stat_activity WHERE backend_type='client backend'").fetchall())
