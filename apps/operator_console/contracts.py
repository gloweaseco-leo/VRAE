"""Versioned presentation DTOs, separate from frozen native contracts."""
from dataclasses import dataclass
import json
import re
import unicodedata

from vrae.domain.contracts import validate_contract

DTO_VERSION = 'operator-console-read-0.1'
TEST_ONLY = 'SYNTHETIC_TEST_ONLY'
STAGES = {
    'PENDING_ADMISSION': ('待准入', {'CREATED', 'POLICY_CHECK', 'QUEUED'}),
    'BLOCKED': ('范围 / 来源阻断', {'POLICY_BLOCKED', 'ACCESS_BLOCKED', 'INSUFFICIENT_EVIDENCE', 'MODEL_INVALID'}),
    'RUNNING': ('采集中', {'FETCHING'}),
    'EVIDENCE_READY': ('证据就绪', {'EVIDENCE_READY', 'RULED'}),
    'DRAFT_READY': ('草稿就绪', {'DRAFT_READY'}),
    'REVIEW_REQUIRED': ('待只读核对', {'REVIEW_REQUIRED'}),
    'COVERAGE_ONLY': ('零问题 · 范围待核对', {'RULED'}),
    'FAILED': ('运行失败', {'FAILED', 'CANCELLED'}),
}


class ConsoleError(ValueError):
    """Fixed codes only; no protected fields in denial messages."""


def refuse(code='INVALID_INPUT'):
    raise ConsoleError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def text(value, limit=160):
    if (type(value) is not str or len(value) > limit or
            any(ord(c) < 32 or ord(c) in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)) for c in value)):
        refuse()
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError:
        refuse()
    return value


def identifier(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,95}', value):
        refuse()
    return value


@dataclass(frozen=True)
class TaskRecord:
    """Immutable DTO bytes; parse at the repository/application boundary."""
    payload: bytes

    @classmethod
    def parse(cls, value):
        try:
            required = {'dto_version', 'source_kind', 'task_id', 'owner_scope', 'title', 'audit_run',
                        'stage', 'coverage_reason', 'report_case', 'report_version', 'report_pins'}
            if type(value) is not dict or set(value) != required or value['dto_version'] != DTO_VERSION:
                refuse('INVALID_DTO')
            if value['source_kind'] != TEST_ONLY or value['stage'] not in STAGES:
                refuse('INVALID_DTO')
            validate_contract('AuditRun', value['audit_run'])
            if value['audit_run']['status'] not in STAGES[value['stage']][1]:
                refuse('INVALID_DTO')
            identifier(value['task_id'])
            identifier(value['owner_scope'])
            text(value['title'])
            text(value['coverage_reason'], 1000)
            if value['report_case'] not in (None, '404', '200'):
                refuse('INVALID_DTO')
            ready = value['stage'] in ('DRAFT_READY', 'REVIEW_REQUIRED', 'COVERAGE_ONLY')
            if ready != (value['report_case'] is not None):
                refuse('INVALID_DTO')
            if ready:
                if type(value['report_version']) is not int or value['report_version'] < 1 or type(value['report_pins']) is not dict:
                    refuse('INVALID_DTO')
                held = value['report_pins']
                if (set(held) != {'pins','expected_draft_ref','expected_html_sha256','expected_issue_count'}
                        or type(held['pins']) is not dict
                        or type(held['expected_issue_count']) is not int
                        or not 0 <= held['expected_issue_count'] <= 3
                        or type(held['expected_draft_ref']) is not str
                        or not re.fullmatch(r'rd-[0-9a-f]{64}',held['expected_draft_ref'])
                        or type(held['expected_html_sha256']) is not str
                        or not re.fullmatch(r'[0-9a-f]{64}',held['expected_html_sha256'])):
                    refuse('INVALID_DTO')
                if (value['report_case'] == '200') != (value['stage'] == 'COVERAGE_ONLY'):
                    refuse('INVALID_DTO')
            elif value['report_pins'] is not None or value['report_version'] is not None:
                refuse('INVALID_DTO')
            return cls(canonical(value))
        except ConsoleError:
            raise
        except Exception:
            raise ConsoleError('INVALID_DTO') from None

    @property
    def document(self):
        return json.loads(self.payload)


def filters(stage='', query=''):
    if type(stage) is not str or (stage and stage not in STAGES):
        refuse()
    text(query, 80)
    if '://' in query or query.startswith(('//', '/', '\\')):
        refuse()
    return stage, unicodedata.normalize('NFC', query).strip().casefold()
