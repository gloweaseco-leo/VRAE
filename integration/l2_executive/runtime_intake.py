"""Bounded private TEST_ONLY controls, consumed inside original Brief authority.

No HTTP receipt/configuration endpoint. The existing supervisor owns this
private state directory; receiver private keys never enter it or the SSR.
"""
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from vrae.l2_ops.intake import SyntheticReceiver
from vrae.l2_ops.sources import OperationsDenied


def consume(manager, adapter, service, ledger, brief_ref):
    root = Path(manager.root)
    request = root/'s4-intake-request.json'
    if not request.exists():
        return
    if request.is_symlink() or request.stat().st_size > 8192:
        raise OperationsDenied('S4_PRIVATE_CONTROL_DENIED')
    running = root/'s4-intake-running.json'
    request.rename(running)
    result = {'request_id': None, 'ok': False}
    try:
        body = json.loads(running.read_bytes())
        ref = body['request_id']
        if type(ref) is not str or len(ref) != 32 or any(c not in '0123456789abcdef' for c in ref):
            raise OperationsDenied('S4_PRIVATE_CONTROL_DENIED')
        result['request_id'] = ref
        operation = body['operation']
        base = {'request_id', 'operation', 'job_id', 'report_id'}
        if (body.get('job_id') != manager.active['task'].job_id or
                body.get('report_id') != manager.active['report_id']):
            raise OperationsDenied('S4_PRIVATE_TASK_CHANGED')
        # Reuse original current task/report/review/PG authority for every
        # private operation, including configuring this synthetic receiver.
        row = adapter.current(service, ledger, brief_ref)
        if operation == 'configure' and set(body) == base | {'public_key'}:
            public = bytes.fromhex(body['public_key'])
            Ed25519PublicKey.from_public_bytes(public)
            if adapter.receiver is not None and adapter.receiver.public_key != public:
                raise OperationsDenied('S4_RECEIVER_REPLACEMENT_DENIED')
            adapter.receiver = SyntheticReceiver(public)
        elif operation == 'receive' and set(body) == base | {'receipt', 'signature'}:
            row = adapter.receive(service, ledger, brief_ref, body['receipt'], bytes.fromhex(body['signature']))
        elif operation != 'read' or set(body) != base:
            raise OperationsDenied('S4_PRIVATE_CONTROL_DENIED')
        result.update(ok=True, row=row)
    except Exception as error:
        result['denied'] = 'S4_PRIVATE_CONTROL_DENIED'
        code = error.args[0] if error.args else None
        result['code'] = code if isinstance(code, str) and code in {
            'L2_CURRENT_AUTHORITY_EXPIRED', 'L2_BRIEF_STALE_OR_CROSS_TASK',
            'S4_PRIVATE_TASK_CHANGED', 'S4_RECEIVER_REPLACEMENT_DENIED',
            'S4_RECEIVER_SIGNATURE_DENIED', 'S4_RECEIPT_STALE_OR_CROSS_TASK',
            'S4_RECEIVER_UNAVAILABLE_OR_REVOKED', 'S4_RECEIPT_CONFLICT',
        } else 'ORIGINAL_AUTHORITY_OR_PRIVATE_CONTROL_DENIED'
        raise
    finally:
        temporary = root/'s4-intake-response.tmp'
        temporary.write_text(json.dumps(result), encoding='utf-8')
        temporary.chmod(0o600)
        temporary.replace(root/'s4-intake-response.json')
        running.unlink()


def control(run, *, command=None, read=False):
    """Original supervisor's exact owned SSR container; no arbitrary path/op."""
    from integration.beta_review.codex3.runner import cmd
    if read:
        return json.loads(cmd(['docker', 'exec', '--user', '10003:10003', run.ssr_name,
            'python', '-c', "from pathlib import Path; print(Path('/state/l2-native/s4-intake-response.json').read_text())"]))
    if type(command) is not dict or command.get('operation') not in ('configure', 'read', 'receive'):
        raise OperationsDenied('S4_PRIVATE_CONTROL_DENIED')
    proof = json.loads(cmd(['docker', 'exec', '--user', '10003:10003', run.ssr_name,
        'python', '-c', "from pathlib import Path; print(Path('/state/l2-native/active-proof.json').read_text())"]))
    assert proof['task']['job_id'] in run.web_tasks
    raw = json.dumps({**command, 'job_id': proof['task']['job_id'], 'report_id': proof['report_id']})
    if len(raw.encode()) > 8192:
        raise OperationsDenied('S4_PRIVATE_CONTROL_DENIED')
    cmd(['docker', 'exec', '--user', '10003:10003', run.ssr_name, 'python', '-c',
         "from pathlib import Path; import sys; p=Path('/state/l2-native/s4-intake-request.json'); "
         "f=p.open('x'); f.write(sys.argv[1]); f.close(); p.chmod(0o600)", raw])
    return {'queued': command['request_id']}
