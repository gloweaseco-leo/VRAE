"""Dedicated bounded egress process, kept outside the network-free domain tree."""
import asyncio
import json
import os
from pathlib import Path
import sys
import stat

from vrae.intelligence.common import encode


def child_environment():
    """Windows DNS needs SystemRoot; inherit no proxy, key, PATH or other input."""
    if sys.platform != 'win32':
        return {}
    root = os.environ.get('SystemRoot')
    if not root:
        from vrae.intelligence.qwen.provider import fail
        fail('EGRESS_SYSTEMROOT_REQUIRED')
    return {'SystemRoot': root}


class NativeTransport:
    """Application allowlist process; does not alter R1B kernel isolation.

    Secret travels through anonymous stdin, never argv/environment/logs. This
    adapter is deployed with the repository infrastructure, not a standalone
    pure-domain wheel. There is no implicit credential lookup or background job.
    """
    def __init__(self, *, peer_pins=None):
        self.peer_pins = peer_pins

    async def post(self, config, key, body, timeout_ms):
        from vrae.intelligence.qwen.provider import MAX_RESPONSE, fail, strict_json
        peers = None
        if self.peer_pins is not None:
            # Runtime root resolves the official host before dropping privileges.
            # No writable hosts file or AI DNS permission is required.
            fd = os.open(self.peer_pins, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                s = os.fstat(fd)
                if (not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_gid != 10008
                        or stat.S_IMODE(s.st_mode) != 0o440 or s.st_size > 4096):
                    fail('MODEL_DNS_REFUSED')
                pins = json.loads(os.read(fd, 4097))
                if pins['host'] != config.host:
                    fail('MODEL_DNS_REFUSED')
                peers = pins['addresses']
            finally:
                os.close(fd)
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-I', '-X', 'utf8', str(Path(__file__).with_name('egress.py')),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=child_environment())
        document = {'workspace': config.workspace_id, 'key': key,
                    'body': body, 'timeout_ms': timeout_ms}
        if peers is not None:
            document['pinned_addresses'] = peers
        envelope = encode(document)
        try:
            raw, _ = await asyncio.wait_for(process.communicate(envelope), timeout_ms / 1000)
            if process.returncode != 0 or len(raw) > MAX_RESPONSE * 2:
                fail('EGRESS_FAILED')
            reply = strict_json(raw)
            if set(reply) != {'status', 'body'}:
                fail('EGRESS_FAILED')
            return reply['status'], reply['body'].encode('utf-8')
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()
