"""Durable result discovery, existing C1 adapter; no provider is provisioned here."""

import argparse
import time
from contracts.l2_launch.contract import canonical
from integration.authorized_targets.store import config, connect
from integration.authorized_targets.postcommit import run
from integration.qwen_provider.committed import Adapter, current_input
from integration.qwen_provider.postcommit import InputPins, replay_input
from vrae.l2.native import NativeTask
from vrae.industry.l2_v1.pack import load_s2
from vrae.rules.s2 import IndustryPins, evaluate_s2


def adapter(binding, job):
    held = current_input(binding, job)
    d = held["artifact"]
    pack, _ = replay_input(
        canonical(d),
        pins=InputPins(
            NativeTask(**d["native_document"]["native_context"]),
            held["commit"]["artifact_sha256"],
            d["version"]["content_hash"],
            d["display_hash"],
        ),
    )
    scope = {k: pack.document[k] for k in ("tenant_id", "run_id", "policy_id", "policy_version")}
    policy = load_s2(tenant_id=scope["tenant_id"], profile_id="industrial")
    industry = IndustryPins(policy["industry_ref"], scope["tenant_id"], profile_id="industrial")
    projection = evaluate_s2(
        pack,
        expected_pack_ref=pack.ref,
        trusted_scope=scope,
        projection_version="s2-projection-1.2.0",
        industry_pins=industry,
    )
    # No selection is invented for a caller. Missing configured buyer pins is
    # an explicit unavailable S3 candidate, while deterministic evidence survives.
    return Adapter(binding, job, projection=projection, buyer_pins=None)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    cfg = config(p.parse_args().config, "APP")
    while True:
        for binding in cfg["bindings"]:
            try:
                with connect(binding) as c:
                    jobs = [
                        str(x[0])
                        for x in c.execute(
                            "SELECT * FROM target_v1.ai_pending(%s)", (binding["tenant_id"],)
                        ).fetchall()
                    ]
                for job in jobs:
                    try:
                        run(binding, job, adapter(binding, job), operation_id="service-ai-" + job)
                        print('{"phase":"POST_COMMIT_RECORDED","model_dispatch":0}', flush=True)
                    except Exception:
                        # Authority loss cannot be turned into an AI receipt.
                        print('{"phase":"POST_COMMIT_DENIED","model_dispatch":0}', flush=True)
            except Exception:
                print('{"phase":"AI_DEPENDENCY_UNAVAILABLE","model_dispatch":0}', flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
