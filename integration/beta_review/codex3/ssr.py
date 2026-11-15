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
    p.add_argument("--bridge")
    p.add_argument("--audit")
    p.add_argument("--deps-ready")
    args = p.parse_args()
    root = Path(__file__).resolve().parent / ".private"
    profile, ready = Path(args.profile).resolve(), Path(args.ready).resolve()
    assert profile.is_relative_to(root.resolve()) and ready.is_relative_to(root.resolve())
    if args.bridge:
        from apps.operator_console.b5p0_profile import load
        bridge, audit = Path(args.bridge).resolve(), Path(args.audit).resolve()
        assert bridge.is_relative_to(root.resolve()) and audit.is_relative_to(root.resolve())
        def sink(event):
            with audit.open("ab") as stream:
                stream.write(json.dumps(event).encode()+b"\n")
        # Passive fatal capture only; no scheduled sampler or authorization decision.
        import faulthandler
        stacks = audit.with_suffix(".stacks.private.log").open("ab")
        faulthandler.enable(file=stacks)
        faulthandler.cancel_dump_traceback_later()
        from .native_observation import record,identity
        record(profile.parent,"SSR_BOOT",**identity())
        deps = Path(args.deps_ready).resolve()
        assert deps.is_relative_to(root.resolve())
        import psycopg  # noqa: F401 -- initialize the locked driver before HTTP
        pending = deps.with_suffix(".tmp")
        pending.write_text(json.dumps({"driver_ready": True}))
        pending.replace(deps)
        app = load(profile, bridge, audit=sink)
    else:
        app = ProvisionedApplication(profile)
    http = server(app)
    ready.write_text(json.dumps({"origin": app.origin}))
    if args.bridge:
        record(profile.parent,"SSR_READY",**identity())
    try:
        http.serve_forever()
    finally:
        http.server_close()

if __name__ == "__main__":
    main()
