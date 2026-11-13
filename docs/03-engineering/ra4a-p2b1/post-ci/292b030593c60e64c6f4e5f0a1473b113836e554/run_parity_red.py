"""Capture actual pre-fix SQL/native parity result on accepted source SHA."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[5]
out=ROOT/'docs/03-engineering/ra4a-p2b1/unicode-pre-fix'
out.mkdir(exist_ok=False)
for name in ('db/migrations/0003_ra4a_test_review_cas.sql','integration/ra4a/p2b1/parity_cases.py'):
    target=out/'sources'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes((ROOT/name).read_bytes())
argv=[sys.executable,'-m','pytest','-q','-x','-p','integration.ra4a.p2b1_plugin','--confcutdir=integration/ra4a/p2b1','integration/ra4a/p2b1/parity_cases.py','--junitxml='+str(out/'tests.xml')]
r=subprocess.run(argv,cwd=ROOT,env=dict(os.environ,RA4A_P2B1_EVIDENCE_DIR=str(out)),capture_output=True,check=False)
(out/'stdout.log').write_bytes(r.stdout)
(out/'stderr.log').write_bytes(r.stderr)
(out/'command.json').write_text(json.dumps({'argv':argv,'exit':r.returncode,'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()},indent=2)+'\n',encoding='utf-8')
print(r.stdout.decode(errors='replace')[-5000:])
raise SystemExit(r.returncode)
