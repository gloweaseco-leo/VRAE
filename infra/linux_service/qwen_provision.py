"""Explicit offline operator action: private stdin -> ext4 key + retained quota.

Not imported by services. Never creates an empty quota or replaces an existing
one. The host seals its former quota before enabling the sole AI runtime.
"""
import base64
from datetime import datetime, UTC, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from contracts.l2_launch.contract import canonical
from integration.authorized_targets.source_authority import TRUST, verify
from infra.linux_service.supervisor import INPUT, private, write
from infra.linux_service.qwen_runtime import DATA_SCOPE, validate
from vrae.intelligence.qwen import Config
from vrae.intelligence.qwen.provider import MODEL_SOURCE


def rows(connection):
    result = {}
    for (table,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', table):
            raise ValueError('QUOTA_TABLE_INVALID')
        result[table] = sorted(connection.execute('SELECT * FROM "' + table + '"').fetchall(), key=repr)
    return result


def main():
    if os.geteuid() != 0:
        raise PermissionError('OPERATOR_ROOT_REQUIRED')
    payload = json.loads(sys.stdin.buffer.read(2_000_001))
    if payload.get('operator_fee_go') != 'GRANTED':
        raise PermissionError('EXPLICIT_OPERATOR_FEE_PERMISSION_REQUIRED')
    Config(payload['workspace_id'])
    key = payload['key']
    if type(key) is not str or not 16 <= len(key) <= 256 or not re.fullmatch(r'[A-Za-z0-9._~+/-]+=*', key):
        raise ValueError('KEY_REQUIRED')
    now = datetime.now(UTC)
    expiry = datetime.fromisoformat(payload['expires_at'])
    if not now < expiry <= now + timedelta(hours=24):
        raise ValueError('BOUNDED_OPERATOR_EXPIRY_REQUIRED')
    manifest = json.loads(private(INPUT / 'manifest.json'))
    TRUST.parent.mkdir(parents=True, exist_ok=True)
    write(TRUST, private(INPUT / 'trust.json'), mode=0o444)
    deployment = json.loads(private(INPUT / 'deployment-intent.json'))
    source = verify(deployment, 'DEPLOYMENT_OWNER', manifest['source_class'], now)
    allowed = payload['authorization_hashes']
    dynamic = payload.get('allow_signed_model_consent', False)
    if type(dynamic) is not bool or (not allowed and not dynamic) or not set(allowed) <= set(source['authorization_hashes']):
        raise PermissionError('EXPLICIT_SOURCE_PROCESSING_PERMISSION_REQUIRED')
    document = {'contract': 'vrae.qwen-runtime-allowance.v1',
        'source_sha': Path('/work/infra/linux_service/source-sha').read_text().strip(),
        'source_class': manifest['source_class'], 'model_fee_go': 'GRANTED',
        'region': 'cn-beijing', 'model': 'qwen4-max', 'workspace_id': payload['workspace_id'],
        'data_scope': DATA_SCOPE, 'max_output_tokens': 2048, 'max_dispatches_per_task': 1,
        'automatic_retry': False, 'daily_cap_micros': payload['daily_cap_micros'],
        'approval_ref': payload['approval_ref'], 'authorization_hashes': allowed,
        'allow_signed_model_consent': dynamic,
        'not_before': now.isoformat(), 'expires_at': expiry.isoformat(),
        'price_source': MODEL_SOURCE, 'input_micros_per_million': payload['input_micros_per_million'],
        'output_micros_per_million': payload['output_micros_per_million']}
    signer = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private(INPUT / 'deployment-key').decode().strip()))
    envelope = {'key_id': deployment['key_id'], 'document': document,
                'signature': signer.sign(canonical(document)).hex()}
    validate(envelope, source_sha=document['source_sha'], source_class=manifest['source_class'], now=now)
    target = Path('/ledger/qwen')
    database = target / 'quota.sqlite'
    if not target.exists():
        raw = base64.b64decode(payload['retained_quota_base64'], validate=True)
        incoming = Path('/tmp/incoming.sqlite')
        with incoming.open('xb') as f:
            f.write(raw)
        with sqlite3.connect(incoming.as_uri() + '?mode=ro', uri=True) as old:
            held = rows(old)
            lineage = hashlib.sha256(canonical(held)).hexdigest()
            if lineage != payload['retained_rows_sha256'] or not held.get('calls') or 'policy' not in held:
                raise ValueError('RETAINED_QUOTA_REQUIRED')
            target.mkdir(mode=0o750)
            with sqlite3.connect(database) as new:
                old.backup(new)
                if rows(new) != held:
                    raise ValueError('QUOTA_TRANSFER_MISMATCH')
        write(target / 'lineage.json', canonical({'old_rows_sha256': lineage,
            'old_calls': len(held['calls']), 'canonical_storage': 'LINUX_EXT4', 'invoice': 'UNKNOWN'}),
            uid=10008, mode=0o640)
        os.chown(target / 'lineage.json', 10008, 10007)
        os.chown(database, 10008, 10007)
        database.chmod(0o640)
        os.chown(target, 10008, 10007)
        target.chmod(0o750)
        transferred = len(held['calls'])
    elif not database.is_file():
        raise PermissionError('LOST_RETAINED_QUOTA_NO_RECREATE')
    else:
        transferred = 0  # Renewal does not restore a former counter snapshot.
    write(INPUT / 'model-key', key.encode('ascii'))
    write(INPUT / 'model-permit.json', canonical(envelope))
    print(canonical({'phase': 'OPERATOR_AI_MATERIAL_STAGED', 'old_calls_transferred': transferred,
        'daily_cap_micros': document['daily_cap_micros'], 'expires_at': document['expires_at'],
        'model_dispatches': 0, 'secret_values_logged': False}).decode())


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('{"phase":"OPERATOR_AI_MATERIAL_REFUSED","model_dispatches":0}', flush=True)
        raise SystemExit(1) from None
