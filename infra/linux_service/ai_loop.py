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
from vrae.reporting.s2_candidate import BuyerCandidatePins, ObservationPin


def adapter(binding, job, selections):
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
    selected = selections.get(binding["tenant_id"] + "/" + held["task"]["source_ref"])
    if selected is None:
        return None
    rows = [
        next(
            r
            for r in projection["industrial_projection"]["rows"]
            if r["model"] == selected["model"] and r["observation"]["rule_id"] == rule
        )
        for rule in selected["rules"]
    ]
    snapshot = next(
        s["snapshot_ref"] for s in pack.document["snapshots"] if s["url"] == selected["subject_url"]
    )
    buyer = BuyerCandidatePins(
        **scope,
        pack_ref=pack.ref,
        projection_ref=projection["projection_ref"],
        projection_version="s2-projection-1.2.0",
        industry_pins=industry,
        subject_model=selected["model"],
        subject_snapshot_ref=snapshot,
        observations=tuple(
            ObservationPin(
                r["observation"]["observation_id"],
                r["observation"]["rule_id"],
                r["observation"]["rule_version"],
                r["source_version"],
                tuple(sorted(p["snapshot_ref"] for p in r["source_pages"])),
            )
            for r in rows
        ),
    )
    return Adapter(binding, job, projection=projection, buyer_pins=buyer)


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
                        run(
                            binding,
                            job,
                            adapter(binding, job, cfg.get("buyer_selection", {})),
                            operation_id="service-ai-" + job,
                        )
                        print('{"phase":"POST_COMMIT_RECORDED","model_dispatch":0}', flush=True)
                    except Exception:
                        # Authority loss cannot be turned into an AI receipt.
                        print('{"phase":"POST_COMMIT_DENIED","model_dispatch":0}', flush=True)
            except Exception:
                print('{"phase":"AI_DEPENDENCY_UNAVAILABLE","model_dispatch":0}', flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
