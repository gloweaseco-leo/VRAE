"""Investigate actual native/PG whitespace parity; no presumed root cause."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT))
from integration.ra4a.p2b1_support import connect, migrate_p2b1

migrate_p2b1()
with connect() as c:
    rows=[]
    for point in (0x20,0x85,0xa0,0x1680,0x2000,0x2028,0x2029,0x202f,0x205f,0x3000):
        char=chr(point)
        pg=c.execute("SELECT %s ~ '[^[:space:]]'",(char,)).fetchone()[0]
        rows.append({'codepoint':hex(point),'native_str_strip_nonblank':bool(char.strip()),'pg_posix_nonblank':pg})
out=Path(__file__).resolve().parent/'actual-unicode-classification.json'
out.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows))
