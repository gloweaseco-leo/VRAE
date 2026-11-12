"""Read-side integration seam. No D1/D2 or RA4A/B API is assumed."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    owner_scope: str
    assigned_ids: frozenset[str]
    source_kind: str


class ReadAuthority(Protocol):
    def require(self, context: object) -> Scope: ...


class TaskRepository(Protocol):
    def assigned(self, scope: Scope) -> list[dict]: ...
    def task(self, task_id: str) -> dict: ...
    def report_source(self, case: str) -> dict: ...


class NativePreparation(Protocol):
    def prepare(self, case: str, source: dict) -> dict: ...
