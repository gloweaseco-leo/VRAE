"""Dedicated bounded egress process, kept outside the network-free domain tree."""
import asyncio
from pathlib import Path
import sys

from vrae.intelligence.common import encode


class NativeTransport:
    """Application allowlist process; does not alter R1B kernel isolation.

    Secret travels through anonymous stdin, never argv/environment/logs. This
    adapter is deployed with the repository infrastructure, not a standalone
    pure-domain wheel. There is no implicit credential lookup or background job.
    """
    async def post(self, config, key, body, timeout_ms):
        from vrae.intelligence.qwen.provider import MAX_RESPONSE, fail, strict_json
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-I', '-X', 'utf8', str(Path(__file__).with_name('egress.py')),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env={})
        envelope = encode({'workspace': config.workspace_id, 'key': key,
                           'body': body, 'timeout_ms': timeout_ms})
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
