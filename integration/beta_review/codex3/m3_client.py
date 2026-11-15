"""Fixed UID10001 original API client; never exports APP credentials."""

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from integration.ra4b import runtime_check as native
from vrae.application.ra4b import store


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("submit", "status"))
    p.add_argument("--source", choices=("404", "200"))
    p.add_argument("--key")
    p.add_argument("--request")
    a = p.parse_args()
    assert os.geteuid() == 10001
    cfg = store.load_config("/tmp/b4-app/config.json", "APP")
    # Accepted client logs metadata only in its normal OUT; this low-role helper
    # has no access to the controller evidence mount, so use its own directory.
    native.OUT = Path("/tmp/b4-app")
    if a.action == "submit":
        assert a.source and a.key and 8 <= len(a.key) <= 128
        code, body = native.request(cfg, payload={"source_ref": "accepted-" + a.source}, key=a.key)
    else:
        assert a.request and str(UUID(a.request)) == a.request
        code, body = native.request(cfg, "GET", "/v1/audit-requests/" + a.request)
    print(json.dumps({"http_status": code, "body": body, "uid": os.geteuid()}), flush=True)
    if code not in (200, 202):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
