"""Existing ConsoleService/SSR ports with signed-session Reviewer reads."""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

from .contracts import TEST_ONLY, canonical, refuse
from .ports import Scope
from .service import ConsoleService


class _Authority:
    def __init__(self, owner):
        self.owner = owner

    def require(self, context):
        state = self.owner.current.get()
        if (
            state is None
            or state[0] != context
            or self.owner.sessions.require(context) is not state[1]
        ):
            refuse("UNAUTHORIZED")
        session = state[1]
        return Scope(
            session.binding.location.tenant,
            "ops-synthetic",
            frozenset([session.task_id]),
            TEST_ONLY,
        )


class _Repository:
    def __init__(self, owner):
        self.owner = owner

    def _state(self):
        state = self.owner.current.get()
        if state is None:
            refuse("UNAUTHORIZED")
        return state

    def assigned(self, scope):
        _, session, snapshot = self._state()
        if scope.assigned_ids != frozenset([session.task_id]):
            refuse("UNAUTHORIZED")
        return [deepcopy(self.owner.tasks[snapshot["pin"].case])]

    def task(self, task_id):
        _, session, snapshot = self._state()
        if session.task_id != task_id:
            refuse("UNAUTHORIZED")
        return deepcopy(self.owner.tasks[snapshot["pin"].case])

    def report_source(self, case):
        _, _, snapshot = self._state()
        if case != snapshot["pin"].case:
            refuse("UNAUTHORIZED")
        return deepcopy(snapshot["source"])


class _Native:
    def __init__(self, owner):
        self.owner = owner

    def prepare(self, case, source):
        state = self.owner.current.get()
        if (
            state is None
            or state[2]["pin"].case != case
            or canonical(source) != canonical(state[2]["source"])
        ):
            refuse("SOURCE_INTEGRITY")
        # Already loaded by NativeVerifier.load_original from actual BYTEA.
        # There is intentionally no call to native.prepare/build_draft here.
        return deepcopy(state[2]["dossier"])


class SignedConsoleService(ConsoleService):
    def __init__(self, sessions, tasks):
        self.sessions, self.tasks = sessions, deepcopy(tasks)
        self.current = ContextVar("b5a_current_verified_original", default=None)
        super().__init__(_Authority(self), _Repository(self), _Native(self))

    @contextmanager
    def request(self, context):
        if self.current.get() is not None:
            refuse("UNAUTHORIZED")
        session = self.sessions.require(context)

        def current():
            if self.sessions.require(context) is not session:
                refuse("UNAUTHORIZED")

        reader = self.sessions.readers[session.binding.db_role]
        with reader.request(session.binding, recheck=current) as snapshot:
            token = self.current.set((context, session, snapshot))
            try:
                yield
                current()
            finally:
                self.current.reset(token)
