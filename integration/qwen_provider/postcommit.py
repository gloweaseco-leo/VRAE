"""Replay PR162 draft bytes against independently held post-COMMIT input pins.

This is NOT a database/current-authority check or an S3 Context factory. The
authenticated C3 caller must obtain committed bytes and pins separately and
retain/recheck current authorization. No timestamps or source modes are invented.
"""
import base64
from dataclasses import asdict, dataclass
import hashlib
import re

from vrae.evidence import EvidencePack
from vrae.intelligence.common import encode
from vrae.intelligence.qwen.provider import QwenError, strict_json
from vrae.l2.native import NativeSource, NativeTask

MAX_ARTIFACT = 8_000_000
TASK_FIELDS = ('tenant_id', 'request_id', 'run_id', 'job_id', 'event_id', 'source_ref')
FIELDS = {'task', 'pack', 'objects_base64', 'diagnosis', 'native_document', 'version',
          'display_hash', 'pack_ref', 'diagnosis_ref', 'source_bundle_sha256',
          'source_access_mode', 'diagnostic_depth', 'ai_state', 'publication',
          'authority', 'external_release'}


@dataclass(frozen=True)
class InputPins:
    """Internal expectations, never browser/model fields or access credentials."""
    task: NativeTask
    artifact_sha256: str
    report_content_hash: str
    display_hash: str


def replay_input(raw: bytes, *, pins: InputPins) -> tuple[EvidencePack, NativeSource]:
    """Reconstitute original immutable inputs; never dispatch or approve anything.

    An accepted PUBLIC_READONLY_CAPTURE source remains that exact mode. Existing
    S3 CompletionPins still refuse it; this helper cannot grant a model context.
    All refusals use one fixed code without reflecting private artifact content.
    """
    try:
        if (type(raw) is not bytes or not 1 <= len(raw) <= MAX_ARTIFACT
                or type(pins) is not InputPins or type(pins.task) is not NativeTask
                or pins.task.source_access_mode != 'PUBLIC_READONLY_CAPTURE'
                or any(type(h) is not str or re.fullmatch('[0-9a-f]{64}', h) is None
                       for h in (pins.artifact_sha256, pins.report_content_hash, pins.display_hash))
                or hashlib.sha256(raw).hexdigest() != pins.artifact_sha256):
            raise ValueError
        d = strict_json(raw)
        task = asdict(pins.task)
        if (type(d) is not dict or set(d) not in (FIELDS, FIELDS | {'source_authority'})
                or encode(d['task']) != encode({k: task[k] for k in TASK_FIELDS})
                or encode(d['native_document']['native_context']) != encode(task)
                or d['pack_ref'] != pins.task.native_pack_ref
                or d['diagnosis_ref'] != pins.task.diagnosis_ref
                or d['source_bundle_sha256'] != pins.task.source_bundle_sha256
                or d['source_access_mode'] != 'L1' or d['diagnostic_depth'] != 'L2'
                or d['ai_state'] != 'NO_MODEL' or d['publication'] != 'UNPUBLISHED'
                or d['authority'] != 'GENERATED_DRAFT_NOT_HUMAN_APPROVED'
                or d['external_release'] is not False):
            raise ValueError
        objects = {k: base64.b64decode(v, validate=True)
                   for k, v in d['objects_base64'].items()}
        pack = EvidencePack(encode(d['pack']), tuple(sorted(objects.items())))
        source = NativeSource(pack, d['diagnosis'], held=pins.task)
        view = source.read()
        if (encode(view.document) != encode(d['native_document'])
                or encode(view.version) != encode(d['version'])
                or view.version['content_hash'] != pins.report_content_hash
                or view.display_hash != pins.display_hash or d['display_hash'] != pins.display_hash):
            raise ValueError
        return pack, source
    except Exception:
        raise QwenError('POST_COMMIT_INPUT_REPLAY_DENIED') from None
