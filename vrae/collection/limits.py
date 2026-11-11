"""Wall-clock, request, byte, page and per-host limits include redirects and robots."""
import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
import math
import threading
import time
from typing import Awaitable, Callable, TypeVar

from .errors import CollectionError
from .policy import SourceAccess

T = TypeVar("T")


@dataclass(frozen=True)
class Limits:
    max_pages: int = 8
    max_bytes: int = 1_500_000
    max_redirects: int = 5
    request_seconds: float = 10
    task_seconds: float = 120
    interval_seconds: float = 1
    max_requests: int = 64
    max_total_bytes: int = 12_065_536

    def __post_init__(self):
        bounds = {"max_pages": (1, 8), "max_bytes": (1, 1_500_000),
                  "max_redirects": (0, 5), "max_requests": (1, 64),
                  "max_total_bytes": (1, 12_065_536), "request_seconds": (0.01, 10),
                  "task_seconds": (0.01, 120), "interval_seconds": (0.01, 120)}
        for field, (low, high) in bounds.items():
            value = getattr(self, field)
            if isinstance(value, bool) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError("Invalid collection limit")
            if field.startswith("max_") and not isinstance(value, int):
                raise ValueError("Integral limit required")


class HostLeases:
    _active: set[str] = set()
    _lock = threading.Lock()

    @classmethod
    @contextmanager
    def claim(cls, host: str):
        with cls._lock:
            if host in cls._active:
                raise CollectionError("HOST_BUSY")
            cls._active.add(host)
        try:
            yield
        finally:
            with cls._lock:
                cls._active.remove(host)


class Budget:
    def __init__(self, limits: Limits, access: SourceAccess,
                 clock: Callable[[], float] = time.monotonic):
        self.limits, self.access, self.clock = limits, access, clock
        self.deadline = clock() + limits.task_seconds
        self.requests = self.bytes = self.pages = 0
        self.cancelled = False
        self.run_id: str | None = None
        self.next_request = clock()
        self.interval = limits.interval_seconds

    def cancel(self):
        self.cancelled = True

    def check(self):
        if self.cancelled:
            raise CollectionError("CANCELLED")
        if self.clock() >= self.deadline:
            raise CollectionError("TIMEOUT")
        self.access.check(self.access.start_url)

    async def run(self, operation: Awaitable[T], timeout: float | None = None) -> T:
        task = asyncio.ensure_future(operation)
        end = min(self.deadline, self.clock() + (timeout or self.limits.task_seconds))
        try:
            while True:
                self.check()
                if self.clock() >= end:
                    raise CollectionError("TIMEOUT")
                done, _ = await asyncio.wait({task}, timeout=min(0.05, end - self.clock()))
                if done:
                    self.check()
                    return task.result()
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def before_request(self):
        self.check()
        if self.requests >= self.limits.max_requests:
            raise CollectionError("LIMIT_EXCEEDED")
        delay = self.next_request - self.clock()
        if delay > 0:
            await self.run(asyncio.sleep(delay))
        self.requests += 1
        self.next_request = self.clock() + self.interval

    def consume(self, count: int):
        self.check()
        self.bytes += count
        if self.bytes > self.limits.max_total_bytes:
            raise CollectionError("LIMIT_EXCEEDED")

    def page(self):
        self.check()
        cap = min(self.limits.max_pages, 5 if self.access.audit["audit_mode"] == "L0" else 8)
        if self.pages >= cap:
            raise CollectionError("LIMIT_EXCEEDED")
        self.pages += 1
