"""Child sees only strict Reviewer/B3-witness profiles; never migration admin."""

import argparse
import json
from pathlib import Path
from apps.operator_console.b5a_http import server
from apps.operator_console.b5p0_profile import load


def main():
    parser = argparse.ArgumentParser()
    for name in ("profile", "bridge", "audit"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / ".runtime"
    paths = [Path(getattr(args, k)).resolve() for k in ("profile", "bridge", "audit")]
    assert all(p.is_relative_to(root.resolve()) for p in paths)

    def sink(event):
        with paths[2].open("ab") as f:
            f.write(json.dumps(event, separators=(",", ":")).encode() + b"\n")

    app = load(paths[0], paths[1], audit=sink)
    http = server(app)
    print(
        json.dumps({"url": app.origin + "/b5a/login", "mode": "B5P0_TEST_ONLY_REHEARSAL"}),
        flush=True,
    )
    try:
        http.serve_forever()
    finally:
        http.server_close()


if __name__ == "__main__":
    main()
