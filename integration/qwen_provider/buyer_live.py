"""Explicit one-shot controlled acceptance; original PG port and NativeTransport.

Run in a separate trusted POSIX caller, never the isolated source Worker. The
operator supplies an existing retained ledger and a separately authorized batch.
Secrets arrive on anonymous stdin, never argv/env or evidence. No retry loop.
"""
import argparse
from datetime import datetime, UTC, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys

import psycopg
from integration.qwen_provider.committed import execute, current_input
from integration.qwen_provider.pg_check import build_adapter
from vrae.intelligence.common import encode
from vrae.intelligence.qwen import Config, Permission, Price, QwenProvider, Quota
from vrae.intelligence.qwen.provider import MODEL_SOURCE
from infra.qwen_provider.transport import NativeTransport

ROOT = Path('/live')
LEDGER = Path('/retained/quota.sqlite')
BATCH = 'owner-7002712356-buyer-batch3'
APPROVAL = 'OWNER_ISSUE156_COMMENT7002712356_2_CNY3'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    ready = json.loads((ROOT / 'ready-private.json').read_bytes())
    assert ready['actual_pg_fake_passed'] is True
    binding, job = ready['binding'], ready['job']
    # Route ordinary authenticated PG TCP to this run's owned internal endpoint.
    # Original connect role/RLS/table-permission checks and transactions execute.
    connect = psycopg.connect
    def routed(*a, **kw):
        assert not a and kw['host'] == '127.0.0.1' and kw.get('port', 5432) == 5432
        return connect(**{**kw, 'host': ready['host'], 'port': ready['port']})
    psycopg.connect = routed
    trust = Path('/run/vrae-targets/trust.json')
    trust.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'trust-public.json', trust)
    trust.chmod(0o444)
    adapter, held = build_adapter(binding, job)
    assert held['artifact']['source_authority']['authorization']['document']['source_class'] == 'CONTROLLED_NON_CUSTOMER'
    before = encode(held)
    if not args.live:
        result = execute(binding, job, adapter, operation_id='buyer-batch3-direct-pg-preflight')
        assert result['reason'] == 'PROVIDER_GO_NOT_GRANTED' and result['pg_receipt_status'] == 'RECORDED'
        (ROOT / 'direct-pg-preflight.json').write_bytes(encode(result))
        print('DIRECT_ORIGINAL_PG_PREFLIGHT_PASS_NO_MODEL_CALL')
        return
    assert (ROOT / 'direct-pg-preflight.json').is_file()
    # A second invocation, including after a failed/unknown attempt, is forbidden.
    with (ROOT / 'live-attempt-started.json').open('xb') as f:
        f.write(encode({'batch': BATCH, 'started_at': datetime.now(UTC).isoformat()}))
    secret = json.loads(sys.stdin.buffer.read())
    expiry = datetime.now(UTC) + timedelta(minutes=15)
    # Baseline is immutable old 3 UNKNOWN + prior 2 USAGE_RECORDED, not a restore.
    with sqlite3.connect(LEDGER) as db:
        old = db.execute('SELECT * FROM calls ORDER BY id').fetchall()
        policy = db.execute('SELECT * FROM policy').fetchall()
    assert len(old) == 5
    quota = Quota(LEDGER, batch=BATCH)
    provider = QwenProvider(Config(secret['workspace_id']), quota,
        permission=Permission(APPROVAL, expiry, 2, 3000000),
        price=Price('official-beijing-qwen4-buyer-20261119', MODEL_SOURCE,
                    10000000, 30000000, expiry), key=secret['key'])
    provider.authorize(datetime.now(UTC))
    adapter._provider = provider
    observed = {}
    native = NativeTransport.post

    async def observe(self, config, key, body, timeout_ms):
        request = encode(body)
        assert key.encode() not in request and config.workspace_id.encode() not in request
        (ROOT / 'buyer-request.json').write_bytes(request)
        status, raw = await native(self, config, key, body, timeout_ms)
        assert key.encode() not in raw and config.workspace_id.encode() not in raw
        (ROOT / 'buyer-response-private.bin').write_bytes(raw)
        observed.update(http_status=status, response_sha256=hashlib.sha256(raw).hexdigest())
        response = json.loads(raw)
        observed.update(finish_reason=(response.get('choices') or [{}])[0].get('finish_reason'),
                        model=response.get('model'), usage=response.get('usage'))
        return status, raw
    NativeTransport.post = observe
    try:
        result = execute(binding, job, adapter, operation_id='owner-7002712356-buyer-001')
    finally:
        NativeTransport.post = native
    # Preserve the result BEFORE any additional PG read can fail.
    (ROOT / 'buyer-receipt.json').write_bytes(encode(result))
    with sqlite3.connect(LEDGER) as db:
        assert db.execute('SELECT * FROM policy').fetchall() == policy
        assert all(db.execute('SELECT * FROM calls WHERE id=?', (r[0],)).fetchone() == r for r in old)
        extra = db.execute('SELECT c.state,c.reserved,c.receipt FROM calls c JOIN call_batches b '
                           'ON b.call_id=c.id WHERE b.batch_id=?', (BATCH,)).fetchall()
    assert len(extra) <= 1 and sum(r[1] for r in extra) <= 3000000
    pins_current = False
    pg_readback = False
    try:
        pins_current = encode(current_input(binding, job)) == before
        # Independent read-only audit of the operator-owned disposable PG. The
        # actual dispatch/authority/record path above uses only the scoped AI role.
        with connect(host=ready['host'], port=ready['port'], dbname='vrae_ra4a_p1',
                     user='postgres', password=secret['audit_password'], connect_timeout=2,
                     options='-c statement_timeout=3000 -c default_transaction_read_only=on') as audit:
            row = audit.execute('SELECT receipt FROM target_v1.ai_receipts '
                'WHERE tenant_id=%s AND job_id=%s AND operation_id=%s',
                (binding['tenant_id'], job, result['operation_id'])).fetchone()
        pg_readback = row is not None and encode(row[0]) == encode(
            {k: v for k, v in result.items() if k != 'pg_receipt_status'})
        if row:
            (ROOT / 'pg-live-readback.json').write_bytes(encode(row[0]))
    except Exception:
        pass
    passed = (result['state'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW'
        and result['pg_receipt_status'] == 'RECORDED' and pins_current and pg_readback
        and observed.get('finish_reason') == 'stop' and observed.get('model') == 'qwen4-max'
        and result['usage'] is not None and result['usage']['usage_origin'] == 'PROVIDER_REPORTED'
        and len(result['claims']) in (1, 2) and len(extra) == 1 and extra[0][0] == 'USAGE_RECORDED'
        and all(c['status'] == 'HUMAN_REVIEW_REQUIRED' for c in result['claims']))
    summary = {'status': 'REAL_QWEN4_BUYER_CANDIDATE_PASS' if passed else 'STOP_NOT_PASSED',
        'old_five_rows_unchanged': True, 'old_policy_unchanged': True,
        'new_dispatches': len(extra), 'new_cap_micros': 3000000,
        'new_reserved_or_estimated_micros': sum(r[1] for r in extra),
        'pg_current_pins': pins_current, 'pg_receipt_status': result['pg_receipt_status'],
        'pg_durable_readback': pg_readback,
        'claims': len(result['claims']), 'reason': result.get('reason'),
        'actual_invoice': 'UNKNOWN', 'customer_data_sent': False,
        'report_published': False, 'automatic_retries': 0, **observed}
    (ROOT / 'buyer-summary.json').write_bytes(encode(summary))
    print(encode(summary).decode())


if __name__ == '__main__':
    main()
