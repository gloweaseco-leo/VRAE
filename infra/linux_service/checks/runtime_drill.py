"""Controlled same-deployment PG/Worker/HTTPS/AI fake acceptance; no live key."""
import base64
from datetime import datetime, UTC, timedelta
import hashlib
import json
import sqlite3
import time

from contracts.l2_launch.contract import canonical
from infra.linux_service import control as ctl
from infra.linux_service.qwen_provision import rows
from vrae.intelligence.qwen import Quota


def exercise(owner, config, client, private, public):
    n = ctl.names(owner)
    manifest = json.loads((config / 'manifest.json').read_bytes())
    assert manifest['source_class'] == 'CONTROLLED_NON_CUSTOMER'
    # Explicit protocol-fake lineage, unrelated to any real retained ledger.
    initial = private / 'FAKE-ONLY-model.sqlite'
    Quota(initial, create=True)
    with sqlite3.connect(initial) as db:
        db.execute('INSERT INTO calls VALUES(?,?,?,?,NULL,NULL)',
                   ('FAKE-historical-unknown', 'FAKE-intent', 100, 'DISPATCHED_USAGE_UNKNOWN'))
        old = rows(db)
    deployment = json.loads((config / 'deployment-intent.json').read_bytes())['document']
    payload = {'operator_fee_go': 'GRANTED', 'workspace_id': 'synthetic-workspace',
        'key': 'synthetic-key-no-real-secret-0000', 'daily_cap_micros': 5_000_000,
        'approval_ref': 'TEST_ONLY_RUNTIME_NOT_NATIVE_GO',
        'expires_at': (datetime.now(UTC) + timedelta(minutes=45)).isoformat(),
        'authorization_hashes': deployment['authorization_hashes'],
        'input_micros_per_million': 10_000_000, 'output_micros_per_million': 30_000_000,
        'retained_quota_base64': base64.b64encode(initial.read_bytes()).decode(),
        'retained_rows_sha256': hashlib.sha256(canonical(old)).hexdigest()}
    ctl.docker('run', '--rm', '-i', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--cap-add', 'CHOWN', '--cap-add', 'DAC_OVERRIDE', '--tmpfs', '/tmp:rw,size=8m',
        '--tmpfs', '/run/vrae-targets:rw,size=1m',
        '--mount', 'type=volume,src=' + n['operator'] + ',dst=/operator',
        '--mount', 'type=volume,src=' + n['ledger'] + ',dst=/ledger', manifest['image'],
        'python', '-m', 'infra.linux_service.qwen_provision', input=canonical(payload))
    manifest['isolated_model_runtime'] = True
    (config / 'manifest.json').write_bytes(canonical(manifest))
    original = ctl.docker
    def fake_bootstrap(*args, **kwargs):
        args = tuple('infra.linux_service.checks.fake_bootstrap' if x == 'infra.linux_service.ai_bootstrap'
                     else x for x in args)
        return original(*args, **kwargs)
    ctl.docker = fake_bootstrap
    try:
        ctl.restart(owner, config)
    finally:
        ctl.docker = original
    end = time.monotonic() + 60
    while time.monotonic() < end:
        try:
            ready = json.loads(ctl.docker('exec', n['ai'], 'cat', '/run/service/ready.json'))
            if ready['phase'] == 'AI_SUPERVISED':
                break
        except Exception:
            pass
        time.sleep(.5)
    else:
        raise AssertionError('FAKE_AI_RUNTIME_NOT_READY')
    assert ready['policy']['verification_realm'] == 'PROTOCOL_FAKE_NOT_REAL_API'
    primary = json.loads(ctl.docker('exec', n['runtime'], 'cat', '/run/service/ready.json'))
    assert 'ai' not in primary['children'] and primary['ai_runtime'] == 'ISOLATED_SIDECAR'
    probe = """import json,os,socket
from pathlib import Path
status=Path('/proc/self/status').read_text()
assert 'CapEff:\\t0000000000000000' in status and 'NoNewPrivs:\\t1' in status
out=[]
for host,port in [('169.254.169.254',80),('192.168.1.1',22),('1.1.1.1',22),('127.0.0.1',8769)]:
 try:
  s=socket.create_connection((host,port),timeout=.3);s.close();out.append(False)
 except OSError:out.append(True)
try:os.setuid(0);out.append(False)
except PermissionError:out.append(True)
try:Path('/operator/deployment-key').read_bytes();out.append(False)
except PermissionError:out.append(True)
assert all(out)
print(json.dumps({'kernel_denials':out,'capabilities_zero':True,'no_new_privileges':True}))
"""
    isolation = json.loads(ctl.docker('exec', '-u', '10008:10008', n['ai'], 'python', '-c', probe))
    submitted = json.loads(ctl.docker('exec', '-u', '10004', client, 'python', '-m',
                                     'infra.linux_service.checks.submit_tasks', '--count', '6'))
    requests = submitted['requests']
    # All IDs originate from authenticated HTTPS202, not fabricated PG rows.
    runs = [r['accepted']['run_id'] for r in requests]
    audit = """import json,sys,psycopg
from pathlib import Path
with psycopg.connect(host='127.0.0.1',dbname='vrae_ra4a_p1',user='postgres',password=Path('/operator/pg-password').read_text(),autocommit=True) as c:
 r=c.execute('SELECT a.receipt FROM target_v1.ai_receipts a JOIN target_v1.results z USING(tenant_id,job_id) WHERE z.run_id=ANY(%s::uuid[]) AND a.operation_id LIKE %s',(json.loads(sys.argv[1]),'service-ai-%')).fetchall()
 print(json.dumps([x[0] for x in r]))
"""
    end = time.monotonic() + 180
    while time.monotonic() < end:
        receipts = json.loads(ctl.docker('exec', n['runtime'], 'python', '-c', audit, json.dumps(runs)))
        if len(receipts) == 6:
            break
        time.sleep(1)
    else:
        raise AssertionError('FAKE_AI_DURABLE_RECEIPTS_MISSING')
    assert sum(r['state'] == 'AI_CANDIDATES_FOR_HUMAN_REVIEW' for r in receipts) == 1
    reasons = {r['reason'] for r in receipts}
    assert {'OWNER_PERMISSION_REQUIRED', 'KEY_REQUIRED', 'CANDIDATE_SCHEMA', 'TIMEOUT', 'BUDGET_REFUSED'} <= reasons
    assert all(not r['grants_report_access'] and r['model_runtime']['mode'] == 'REAL_QWEN' for r in receipts)
    for r in receipts:
        if r.get('usage'):
            assert r['usage']['usage_origin'] == 'PROTOCOL_FAKE_NOT_REAL_API'
            assert r['usage']['real_model_calls'] == 0
    # Root fixture's retained import remains intact; fake reservations live only
    # in the AI test process's explicit disposable quota, never in real lineage.
    lineage = "import sqlite3,json; c=sqlite3.connect('/model-ledger/quota.sqlite'); print(json.dumps(c.execute('SELECT id,reserved,state FROM calls').fetchall()))"
    assert json.loads(ctl.docker('exec', '-u', '10008', n['ai'], 'python', '-c', lineage)) == [
        ['FAKE-historical-unknown', 100, 'DISPATCHED_USAGE_UNKNOWN']]
    (public / 'qwen-runtime.json').write_bytes(canonical({'scope': 'SAME_DEPLOYMENT_PROTOCOL_FAKE',
        'actual_pg_worker_https': True, 'same_pg_volumes': True, 'sole_ai_loop': True,
        'source_namespace_internal_unchanged': True, 'model_calls': 0, 'isolation': isolation,
        'cases': [{'state': r['state'], 'reason': r['reason'], 'usage': r.get('usage'),
                   'task': r['task'], 'report_content_hash': r['report_content_hash']} for r in receipts],
        'retained_lineage_unchanged': True, 'customer_report_published': False}))
