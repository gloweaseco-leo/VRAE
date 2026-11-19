"""One explicitly authorized real dispatch; original ledger, DPAPI anonymous stdin."""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from integration.qwen_provider.probe import minimal_probe_body
from vrae.intelligence.common import encode
from vrae.intelligence.qwen import Config, Permission, Price, QwenProvider, Quota
from vrae.intelligence.qwen.provider import MODEL_SOURCE, digest, strict_json
from infra.qwen_provider.transport import NativeTransport

ROOT = Path(__file__).parent / 'live-batch2'
ROOT.mkdir(exist_ok=True)
LEDGER = Path(__file__).parent / 'live-smoke' / 'quota.sqlite'
BATCH = 'owner-7000206811-qwen4-beijing-2'
APPROVAL = 'https://github.com/gloweaseco-leo/VRAE/issues/156#issuecomment-7000206811'
APPROVAL_REF = 'OWNER_ISSUE156_COMMENT7000206811_QWEN4_2_CNY6'

def now():
    return datetime.now(timezone.utc)

def write(name, value):
    with (ROOT / name).open('xb') as f:
        f.write(encode(value))

def historical():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        policy = db.execute('SELECT * FROM policy').fetchall()
        rows = db.execute('SELECT * FROM calls ORDER BY id').fetchall()
        return policy, rows

async def main():
    assert LEDGER.is_file() and not (ROOT / 'probe-result.json').exists()
    credentials = json.loads(sys.stdin.read())
    key, workspace = credentials['key'], credentials['workspace_id']
    assert workspace == 'REDACTED_WORKSPACE'
    before = historical()
    assert len(before[1]) == 3 and all(r[3] == 'DISPATCHED_USAGE_UNKNOWN' for r in before[1])
    state_path = ROOT / 'grant.json'
    if not state_path.exists():
        write('grant.json', {'batch': BATCH, 'approval': APPROVAL, 'created_at': now().isoformat(),
            'expires_at': (now() + timedelta(hours=24)).isoformat(), 'max_calls': 2, 'cap_micros':6000000,
            'price_source':MODEL_SOURCE, 'input_micros_per_million':10000000,
            'output_micros_per_million':30000000})
    grant = json.loads(state_path.read_bytes())
    assert grant['batch'] == BATCH and grant['approval'] == APPROVAL and grant['max_calls'] == 2
    expiry = datetime.fromisoformat(grant['expires_at'])
    quota = Quota(LEDGER, create=False, batch=BATCH)
    provider = QwenProvider(Config(workspace), quota,
        permission=Permission(APPROVAL_REF, expiry, 2, 6000000),
        price=Price('official-beijing-qwen4-20261119', MODEL_SOURCE, 10000000, 30000000, expiry), key=key)
    assert not provider.protocol_fake
    provider.authorize(now())
    operation = 'owner-7000206811-qwen4-probe-001'
    body = minimal_probe_body()
    write('probe-request.json', body)
    observed = {}
    original = NativeTransport.post

    async def observe(self, config, secret, request, timeout_ms):
        observed['transport_entered_at'] = now().isoformat()
        status, raw = await original(self, config, secret, request, timeout_ms)
        observed.update(http_status=status, response_sha256=hashlib.sha256(raw).hexdigest(),
                        response_bytes=len(raw))
        assert key.encode() not in raw
        with (ROOT / 'probe-response.bin').open('xb') as f:
            f.write(raw)
        try:
            obj = strict_json(raw)
            observed['reported_model'] = obj.get('model')
            observed['reported_usage'] = obj.get('usage')
            error = obj.get('error') or {}
            observed['vendor_error_code'] = error.get('code')
        except Exception:
            observed['response_json_valid'] = False
        return status, raw

    NativeTransport.post = observe
    result = {'batch':BATCH, 'operation_id':operation, 'approval':APPROVAL,
        'started_at':now().isoformat(), 'code_head':subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=REPO).decode().strip(),
        'requested_model':'qwen4-max', 'max_completion_tokens':64,
        'first_success':False, 'stop':True, 'usage':None, 'actual_invoice_cost':'UNKNOWN',
        'historical_usage_and_cost':'UNKNOWN', 'protocol_fake':False,
        'historical_rows_sha256_before':hashlib.sha256(encode(before)).hexdigest()}
    try:
        content, usage = await provider.complete(body, operation=operation,
            scope={'tenant_id':'synthetic-owner-probe', 'run_id':'owner-7000206811-probe',
                   'policy_id':'synthetic-no-source', 'policy_version':1},
            context_ref='s3ctx-' + digest({'pure_synthetic':True,'operation':operation}),
            now=now(), timeout_ms=120000)
        result['usage'] = usage
        assert strict_json(content) == {'ok':True}
        result.update(first_success=True, stop=False, code='REAL_MODEL_AND_USAGE_CONFIRMED')
    except Exception as error:
        from vrae.intelligence.qwen import QwenError
        result['code'] = str(error) if type(error) is QwenError else 'PROBE_FAILED'
    finally:
        NativeTransport.post = original
    after = historical()
    original_ids = {r[0] for r in before[1]}
    preserved = (after[0], [r for r in after[1] if r[0] in original_ids])
    assert preserved == before
    result.update(observed)
    result.update(finished_at=now().isoformat(), historical_rows_unchanged=True,
                  ledger_total_rows=len(after[1]), new_batch_rows=len(after[1])-3)
    assert key.encode() not in encode(result)
    write('probe-result.json', result)
    print(encode(result).decode())

if __name__ == '__main__':
    asyncio.run(main())
