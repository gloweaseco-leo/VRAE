"""Freeze actual collected new node IDs and untouched accepted fixture hashes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
out=HERE/(sys.argv[1] if len(sys.argv)>1 else "FROZEN_MATRIX.json")
assert out.parent==HERE and out.suffix==".json"
assert not out.exists(), "Do not overwrite a freeze"
r=subprocess.run([sys.executable,"-m","pytest","-q","--collect-only",
                  "--confcutdir=integration/ra4a/p2b1","integration/ra4a/p2b1/cases.py","integration/ra4a/p2b1/parity_cases.py"],
                 cwd=ROOT,capture_output=True,check=True)
(HERE/(out.stem+"-collection.stdout.log")).write_bytes(r.stdout)
(HERE/(out.stem+"-collection.stderr.log")).write_bytes(r.stderr)
ids=[line.strip() for line in r.stdout.decode().splitlines() if line.startswith("integration/ra4a/p2b1/") and "::" in line]
assert len(ids)==len(set(ids)) and len(ids)>0
paths=("integration/ra4a/p2b1/cases.py","integration/ra4a/p2b1/parity_cases.py","tests/persistence/test_p2b1_contracts.py",
       "tests/reviewing/synthetic.py","integration/ra4a/p2a_support.py")
files=[{"path":p,"lf_sha256":hashlib.sha256((ROOT/p).read_bytes().replace(b"\r\n",b"\n")).hexdigest()} for p in paths]
out.write_text(json.dumps({"entry_main":"558d183624a0a36d1f4eaf9d3d75af73b9c88547",
                          "p2b1_count":len(ids),"actual_collected_ids":ids,"sources_and_accepted_fixtures":files,
                          "skip_xfail_added":False,"native_approval_authority":False},indent=2)+"\n",encoding="utf-8")
print("FROZEN_NEW_P2B1_ACTUAL_COLLECTION="+str(len(ids)))
