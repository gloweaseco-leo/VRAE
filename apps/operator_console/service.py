"""Read-only use cases behind trusted-call authority and repository ports."""
from contextlib import contextmanager
from .contracts import STAGES, TEST_ONLY, TaskRecord, canonical, filters, identifier, refuse
from .ports import NativePreparation, ReadAuthority, TaskRepository
from .targets import ReviewTargetBridge


class ConsoleService:
    def __init__(self, authority: ReadAuthority, repository: TaskRepository, native: NativePreparation):
        self.authority, self.repository, self.native = authority, repository, native
        self.targets = ReviewTargetBridge()

    def _pg(self):
        from .pg_read import PgReadRepository
        return self.repository if type(self.repository) is PgReadRepository else None

    @contextmanager
    def request(self, context):
        pg=self._pg()
        if pg is None:
            yield
        else:
            with pg.request(self._scope(context)):
                yield

    def _scope(self, context):
        scope = self.authority.require(context)
        if scope.source_kind != TEST_ONLY:
            refuse('UNAUTHORIZED')  # Real authority adapters are not implemented in C0.
        return scope

    def _task(self, scope, task_id):
        identifier(task_id)
        if task_id not in scope.assigned_ids:
            refuse('UNAUTHORIZED')  # Before repository lookup/existence disclosure.
        task = TaskRecord.parse(self.repository.task(task_id)).document
        if (task['task_id'] != task_id or task['audit_run']['tenant_id'] != scope.tenant_id
                or task['owner_scope'] != scope.owner_scope):
            refuse('UNAUTHORIZED')
        return task

    def pool(self, context, stage='', query=''):
        scope = self._scope(context)
        stage, term = filters(stage, query)
        rows = self.repository.assigned(scope)
        if len(rows) > 100:
            refuse('INVALID_DTO')
        tasks = []
        for row in rows:
            record = TaskRecord.parse(row).document
            task = self._task(scope, record['task_id'])
            if (not stage or task['stage']==stage) and (not term or term in (task['title']+' '+task['task_id']).casefold()):
                tasks.append(task)
        order = list(STAGES)
        if self._pg():
            ready=next((t for t in tasks if t['report_case'] is not None),None)
            if ready is not None:
                self.targets.verify_assignment(ready)
                self.repository.probe(scope,ready)
            else:
                self.repository.authorize_metadata(scope)
        return sorted(tasks, key=lambda t:(order.index(t['stage']),t['task_id']))[:40]

    def detail(self, context, task_id):
        scope = self._scope(context)
        task=self._task(scope, task_id)
        if self._pg():
            if task['report_case'] is not None:
                self.targets.verify_assignment(task)
            self.repository.probe(scope,task)
        return task

    def review(self, context, task_id, version, draft_ref):
        scope = self._scope(context)
        task = self._task(scope, task_id)
        if task['stage'] not in ('DRAFT_READY','REVIEW_REQUIRED','COVERAGE_ONLY'):
            refuse('NOT_READY')
        if type(version) is not int or version != task['report_version'] or draft_ref != task['report_pins']['expected_draft_ref']:
            refuse('STALE_VERSION')
        self.targets.verify_assignment(task)
        if self._pg():
            dossier,source=self.repository.dossier(scope,task,self.native)
        else:
            source = self.repository.report_source(task['report_case'])
            dossier = self.native.prepare(task['report_case'], source)
        d = dossier['document']
        if (task['report_pins'] != dossier['held'] or d['metadata']['version'] != version
                or d['scope']['tenant_id'] != scope.tenant_id or d['scope']['run_id'] != task['audit_run']['run_id']
                or d['draft_ref'] != draft_ref):
            refuse('SOURCE_INTEGRITY')
        artifacts = dossier['_artifacts']
        if canonical(d) != artifacts['document']:
            refuse('SOURCE_INTEGRITY')
        dossier['review_target'] = self.targets.prepare(task,artifacts['document'],artifacts['html'],
                                                       canonical(source)).document
        return task, dossier

    def target(self, context, task_id, version, draft_ref, expected_digest):
        task,dossier = self.review(context,task_id,version,draft_ref)
        if expected_digest != dossier['review_target']['target_digest']:
            refuse('STALE_VERSION')
        return task,dossier

    def evidence(self, context, task_id, version, draft_ref, index, expected_digest=None):
        task, dossier = (self.target(context,task_id,version,draft_ref,expected_digest)
                         if expected_digest is not None else self.review(context,task_id,version,draft_ref))
        if type(index) is not int or not 0 <= index < len(dossier['evidence']):
            refuse('INVALID_INPUT')
        return task, dossier, dossier['evidence'][index]

    def mutate(self, context, action, payload=None):
        self._scope(context)
        refuse('NOT_IMPLEMENTED')
