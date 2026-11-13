"""Separate child process: only a restricted Reviewer profile, never lab state."""

import argparse
import json
from pathlib import Path

from apps.operator_console.b5a_http import server
from apps.operator_console.b5a_profile import ProvisionedApplication


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profile", required=True)
    p.add_argument("--audit", required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parent / ".runtime"
    profile, audit = Path(args.profile).resolve(), Path(args.audit).resolve()
    assert profile.is_relative_to(root.resolve()) and audit.is_relative_to(root.resolve())

    def sink(event):
        with audit.open("ab") as stream:
            stream.write(json.dumps(event, separators=(",", ":")).encode() + b"\n")

    app = ProvisionedApplication(profile, audit=sink)
    http = server(app)
    print(
        json.dumps(
            {"mode": "B5A_TEST_ONLY_SIGNED_REVIEWER_READ", "url": app.origin + "/b5a/login"}
        ),
        flush=True,
    )
    try:
        http.serve_forever()
    finally:
        http.server_close()


if __name__ == "__main__":
    main()
