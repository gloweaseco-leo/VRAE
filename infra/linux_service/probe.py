"""A trusted service's file-configured mTLS health check; no secret CLI values."""

import argparse
import http.client
import json
import os
from pathlib import Path
import ssl


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    path = Path(p.parse_args().config)
    st = path.stat()
    if os.name == "posix" and (st.st_uid != os.geteuid() or st.st_mode & 0o077):
        raise PermissionError("PRIVATE_CALLER_CONFIG_REQUIRED")
    cfg = json.loads(path.read_bytes())
    ctx = ssl.create_default_context(cafile=cfg["ca"])
    ctx.load_cert_chain(cfg["certificate"], cfg["key"])
    probes = [(cfg["api_port"], "/health/ready", cfg["api_bearer"], "application/json")]
    if cfg.get("review_bearer"):
        probes.append(
            (
                cfg["review_port"],
                "/v1/report-authority/health",
                cfg["review_bearer"],
                'application/vnd.vrae.report+json; profile="vrae.report-authority.v1"',
            )
        )
    results = []
    for port, route, bearer, media in probes:
        c = http.client.HTTPSConnection(cfg["host"], port, context=ctx, timeout=10)
        try:
            c.request("GET", route, headers={"Authorization": "Bearer " + bearer, "Accept": media})
            r = c.getresponse()
            value = json.loads(r.read(65537))
            results.append(
                {
                    "path": route,
                    "status": r.status,
                    "ready": r.status == 200
                    and (value.get("status") == "READY" or value.get("ready") is True),
                    "source_sha": value.get("source_sha"),
                }
            )
        finally:
            c.close()
    print(json.dumps({"checks": results}))
    if not all(x["ready"] for x in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
