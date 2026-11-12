"""Read-only D1/D2 integration. Independent holds never come from the DTO."""
from dataclasses import dataclass
import json
from pathlib import Path

from vrae.reviewing import (ReviewError, ReviewTarget, SyntheticTrust, build_target,
                           validate_target, prepare_production_review)
from vrae.reviewing.canonical import canonical, parse, SOURCE_LIMIT

from .contracts import ConsoleError, TEST_ONLY, refuse

VERSION='operator-console-target-read-0.1'
CONDITIONS=['真实自然人身份及任务授权尚未接入', '受保护的不可变对象存储及最新版本账本尚未接入',
            '持久审核事务、审计和 outbox 尚未接入', '审批、ShareGrant 与客户访问未开放']


@dataclass(frozen=True)
class TargetRead:
    """Validated projection bytes, not an approval or authority capability."""
    payload: bytes

    @property
    def document(self):
        return parse(self.payload)


class ReviewTargetBridge:
    def __init__(self):
        # Frozen accepted D1/D2 records; no caller-supplied trust/pin switch.
        self._pins=json.loads(Path(__file__).with_name('review-target-pins.json').read_text(encoding='utf-8'))

    def _held(self, case):
        if case not in ('404','200'):
            refuse('SOURCE_INTEGRITY')
        return self._pins['cases'][case]

    def _trust(self, case):
        row=self._held(case)
        return SyntheticTrust(self._pins['authority'],canonical(row['held']),
                              canonical(row['policy']),row['artifact_ref'])

    def _projection(self, task, target, document):
        t=target.document
        if (task['source_kind']!=TEST_ONLY or task['audit_run']['tenant_id']!=t['tenant_id']
                or task['audit_run']['run_id']!=t['run_id'] or type(task['report_version']) is not int
                or task['report_version']!=t['report_version']
                or task['report_pins']['expected_draft_ref']!=t['draft_ref']):
            refuse('SOURCE_INTEGRITY')
        d=parse(document,limit=SOURCE_LIMIT)
        return {'dto_version':VERSION,'source_kind':TEST_ONLY,'state':'READ_ONLY_NOT_AUTHORIZED',
            'task_id':task['task_id'],'owner_scope':task['owner_scope'],'tenant_id':t['tenant_id'],
            'latest_report_version':self._held(task['report_case'])['expected_target']['report_version'],
            'latest_version_authority':'HELD_SYNTHETIC_FIXTURE_ONLY_NOT_PRODUCTION_LEDGER',
            'target_digest':target.target_digest,'target':t,
            'native_h0':t['native_content_hash'],'native_report_version':d['native_report_version'],
            'limitations':d['limitations'],'recorded_coverage':d['recorded_coverage'],
            'examined_pages':d['examined_pages'],'missing_conditions':CONDITIONS}

    def prepare(self, task, document, html, source):
        try:
            target=build_target(document,html,source,trust=self._trust(task['report_case']))
            projection=self._projection(task,target,document)
            return self.load(task,canonical(projection),document,html,source)
        except ConsoleError:
            raise
        except (ReviewError,ValueError,TypeError,KeyError):
            refuse('SOURCE_INTEGRITY')

    def load(self, task, payload, document, html, source):
        """Consumer boundary: revalidate the actual target and whole projection.

        A syntactically valid/rehashed target supplied by a future read port is
        not trusted. Original held target, policy and object pins remain outside it.
        """
        try:
            value=parse(payload)
            target=validate_target(ReviewTarget(canonical(value['target'])),document,html,source,
                                   trust=self._trust(task['report_case']))
            row=self._held(task['report_case'])
            if target.target_digest!=row['expected_target_digest'] or target.document!=row['expected_target']:
                refuse('SOURCE_INTEGRITY')
            expected=self._projection(task,target,document)
            if canonical(value)!=canonical(expected):
                refuse('SOURCE_INTEGRITY')
            return TargetRead(canonical(expected))
        except ConsoleError:
            raise
        except (ReviewError,ValueError,TypeError,KeyError):
            refuse('SOURCE_INTEGRITY')


class FutureRealReviewAdapter:
    """No simulation or identity inference: accepted production port denies ALL."""
    def prepare(self, *args, **kwargs):
        return prepare_production_review(*args,**kwargs)
