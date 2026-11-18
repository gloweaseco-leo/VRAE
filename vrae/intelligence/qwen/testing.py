"""Explicit no-socket protocol fake. This module never produces a live-pass receipt."""
import asyncio
from dataclasses import dataclass, field
import json


@dataclass
class FakeTransport:
    response: object
    status: int = 200
    timeout: bool = False
    calls: int = 0
    bodies: list = field(default_factory=list, repr=False)

    async def post(self, config, key, body, timeout_ms):
        self.calls += 1
        self.bodies.append(json.loads(json.dumps(body)))
        if self.timeout:
            await asyncio.sleep(timeout_ms / 1000 + 1)
        raw = self.response if type(self.response) is bytes else json.dumps(self.response).encode()
        return self.status, raw
