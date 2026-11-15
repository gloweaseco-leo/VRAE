"""Low-UID crash with generated result and native finish still uncommitted."""

import argparse
import time
from vrae.application.ra4b import store
from vrae.application.ra4b_p2.m1.runtime import load, build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    cfg = store.load_config(parser.parse_args().config, "WORKER")
    with store.connect(cfg) as c:
        lease = store.claim(c, cfg, 30)
        output = build(load(c, cfg["tenant"], lease), lease)
        with c.transaction():
            c.execute(
                "SELECT ra4b_p2.m1_commit(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    cfg["tenant"],
                    lease[0],
                    lease[2],
                    lease[3],
                    output.source,
                    output.report,
                    output.html,
                    output.binding,
                ),
            )
            print("READY_UNCOMMITTED", flush=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
