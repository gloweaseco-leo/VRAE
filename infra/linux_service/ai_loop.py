"""Original durable discovery -> one trusted Qwen4 adapter; never retry dispatch."""

import argparse
import time
from contracts.l2_launch.contract import canonical
from integration.authorized_targets.store import config, connect
from integration.qwen_provider.committed import Adapter, current_input, execute
from integration.qwen_provider.postcommit import InputPins, replay_input
from vrae.l2.native import NativeTask
from vrae.industry.l2_v1.pack import load_s2
from vrae.rules.s2 import IndustryPins, evaluate_s2
from vrae.reporting.s2_candidate import BuyerCandidatePins, ObservationPin


def adapter(binding, job, selections, *, real_qwen=False):
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
        # Generic bounded selection from recorded projection, never a demo
        # tenant/model/URL fallback or a model-created product fact.
        rows = projection['industrial_projection']['rows']
        first = next((r for r in rows if type(r.get('model')) is str
                      and r['model'] not in ('UNKNOWN', 'UNSPECIFIED') and r.get('source_pages')), None)
        if first is None:
            # Website evidence remains analyzable without a declared product.
            result = Adapter(binding, job, projection=projection, buyer_pins=None)
            if real_qwen:
                from infra.linux_service.qwen_runtime import provider_for
                from vrae.intelligence.qwen import QwenError
                try:
                    result._provider = provider_for(binding, job, held)
                except QwenError as error:
                    result._model_setup_code = str(error)
            return result
        snapshot = first['source_pages'][0]['snapshot_ref']
        selected = {'model': first['model'], 'rules': sorted({
            r['observation']['rule_id'] for r in rows if r['model'] == first['model']
            and any(p['snapshot_ref'] == snapshot for p in r['source_pages'])})[:2],
            'subject_url': next(s['url'] for s in pack.document['snapshots'] if s['snapshot_ref'] == snapshot)}
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
    result = Adapter(binding, job, projection=projection, buyer_pins=buyer)
    if real_qwen:
        from infra.linux_service.qwen_runtime import provider_for
        from vrae.intelligence.qwen import QwenError
        try:
            result._provider = provider_for(binding, job, held)
        except QwenError as error:
            result._model_setup_code = str(error)
    return result


def process_job(binding, job, selections, *, real_qwen=False):
    selected = adapter(binding, job, selections, real_qwen=real_qwen)
    def invoke(request):
        if selected is None:
            return {'state': 'AI_UNAVAILABLE', 'reason': 'BUYER_SELECTION_REQUIRED',
                    'claims': [], 'usage': None, 'real_model_calls': 0}
        result = selected(request)
        if getattr(selected, '_model_setup_code', None):
            result['reason'] = selected._model_setup_code
        result['model_runtime'] = {'mode': 'REAL_QWEN' if real_qwen else 'NO_MODEL',
                                  'configured': selected._provider is not None,
                                  'actual_invoice': 'UNKNOWN'}
        if selected._provider is not None:
            from datetime import datetime, UTC
            try:
                result['model_runtime']['budget'] = selected._provider.quota.daily_status(datetime.now(UTC))
            except Exception:
                result.update(state='AI_UNAVAILABLE', reason='QUOTA_STATUS_UNAVAILABLE', claims=[])
                result['model_runtime']['budget'] = {'status': 'UNKNOWN'}
        return result
    return execute(binding, job, invoke, operation_id='service-ai-' + job)


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
                        result = process_job(binding, job, cfg.get('buyer_selection', {}),
                                             real_qwen=cfg.get('runtime_qwen') is True)
                        print(canonical({'phase': 'POST_COMMIT_RECORDED' if result['pg_receipt_status'] == 'RECORDED'
                            else 'POST_COMMIT_UNAVAILABLE', 'state': result['state'],
                            'pg_receipt_status': result['pg_receipt_status'],
                            'provider_attempts': result.get('provider_attempts', 0),
                            'model': 'qwen4-max', 'actual_invoice': 'UNKNOWN'}).decode(), flush=True)
                    except Exception:
                        # Authority loss cannot be turned into an AI receipt.
                        print('{"phase":"POST_COMMIT_DENIED","model_dispatch":0}', flush=True)
            except Exception:
                print('{"phase":"AI_DEPENDENCY_UNAVAILABLE","model_dispatch":0}', flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
