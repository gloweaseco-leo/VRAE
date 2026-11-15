"""One existing signed SSR server; child receives Reviewer profiles only."""

import argparse
import json
from pathlib import Path
from apps.operator_console.b5a_http import server
from apps.operator_console.b5b_profile import load


def main():
    parser = argparse.ArgumentParser()
    for key in ("profile", "bridge", "policies", "audit", "ready"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    root = (Path(__file__).resolve().parent / ".runtime").resolve()
    paths = {
        k: Path(getattr(args, k)).resolve()
        for k in ("profile", "bridge", "policies", "audit", "ready")
    }
    if not all(p.is_relative_to(root) for p in paths.values()):
        raise ValueError("B5B_OWNED_PRIVATE_PROFILE_REQUIRED")

    def audit(event):
        with paths["audit"].open("ab") as stream:
            stream.write(json.dumps(event, separators=(",", ":")).encode() + b"\n")

    app = load(paths["profile"], paths["bridge"], paths["policies"], audit=audit)
    http = server(app)
    pending = paths["ready"].with_suffix(".tmp")
    pending.write_text(json.dumps({"origin": app.origin}), encoding="utf-8")
    pending.replace(paths["ready"])
    print(
        json.dumps(
            {"url": app.origin + "/b5a/login", "mode": "B5B_EXISTING_SIGNED_SSR_NOT_WORKER_OUTPUT"}
        ),
        flush=True,
    )
    try:
        http.serve_forever()
    finally:
        http.server_close()


if __name__ == "__main__":
    main()
