"""Frozen-source real PG16 run, with bounded source-free public evidence."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
PRIVATE=ROOT / "integration/b6_p0/.runtime"
PUBLIC=ROOT / "docs/03-engineering/b6-p0/evidence"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()


def source():
    paths=[]
    for directory in ("vrae/b6_p0","contracts/b6_p0","integration/b6_p0","tests/b6_p0"):
        paths.extend(p for p in (ROOT / directory).rglob("*") if p.is_file()
                     and not {".runtime","__pycache__"}.intersection(p.parts))
    workflow=ROOT / ".github/workflows/b6-p0.yml"
    if workflow.exists():
        paths.append(workflow)
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(paths)}


def main():
    label=sys.argv[1]
    assert re.fullmatch(r"[a-z0-9-]{3,28}",label)
    private=PRIVATE / (label+"-driver")
    private.mkdir(parents=True,exist_ok=False)
    public=PUBLIC / label
    public.mkdir(parents=True,exist_ok=False)
    frozen=source()
    env=dict(os.environ,PYTHONUTF8="1",PYTHONDONTWRITEBYTECODE="1",B6_LABEL=label)
    command=[sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider",
             "--tb=short","--show-capture=no","tests/b6_p0","integration/b6_p0/cases.py"]
    collection=subprocess.run(command+["--collect-only"],cwd=ROOT,env=env,capture_output=True)
    (private / "collection.log").write_bytes(collection.stdout+collection.stderr)
    matches=re.findall(rb"(\d+) tests? collected",collection.stdout)
    assert collection.returncode==0 and len(matches)==1,"B6_COLLECTION_RED"
    expected=int(matches[0])
    native=private / "native-junit.xml"
    with (private / "stdout.log").open("wb") as out,(private / "stderr.log").open("wb") as error:
        p=subprocess.run(command+["--junitxml="+str(native)],cwd=ROOT,env=env,stdout=out,stderr=error)
    nodes=list(ET.parse(native).getroot().iter("testcase")) if native.exists() else []
    red=[n.attrib["name"] for n in nodes if any(n.find(k) is not None for k in ("failure","error","skipped"))]
    observations=[json.loads(p.read_bytes()) for p in sorted(PRIVATE.glob(label+"-pg-*/case-*/observations.json"))]
    pure=[n for n in nodes if n.attrib["classname"].startswith("tests.b6_p0.")]
    summary={"python":sys.version.split()[0],"returncode":p.returncode,"expected_tests":expected,
             "tests":len(nodes),"passed":len(nodes)-len(red),"red_or_skipped":red,
             "pure_tests":len(pure),"real_pg_cases":len(observations),"source_unchanged":source()==frozen,
             "native_junit_sha256":sha(native.read_bytes()) if native.exists() else None,
             "authority":"TEST_ONLY_PRIVATE_PREVIEW","approval_proven":False,
             "shareable":False,"delivery_allowed":False,"external_visibility":False}
    (public / "source.json").write_bytes(encode(frozen))
    if (p.returncode or red or len(nodes)!=expected or len(observations)!=expected-len(pure)
            or source()!=frozen):
        summary["status"]="RED_OR_SOURCE_CHANGED"
        (public / "summary.json").write_bytes(encode(summary))
        print(json.dumps(summary),flush=True)
        raise SystemExit(1)
    assert observations and all(r["before"]==r["after"] for r in observations)
    assert len({r["case_id"] for r in observations})==len(observations)
    states=sorted({e["sqlstate"] for r in observations for e in r["sqlstates"]})
    assert "42501" in states
    cleanup=[json.loads(p.read_bytes()) for p in sorted(PRIVATE.glob(label+"-pg-*/**/cleanup.json"))]
    assert len(cleanup)==len(observations)+1
    assert all(c.get("database_dropped") or (c.get("port_closed") and all(r["absent"] for r in c["resources"])) for c in cleanup)
    safe={"native-junit.xml":native.read_bytes(),"postgres-observations.json":encode(observations),
          "cleanup.json":encode(cleanup)}
    from vrae.b6_p0 import Candidate, IntendedEnvelope
    from vrae.b6_p0.preview import PrivatePackage
    for case in ("404","200"):
        positive=[r for r in observations if r["case_id"]==f"test_actual_signed_reviewer_original_roundtrip_no_writes[{case}]"]
        assert len(positive)==1
        path=next(p.parent for p in PRIVATE.glob(label+"-pg-*/case-*/observations.json")
                  if json.loads(p.read_bytes())["case_id"]==positive[0]["case_id"])
        c=Candidate((path / "candidate.json").read_bytes())
        html=(path / "preview.html").read_bytes()
        PrivatePackage(c,html)
        envelope=IntendedEnvelope((path / "intended-envelope.json").read_bytes())
        safe["candidate-"+case+".json"]=c.payload
        safe["preview-"+case+".html"]=html
        safe["intended-envelope-"+case+".json"]=envelope.payload
    secrets=set()
    for path in PRIVATE.glob(label+"-pg-*/case-*/scan-secrets.json"):
        secrets.update(v for v in json.loads(path.read_bytes()) if v)
    for name,raw in safe.items():
        assert len(raw)<=2_000_000
        assert not any(s.encode() in raw for s in secrets),"B6_CREDENTIAL_PUBLICATION_DENIED"
        assert not re.search(rb"Bearer\s+|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.|postgresql://|BEGIN PRIVATE KEY",raw)
        if name.endswith(".html"):
            assert b"NOT APPROVED" in raw and not re.search(rb"<script|https?://|mailto:|tel:|href=|src=",raw,re.I)
        (public / name).write_bytes(raw)
    summary.update(status="ACTUAL_B6_LOCAL_GATES_PASS",business_and_catalog_unchanged=True,
                   actual_sqlstates=states,cleanup_records=len(cleanup),credential_values_scanned=len(secrets),
                   private_preview_pages=2,external_delivery_attempts_sent=0)
    (public / "summary.json").write_bytes(encode(summary))
    assert source()==frozen
    manifest={p.name:{"sha256":sha(p.read_bytes()),"bytes":p.stat().st_size} for p in sorted(public.iterdir()) if p.is_file() and p.name!="manifest.json"}
    (public / "manifest.json").write_bytes(encode(manifest))
    print(json.dumps(summary),flush=True)


if __name__=="__main__":
    main()
