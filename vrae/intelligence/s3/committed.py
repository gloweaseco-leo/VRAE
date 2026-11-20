"""Internal capture-input timing pins; original C3 current authority is mandatory.

These objects are not transport credentials. Only the trusted server adapter
constructs them after reading the original committed_input port. The callback
must re-open that port, including its current signature/PG checks, on every use.
"""
from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Callable

from vrae.l2.native import NativeSource, NativeTask
from .offline import CompletionPins, deny


@dataclass(frozen=True)
class CommittedCompletionPins(CompletionPins):
    transaction_id: int
    artifact_sha256: str
    current_input_ref: str
    recheck: Callable[[NativeSource, datetime], None] = field(repr=False, compare=False)

    response_language: str = 'en'

    def check(self, source, now):
        times = (now, self.lease_started_at, self.lease_expires_at,
                 self.worker_completed_at, self.authority_expires_at)
        if (self.response_language not in ('zh', 'en')
                or type(source) is not NativeSource or type(self.task) is not NativeTask
                or source.held != self.task
                or self.task.source_access_mode != 'PUBLIC_READONLY_CAPTURE'
                or any(type(t) is not datetime or t.utcoffset() is None for t in times)
                or (self.lease_expires_at - self.lease_started_at).total_seconds() != 30
                or not self.lease_started_at <= self.worker_completed_at <= self.lease_expires_at
                or type(self.transaction_id) is not int or self.transaction_id <= 0
                or any(type(h) is not str or re.fullmatch('[0-9a-f]{64}', h) is None
                       for h in (self.artifact_sha256, self.current_input_ref))
                or source.read().version['content_hash'] != self.report_content_hash):
            deny('POST_COMMIT_BINDING_INVALID')
        if now < self.lease_expires_at:
            deny('WORKER_LEASE_NOT_ENDED')
        if now >= self.authority_expires_at:
            deny('CURRENT_AUTHORITY_EXPIRED')
        # A copied descriptor or locally plausible time cannot authorize use.
        self.recheck(source, now)
