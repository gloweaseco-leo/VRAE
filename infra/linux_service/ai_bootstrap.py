"""Same deployment's sole AI loop in an independent egress namespace.

The primary source/PG/Worker namespace remains internal. No model gateway,
new Worker, Docker socket, browser credential or production data fixture.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from contracts.l2_launch.contract import canonical
from integration.authorized_targets.source_authority import TRUST
from infra.linux_service import supervisor as parent
from infra.linux_service import qwen_runtime as model


def main():
    if os.geteuid() != 0 or Path('/var/run/docker.sock').exists():
        raise PermissionError('NAMESPACE_PARENT_REQUIRED')
    manifest = json.loads(parent.private(parent.INPUT / 'manifest.json'))
    sha = Path('/work/infra/linux_service/source-sha').read_text().strip()
    if manifest['source_sha'] != sha:
        raise PermissionError('DEPLOYMENT_SOURCE_MISMATCH')
    parent.RUNTIME.mkdir(mode=0o711, exist_ok=True)
    parent.RUNTIME.chmod(0o711)
    TRUST.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    parent.write(TRUST, parent.private(parent.INPUT / 'trust.json'), mode=0o444)
    cfg = json.loads(parent.private(parent.INPUT / 'ai.json'))
    if any(b.get('port') != 'AI' or b['kind'] != 'APP' for b in cfg['bindings']):
        raise PermissionError('SEPARATE_SERVICE_ROLES_REQUIRED')
    directory = parent.RUNTIME / 'ai'
    directory.mkdir(mode=0o750)
    os.chown(directory, 0, model.AI_UID)
    configured = False
    policy = {'uid': model.AI_UID, 'default': 'REJECT', 'provider_ip_count': 0, 'dns_count': 0}
    parent.fence(model.AI_UID, [5432])
    try:
        envelope = json.loads(parent.private(parent.INPUT / 'model-permit.json'))
        document = model.validate(envelope, source_sha=sha, source_class=manifest['source_class'])
        parent.write(model.PERMIT, canonical(envelope), mode=0o440)
        os.chown(model.PERMIT, 0, model.AI_UID)
        secret = parent.private(parent.INPUT / 'model-key')
        parent.write(model.KEY, secret, mode=0o440)
        os.chown(model.KEY, 0, model.AI_UID)
        del secret
        policy = model.model_fence(parent.command, document)
        configured = True
    except Exception:
        # The original loop still records NO-GO/KEY_REQUIRED failures via PG.
        # No remote exception, credential value or workspace is logged.
        parent.fence(model.AI_UID, [5432])
        model.PERMIT.unlink(missing_ok=True)
    cfg['runtime_qwen'] = True
    cfg['source_sha'] = sha
    parent.write(directory / 'config.json', canonical(cfg), model.AI_UID, mode=0o400)
    endpoint = json.loads(parent.private(parent.INPUT / 'ai-pg-endpoint.json'))
    # Operator-inspected internal endpoint. AI itself can only use localhost PG.
    import ipaddress
    if not ipaddress.ip_address(endpoint['host']).is_private or endpoint['port'] != 15432:
        raise PermissionError('PRIVATE_ORIGINAL_PG_REQUIRED')
    forward = model.pg_forward('127.0.0.1', 5432, endpoint['host'], 15432)
    stop = False
    def halt(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, halt)
    signal.signal(signal.SIGINT, halt)
    child = None
    failures = 0
    try:
        while not stop:
            if child is None or child.poll() is not None:
                if child is not None:
                    failures += 1
                    if failures > 5:
                        raise RuntimeError('SERVICE_RESTART_BUDGET_EXHAUSTED')
                child = subprocess.Popen([sys.executable, '-m', 'infra.linux_service.ai_loop',
                    '--config', str(directory / 'config.json')], user=model.AI_UID,
                    group=model.AI_UID, extra_groups=[], env=parent.ENV, stdin=subprocess.DEVNULL)
            (parent.RUNTIME / 'ready.json').write_bytes(canonical({
                'phase': 'AI_SUPERVISED', 'source_sha': sha, 'model': 'qwen4-max',
                'model_configuration_valid': configured, 'policy': policy,
                'actual_invoice': 'UNKNOWN'}))
            time.sleep(1)
    finally:
        if child is not None and child.poll() is None:
            subprocess.run([sys.executable, '-c',
                'import os,sys,signal;os.kill(int(sys.argv[1]),signal.SIGTERM)', str(child.pid)],
                user=model.AI_UID, group=model.AI_UID, extra_groups=[], env=parent.ENV, check=False)
            child.wait(timeout=10)
        forward.shutdown()


if __name__ == '__main__':
    main()
