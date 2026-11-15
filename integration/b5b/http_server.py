"""One existing signed SSR server; child receives Reviewer profiles only."""

import argparse
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path
from apps.operator_console.b5a_http import server
from apps.operator_console.b5b_profile import load


def main():
    parser = argparse.ArgumentParser()
    for key in ("profile", "bridge", "policies", "audit", "ready"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument('--generated-profile')
    args = parser.parse_args()
    if os.environ.get('B5B_DIAGNOSTIC_STACKS') == '1':
        def stacks():
            while True:
                time.sleep(20)
                for stack in sys._current_frames().values():
                    sys.stderr.write('PRIVATE_B5B_DIAGNOSTIC_STACK\n' + ''.join(traceback.format_stack(stack)))
                sys.stderr.flush()
        threading.Thread(target=stacks, daemon=True).start()
    root = (Path(__file__).resolve().parent / ".runtime").resolve()
    paths = {
        k: Path(getattr(args, k)).resolve()
        for k in ("profile", "bridge", "policies", "audit", "ready")
    }
    if args.generated_profile is not None:
        paths['generated_profile'] = Path(args.generated_profile).resolve()
    if not all(p.is_relative_to(root) for p in paths.values()):
        raise ValueError("B5B_OWNED_PRIVATE_PROFILE_REQUIRED")

    def audit(event):
        with paths["audit"].open("ab") as stream:
            stream.write(json.dumps(event, separators=(",", ":")).encode() + b"\n")

    app = load(paths["profile"], paths["bridge"], paths["policies"], audit=audit,
               generated_profile=paths.get('generated_profile'))
    http = server(app)
    pending = paths["ready"].with_suffix(".tmp")
    pending.write_text(json.dumps({"origin": app.origin}), encoding="utf-8")
    pending.replace(paths["ready"])
    print(
        json.dumps(
            {"url": app.origin + ('/b5a/m2/' if args.generated_profile else '/b5a/login'),
             "mode": 'M2_SAME_SIGNED_SSR_GENERATED_TASKS' if args.generated_profile else 'B5B_EXISTING_SIGNED_SSR_NOT_WORKER_OUTPUT'}
        ),
        flush=True,
    )
    try:
        http.serve_forever()
    finally:
        http.server_close()


if __name__ == "__main__":
    main()
