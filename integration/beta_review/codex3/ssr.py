"""Original accepted SSR, restricted Reviewer profile only."""
import argparse
import json
from pathlib import Path
from apps.operator_console.b5a_http import server
from apps.operator_console.b5a_profile import ProvisionedApplication

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profile", required=True)
    p.add_argument("--ready", required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parent / ".private"
    profile, ready = Path(args.profile).resolve(), Path(args.ready).resolve()
    assert profile.is_relative_to(root.resolve()) and ready.is_relative_to(root.resolve())
    app = ProvisionedApplication(profile)
    http = server(app)
    ready.write_text(json.dumps({"origin": app.origin}))
    try:
        http.serve_forever()
    finally:
        http.server_close()

if __name__ == "__main__":
    main()
