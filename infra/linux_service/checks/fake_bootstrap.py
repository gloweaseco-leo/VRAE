"""Explicit controlled acceptance entrypoint; never selected by service control."""
import json
import subprocess
from infra.linux_service import ai_bootstrap, qwen_runtime
from infra.linux_service.supervisor import INPUT, private


def main():
    d = json.loads(private(INPUT / 'model-permit.json'))['document']
    assert d['source_class'] == 'CONTROLLED_NON_CUSTOMER' and d['approval_ref'].startswith('TEST_ONLY_')
    popen = subprocess.Popen
    def spawn(args, **kwargs):
        if 'infra.linux_service.ai_loop' in args:
            args = ['infra.linux_service.checks.fake_loop' if x == 'infra.linux_service.ai_loop' else x for x in args]
        return popen(args, **kwargs)
    subprocess.Popen = spawn
    qwen_runtime.model_fence = lambda *_: {'uid': 10008, 'default': 'REJECT',
        'provider_ip_count': 0, 'dns_count': 0, 'verification_realm': 'PROTOCOL_FAKE_NOT_REAL_API'}
    ai_bootstrap.main()


if __name__ == '__main__':
    main()
