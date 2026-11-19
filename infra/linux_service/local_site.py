"""Optional owned source fixture, confined to explicitly controlled internal deployments."""

import argparse
import asyncio
import json
from pathlib import Path
import shutil
import subprocess
from integration.authorized_targets.checks.site import serve


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    args = p.parse_args()
    root = Path("/tmp/lab")
    root.mkdir(mode=0o700, exist_ok=True)
    for source, target in [("source-ca.pem", "cert.pem"), ("source-key.pem", "key.pem")]:
        shutil.copyfile("/operator/" + source, root / target)
    for address in ["93.184.216.20/32", "93.184.216.53/32"]:
        subprocess.run(["ip", "addr", "add", address, "dev", "lo"], capture_output=True)
    asyncio.run(serve(json.loads(Path(args.config).read_bytes())))


if __name__ == "__main__":
    main()
