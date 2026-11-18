"""Deterministic independent source/contract replay; absent HTTP stays BLOCKED."""
import argparse
import asyncio
import hashlib
import json
import re
import socket
import subprocess
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from .contract_cases import (
    READ_CASES,
    SUBMIT_CASES,
    VIEW_CASES,
    idempotency_attack,
    log_attack,
    session_attack,
    submit_attack,
    view_attack,
)
from .source_cases import CASES, OWN, execute

ROOT = OWN.parents[2]
BASE = '7fdeeed0f427ce3b94677ab2a480eae1556e85ca'


@contextmanager
def network_tripwire():
    """Instrumentation only, not a fake HTTP response. Unexpected IO FAILS."""
    attempted = []
    def refused(*args, **kwargs):
        attempted.append(True)
        raise AssertionError('UNEXPECTED_NETWORK_ATTEMPT')
    with ExitStack() as stack:
        for owner, name in [(socket, 'create_connection'), (socket, 'getaddrinfo'),
                            (asyncio.BaseEventLoop, 'sock_connect')]:
            stack.enter_context(patch.object(owner, name, refused))
        yield attempted


def http_gaps():
    return [{**case, 'realm': 'ACTUAL_G1_HTTP_NOT_EXECUTED', 'verdict': 'BLOCKED',
             'code': 'BLOCKED_PENDING_G1_IMPL', 'source_base': BASE,
             'reason': 'No independently audited running C3 G1 HTTP/PG service has been supplied.'}
            for case in json.loads((OWN/'http_matrix.json').read_text(encoding='utf-8'))]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{3,40}', args.label):
        raise ValueError('OWNED_LABEL_REQUIRED')
    out = OWN/'.runtime'/args.label
    out.mkdir(parents=True, exist_ok=False)
    source, contract = [], []
    with network_tripwire() as attempted:
        for spec in CASES:
            row, archive = execute(spec)
            # Actual second replay must reproduce all source results and pack bytes.
            again, second = execute(spec)
            if canonical((row, archive)) != canonical((again, second)):
                row['verdict'] = 'FAIL'
                row['replay_mismatch'] = True
            source.append(row)
            if archive is not None:
                (out/(spec['id']+'-pack.json')).write_bytes(canonical(archive))
        for kind in SUBMIT_CASES:
            folder = out/('contract-'+kind)
            folder.mkdir()
            contract.append(submit_attack(folder, kind))
        for kind in READ_CASES:
            folder = out/('contract-'+kind)
            folder.mkdir()
            contract.append(session_attack(folder, kind))
        for kind in VIEW_CASES:
            contract.append(view_attack(kind))
        folder = out/'contract-idempotency'
        folder.mkdir()
        contract.extend((idempotency_attack(folder), log_attack()))
        if attempted:
            raise AssertionError('TARGET_NETWORK_WAS_ATTEMPTED')
    gaps = http_gaps()
    core = {'source': source, 'contract_only': contract, 'http': gaps}
    report = {'kind': 'G1_S1_INDEPENDENT_SECURITY_PARTIAL_HTTP_BLOCKED', 'base': BASE,
        'source_sha': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'source_tree_dirty': bool(subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True).strip()),
        'results': core, 'deterministic_replay_sha256': hashlib.sha256(canonical(core)).hexdigest(),
        'unexpected_network_attempts': len(attempted), 'actual_g1_http_pass': False,
        'source_pass': sum(row['verdict'] == 'PASS' for row in source),
        'contract_function_pass': len(contract), 'http_blocked': len(gaps),
        'real_human_review': False, 'real_share_grants': False, 'real_model_calls': 0,
        'g2_live_permission': 'NOT_GRANTED_LIVE_CAPTURE_DISABLED'}
    (out/'matrix.json').write_bytes(canonical(report))
    (out/'http-blocked.json').write_bytes(canonical(gaps))
    # Do not upload fixture SQLite journals, grants or session values.
    print(json.dumps({k: v for k, v in report.items() if k not in ('results',)}))
    if any(row['verdict'] != 'PASS' for row in source+contract):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
