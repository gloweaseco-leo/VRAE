"""Seal current lab credentials scan and verified cleanup; never serialize secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser()
    p.add_argument("output",type=Path)
    a=p.parse_args()
    out=a.output.resolve()
    assert out.is_relative_to(HERE)
    out.mkdir(parents=True,exist_ok=False)
    state_path=ROOT/"infra/ra4a/.venv/lab-state.json"
    state=json.loads(state_path.read_text())
    secrets=[state["admin_password"],*state["runtime_passwords"].values()]
    paths=[x for x in HERE.rglob("*") if x.is_file() and "__pycache__" not in x.parts]
    for path in paths:
        assert not any(s.encode() in path.read_bytes() for s in secrets), path
    result=subprocess.run([sys.executable,"infra/ra4a/lab.py","stop","--output",str(out/"teardown")],
                          cwd=ROOT,capture_output=True)
    (out/"stdout.log").write_bytes(result.stdout)
    (out/"stderr.log").write_bytes(result.stderr)
    assert result.returncode==0
    report={"actual_lab_secret_count":len(secrets),"actual_credential_scan":"NO_MATCHES",
            "scanned_files":len(paths),"cleanup_exit":result.returncode,
            "schema_sha256":state.get("p2a_schema_sha256"),
            "teardown_sha256":hashlib.sha256((out/"teardown/teardown.json").read_bytes()).hexdigest()}
    (out/"scan-and-cleanup.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))


if __name__=="__main__":
    main()
