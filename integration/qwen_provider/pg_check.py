"""Controlled noncustomer PG drill extension. Protocol fake, never a live GO."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

from integration.authorized_targets.postcommit import run
from integration.qwen_provider.committed import Adapter, current_input, execute
from integration.qwen_provider.postcommit import InputPins, replay_input
from integration.qwen_provider.fixture import response
from contracts.l2_launch.contract import canonical
from vrae.industry.l2_v1.pack import load_s2
from vrae.intelligence.qwen import Config, Permission, Price, QwenProvider, Quota
from vrae.intelligence.qwen.provider import MODEL_SOURCE
from vrae.intelligence.qwen.testing import FakeTransport
from vrae.l2.native import NativeTask
from vrae.reporting.s2_candidate import BuyerCandidatePins, ObservationPin
from vrae.rules.s2 import IndustryPins, evaluate_s2


def build_adapter(binding, job):
    held = current_input(binding, job)
    d = held['artifact']
    pack, _ = replay_input(canonical(d), pins=InputPins(
        NativeTask(**d['native_document']['native_context']), held['commit']['artifact_sha256'],
        d['version']['content_hash'], d['display_hash']))
    scope = {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}
    config = load_s2(tenant_id=scope['tenant_id'], profile_id='industrial')
    industry = IndustryPins(config['industry_ref'], scope['tenant_id'], profile_id='industrial')
    projection = evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope,
                             projection_version='s2-projection-1.2.0', industry_pins=industry)
    # This model/path is solely the accepted controlled site, not a product default.
    rows = [next(r for r in projection['industrial_projection']['rows']
                 if r['model'] == 'TX10' and r['observation']['rule_id'] == rule)
            for rule in ('INFO-02', 'TRUST-02')]
    buyer = BuyerCandidatePins(**scope, pack_ref=pack.ref, projection_ref=projection['projection_ref'],
        projection_version='s2-projection-1.2.0', industry_pins=industry, subject_model='TX10',
        subject_snapshot_ref=next(s['snapshot_ref'] for s in pack.document['snapshots']
                                 if s['url'].endswith('/products/item')),
        observations=tuple(ObservationPin(r['observation']['observation_id'],
            r['observation']['rule_id'], r['observation']['rule_version'], r['source_version'],
            tuple(sorted(p['snapshot_ref'] for p in r['source_pages']))) for r in rows))
    adapter = Adapter(binding, job, projection=projection, buyer_pins=buyer)
    return adapter, held


def verify(binding, job, admin, check):
    adapter, held = build_adapter(binding, job)
    unavailable = run(binding, job, adapter, operation_id='c1-pg-no-go-' + str(job))
    check(unavailable['reason'] == 'PROVIDER_GO_NOT_GRANTED' and unavailable['real_model_calls'] == 0,
          'C1 original committed capture prepares S3 without fee permission or model dispatch')
    context = adapter._session.context
    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
    fake = FakeTransport(response(context))
    # This exclusive, disposable FAKE quota is unrelated to the exhausted real ledger.
    quota = Quota(Path('/tmp') / ('FAKE-c1-pg-' + str(job) + '.sqlite'), create=True)
    adapter._provider = QwenProvider(config=Config('synthetic-workspace'), quota=quota,
        permission=Permission('TEST_ONLY_CONTROLLED_PG_PROTOCOL', expiry, 6, 1000000),
        price=Price('TEST_ONLY_FICTITIOUS_PRICE', MODEL_SOURCE, 1000000, 2000000, expiry),
        key='synthetic-key-no-real-secret-0000', _transport=fake)
    original = FakeTransport.post

    async def post(self, *args):
        count = admin.execute('SELECT count(*) FROM pg_stat_activity WHERE usename=%s AND xact_start IS NOT NULL',
                              (binding['role'],)).fetchone()[0]
        check(count == 0, 'C1 provider I/O holds no original PG transaction or Worker lease')
        return await original(self, *args)

    FakeTransport.post = post
    try:
        result = run(binding, job, adapter, operation_id='c1-pg-fake-' + str(job))
        check(result['state'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW'
              and result['usage']['usage_origin'] == 'PROTOCOL_FAKE_NOT_REAL_API'
              and result['provider_operation_id'] == result['operation_id'],
              'C1 original PG COMMIT reaches original Qwen Session and bound fake usage')
        fake.response = response(context)
        fake.response['choices'][0]['message']['content'] = '{}'
        failed = run(binding, job, adapter, operation_id='c1-pg-schema-' + str(job))
        check(failed['state'] == 'AI_UNAVAILABLE' and failed['usage'] is not None
              and failed['claims'] == [], 'C1 invalid model candidate retains settled usage and deterministic fallback')
        for name, finish in (('length', 'length'), ('bad-ref', 'stop')):
            fake.response = response(context)
            fake.response['choices'][0]['finish_reason'] = finish
            if name == 'bad-ref':
                content = json.loads(fake.response['choices'][0]['message']['content'])
                content['claims'][0]['refs'] = ['cf-' + '0' * 64]
                fake.response['choices'][0]['message']['content'] = json.dumps(content)
            denied = run(binding, job, adapter, operation_id='c1-pg-' + name + '-' + str(job))
            check(denied['state'] == 'AI_UNAVAILABLE' and not denied['claims'] and denied['usage'],
                  'C1 actual PG persists unavailable ' + name + ' with durable usage')
        for item in (result, failed, denied):
            stored = admin.execute('SELECT receipt FROM target_v1.ai_receipts '
                'WHERE tenant_id=%s AND job_id=%s AND operation_id=%s',
                (binding['tenant_id'], job, item['operation_id'])).fetchone()[0]
            check(stored == item, 'C1 actual PG receipt readback equals bound Session output')
        # Withdraw only the owned synthetic grant after supplier usage is returned.
        # The original authority port, not a mocked PG read, must refuse it.
        async def withdraw(self, *args):
            reply = await post(self, *args)
            admin.execute('UPDATE target_v1.authorizations SET revoked=true '
                          'WHERE tenant_id=%s AND target_id=%s',
                          (binding['tenant_id'], held['task']['source_ref']))
            return reply
        fake.response = response(context)
        FakeTransport.post = withdraw
        try:
            refused = execute(binding, job, adapter, operation_id='c1-pg-withdraw-' + str(job))
            check(refused['state'] == 'AI_UNAVAILABLE' and not refused['claims']
                  and refused['usage'] and refused['pg_receipt_status'] == 'UNKNOWN',
                  'C1 post-dispatch actual PG withdrawal preserves usage without candidate receipt')
            check(admin.execute('SELECT count(*) FROM target_v1.ai_receipts WHERE operation_id=%s',
                                (refused['operation_id'],)).fetchone()[0] == 0,
                  'C1 failed current authority cannot insert or publish a PG candidate')
        finally:
            admin.execute('UPDATE target_v1.authorizations SET revoked=false '
                          'WHERE tenant_id=%s AND target_id=%s',
                          (binding['tenant_id'], held['task']['source_ref']))
            FakeTransport.post = post
        after = current_input(binding, job)
        check(canonical(after) == canonical(held) and not result['grants_report_access'],
              'C1 source/task/artifact/report/display hashes and unpublished authority are unchanged')
        Path('/evidence/c1-committed.json').write_text(json.dumps({
            'actual_pg_input': True, 'protocol': 'FAKE_NOT_REAL_QWEN', 'live_model_calls': 0,
            'same_input_hashes': True, 'no_pg_transaction_during_provider': True,
            'fake_candidate_state': result['state'], 'fallback_state': failed['state'],
            'usage_bound': True, 'report_access_granted': False}), encoding='utf-8')
    finally:
        FakeTransport.post = original
