"""Closed evidence allowlist, native hashes and accepted Git identity checks."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from .run import ROOT, source

ENTRY="ae2505f74f7a81d7a563c05d1a811aaa526c2839"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def allowed(path):
    return bool(re.fullmatch(r"(?:contracts/b6_p0|vrae/b6_p0|integration/b6_p0|tests/b6_p0|docs/03-engineering/b6-p0)/.+|\.github/workflows/b6-p0\.yml",path))


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)


def inventory(base):
    assert re.fullmatch(r"[0-9a-f]{40}",base)
    original={}
    raw=git("ls-tree","-r","-z",base)
    for row in raw.split(b"\0"):
        if row:
            fields,path=row.split(b"\t",1)
            mode,kind,oid=fields.decode().split()
            assert kind=="blob"
            original[path.decode()]=(mode,oid)
    index={}
    for row in git("ls-files","-s","-z").split(b"\0"):
        if row:
            fields,path=row.split(b"\t",1)
            mode,oid,stage=fields.decode().split()
            assert stage=="0"
            index[path.decode()]=(mode,oid)
    assert all(index.get(path)==value for path,value in original.items())
    for row in git("diff","--name-status",base).decode().splitlines():
        status,path=row.split("\t",1)
        assert status=="A" and allowed(path),(status,path)
    others={p for p in git("ls-files","--others","--exclude-standard","-z").decode().split("\0") if p}
    assert all(allowed(p) for p in others)
    changed=sorted((set(index)-set(original)) | others)
    return {"entry_accepted_main":ENTRY,"latest_accepted_base":base,
            "accepted_files":len(original),"accepted_git_tree_listing_sha256":sha(raw),
            "accepted_blobs_and_modes_unchanged":True,"allowed_new_paths":changed}


def verify(folder):
    from vrae.b6_p0 import Candidate, IntendedEnvelope
    from vrae.b6_p0.preview import PrivatePackage
    folder=Path(folder)
    names={"summary.json","source.json","native-junit.xml","postgres-observations.json","cleanup.json","manifest.json"}
    names|={kind+"-"+case+suffix for case in ("404","200")
            for kind,suffix in (("candidate",".json"),("preview",".html"),("intended-envelope",".json"))}
    assert {p.name for p in folder.iterdir()}==names
    manifest=json.loads((folder / "manifest.json").read_bytes())
    assert set(manifest)==names-{"manifest.json"}
    for name,row in manifest.items():
        raw=(folder / name).read_bytes()
        assert row=={"sha256":sha(raw),"bytes":len(raw)}
        assert len(raw)<=2_000_000
        assert not re.search(rb"Bearer\s+|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.|postgresql://|BEGIN PRIVATE KEY",raw)
    summary=json.loads((folder / "summary.json").read_bytes())
    assert summary["returncode"]==0 and summary["tests"]==summary["passed"]==summary["expected_tests"]
    assert summary["source_unchanged"] and not summary["red_or_skipped"]
    assert json.loads((folder / "source.json").read_bytes())==source()
    native=(folder / "native-junit.xml").read_bytes()
    assert sha(native)==summary["native_junit_sha256"]
    suites=ET.fromstring(native)
    assert len(list(suites.iter("testcase")))==summary["tests"]
    assert all(n.tag in {"testsuites","testsuite","testcase"} and not (n.text or "").strip() for n in suites.iter())
    observations=json.loads((folder / "postgres-observations.json").read_bytes())
    assert len(observations)==summary["real_pg_cases"]==summary["tests"]-summary["pure_tests"]
    assert all(r["before"]==r["after"] for r in observations)
    assert len({r["case_id"] for r in observations})==len(observations)
    assert {"42501"} <= {e["sqlstate"] for r in observations for e in r["sqlstates"]}
    cleanup=json.loads((folder / "cleanup.json").read_bytes())
    assert len(cleanup)==summary["cleanup_records"]==len(observations)+1
    assert all(c.get("database_dropped") or (c.get("port_closed") and all(r["absent"] for r in c["resources"])) for c in cleanup)
    for case in ("404","200"):
        candidate=Candidate((folder / ("candidate-"+case+".json")).read_bytes())
        html=(folder / ("preview-"+case+".html")).read_bytes()
        PrivatePackage(candidate,html)
        envelope=IntendedEnvelope((folder / ("intended-envelope-"+case+".json")).read_bytes())
        assert envelope.document["candidate_digest"]==candidate.document["content_digest"]
        assert len(candidate.document["findings"])==(1 if case=="404" else 0)
        assert b"NOT APPROVED" in html and not re.search(rb"<script|https?://|mailto:|tel:|href=|src=",html,re.I)
    return {"status":"B6_ORIGINAL_PUBLICATION_BYTES_VERIFIED","files":len(names),
            "tests":summary["tests"],"real_pg_cases":len(observations),"private_previews":2}


if __name__=="__main__":
    if sys.argv[1]=="inventory":
        print(json.dumps(inventory(sys.argv[2]),sort_keys=True))
    else:
        print(json.dumps(verify(sys.argv[1]),sort_keys=True))
