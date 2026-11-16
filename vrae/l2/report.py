"""Pinned L2 result adapter. Replays source bytes; reuses V1 report contracts.

Byte binding is not a claim of independent factual truth or legal source rights.
The producer and source mode remain explicit. No uploaded document supplies trust.
"""
from dataclasses import dataclass
import copy
import hashlib
from pathlib import Path
import re
from typing import NoReturn

from vrae.domain.contracts import validate_contract
from vrae.domain.reviews import report_content_hash
from vrae.reviewing.canonical import canonical, parse

CONTRACT = 'vrae.l2.deep-result.v1'
TASKS = ('DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL')


class L2Denied(ValueError):
    pass


def deny(code='L2_REQUEST_DENIED') -> NoReturn:
    raise L2Denied(code) from None


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return canonical(value, limit=2_000_000)


def bounded(value, maximum=4000):
    if type(value) is not str or not value.strip() or len(value) > maximum:
        deny('L2_INVALID_TEXT')
    if any(ord(c) < 32 and c not in '\n\t' for c in value):
        deny('L2_INVALID_TEXT')
    return value


@dataclass(frozen=True)
class DeepReport:
    payload: bytes
    source_digest: str

    @property
    def document(self):
        return parse(self.payload, limit=2_000_000)

    @property
    def display_hash(self):
        return sha(self.payload)

    @property
    def findings(self):
        d = self.document
        meta = d['meta']
        rows = []
        for f in d['findings']:
            rows.append({'schema_version':'1.0', 'tenant_id':meta['tenant_id'],
                'finding_id':f['id'], 'run_id':meta['run_id'], 'observation_id':f['id'],
                'kind':f['kind'], 'evidence_ids':f['evidence_ids'], 'statement':f['statement'],
                'buyer_task':f['task'], 'severity':None if f['kind']=='UNKNOWN' else f['severity'],
                'rule_version':d['producer']['version']})
        for row in rows:
            validate_contract('Finding', row)
        return rows

    @property
    def version(self):
        d = self.document
        m = d['meta']
        row = {'schema_version':'1.0', 'tenant_id':m['tenant_id'], 'report_id':m['report_id'],
            'report_version_id':m['report_id']+'.v'+str(m['version']), 'run_id':m['run_id'],
            'version':m['version'], 'content_hash':'0'*64, 'status':'REVIEW_REQUIRED',
            'finding_ids':[f['finding_id'] for f in self.findings], 'created_by':m['created_by'],
            'created_at':m['created_at'], 'approved_by':None, 'approved_at':None, 'audit_mode':'L2'}
        row['content_hash'] = report_content_hash(row, self.findings)
        validate_contract('ReportVersion', row)
        return row


class OfflineSource:
    def __init__(self, root, expected_sha256):
        self.root = Path(root).resolve()
        if not re.fullmatch('[a-f0-9]{64}', expected_sha256):
            deny('L2_PIN_REQUIRED')
        self.expected = expected_sha256

    def read(self):
        raw = (self.root/'result.json').read_bytes()
        if sha(raw) != self.expected:
            deny('L2_SOURCE_CHANGED')
        d = parse(raw, limit=2_000_000)
        self.validate(d)
        return DeepReport(encoded(d), self.expected)

    def validate(self, d):
        held_raw = (self.root/'result.json').read_bytes()
        if sha(held_raw) != self.expected:
            deny('L2_SOURCE_CHANGED')
        held = parse(held_raw, limit=2_000_000)
        # A revision may change blueprint proposals and version authorship, not
        # evidence, observations, priorities, industry inputs or scope silently.
        normalized = copy.deepcopy(d)
        for key in ('version','created_by','created_at'):
            normalized['meta'][key] = held['meta'][key]
        if len(normalized['blueprint']) != len(held['blueprint']):
            deny('L2_SOURCE_FACTS_IMMUTABLE')
        for item, original in zip(normalized['blueprint'], held['blueprint']):
            item['change'] = original['change']
        if encoded(normalized) != encoded(held):
            deny('L2_SOURCE_FACTS_IMMUTABLE')
        if d['contract'] != CONTRACT or d['meta']['source_mode'] not in ('SYNTHETIC_OFFLINE','PERMITTED_OFFLINE'):
            deny('L2_UNSUPPORTED_RESULT_CONTRACT')
        validate_contract('IndustryPack', d['industry_pack'])
        if d['industry_pack']['tenant_id'] != d['meta']['tenant_id'] or d['meta']['version'] < 1:
            deny('L2_SCOPE_MISMATCH')
        if d['industry_pack_sha256'] != sha(encoded(d['industry_pack'])):
            deny('L2_INDUSTRY_PACK_CHANGED')
        if d['producer']['assurance'] != 'OFFLINE_AUTHORED_SOURCE_BOUND_NOT_NATIVE_GUARD':
            deny('L2_PRODUCER_NOT_ACCEPTED')
        if {j['task'] for j in d['journey']} != set(TASKS) or len(d['journey']) != 5:
            deny('L2_JOURNEY_INCOMPLETE')
        if not 1 <= len(d['snapshots']) <= 40 or not 1 <= len(d['findings']) <= 64:
            deny('L2_RESULT_BOUND')
        snapshots = {}
        for s in d['snapshots']:
            path = (self.root/s['body_file']).resolve()
            if not path.is_relative_to(self.root) or path.is_symlink() or s['id'] in snapshots:
                deny('L2_SOURCE_PATH_DENIED')
            content = path.read_bytes()
            if len(content) > 1_000_000 or sha(content) != s['sha256']:
                deny('L2_SOURCE_CHANGED')
            if not s['url'].startswith('https://') or not s['captured_at']:
                deny('L2_SOURCE_LOCATION_REQUIRED')
            snapshots[s['id']] = content
        evidence = {}
        for item in d['evidence']:
            content = snapshots.get(item['snapshot_id'])
            start, end = item['byte_start'], item['byte_end']
            if (content is None or type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(content) or item['id'] in evidence
                    or content[start:end] != item['quote'].encode('utf-8')
                    or sha(content[start:end]) != item['sha256']):
                deny('L2_EVIDENCE_BINDING_DENIED')
            evidence[item['id']] = item
        found = {}
        for f in d['findings']:
            if f['id'] in found or f['task'] not in TASKS or f['kind'] not in ('OBSERVATION','HYPOTHESIS','UNKNOWN'):
                deny('L2_FINDING_INVALID')
            if f['kind']=='UNKNOWN':
                if f['evidence_ids'] or f['priority']!='UNRANKED' or f['severity'] is not None:
                    deny('L2_UNKNOWN_CANNOT_BECOME_FAILURE')
            elif not f['evidence_ids'] or not set(f['evidence_ids']) <= evidence.keys():
                deny('L2_EVIDENCE_REQUIRED')
            if f['priority'] not in ('P1','P2','P3','UNRANKED'):
                deny('L2_PRIORITY_INVALID')
            for key in ('title','statement','scope','buyer_impact','priority_basis','uncertainty','recommendation','recheck'):
                bounded(f[key])
            found[f['id']] = f
        for j in d['journey']:
            if not set(j['finding_ids']) <= found.keys():
                deny('L2_JOURNEY_REFERENCE_INVALID')
        blueprints = set()
        for b in d['blueprint']:
            if (b['id'] in blueprints or not b['finding_ids'] or not set(b['finding_ids']) <= found.keys()
                    or all(found[k]['kind']=='UNKNOWN' for k in b['finding_ids'])
                    or b['service_fit'] not in ('STANDARD_CANDIDATE','CUSTOM_ASSESSMENT')):
                deny('L2_BLUEPRINT_REFERENCE_INVALID')
            if not b['acceptance'] or not b['customer_inputs']:
                deny('L2_BLUEPRINT_NOT_ACTIONABLE')
            blueprints.add(b['id'])
        for key in ('summary','service_catalog','limitations','buyer'):
            if not d[key]:
                deny('L2_CONTEXT_REQUIRED')
        # Reuse strict V1 finding/report-version schemas and canonical hash.
        view = DeepReport(encoded(d), self.expected)
        view.version

    def revision(self, previous, changes, actor_id, created_at):
        d = copy.deepcopy(previous.document)
        if not changes or set(changes) - {b['id'] for b in d['blueprint']}:
            deny('L2_REVISION_SCOPE_DENIED')
        for b in d['blueprint']:
            if b['id'] in changes:
                b['change'] = bounded(changes[b['id']], 2000)
        d['meta']['version'] += 1
        d['meta']['created_by'] = actor_id
        d['meta']['created_at'] = created_at
        self.validate(d)
        return DeepReport(encoded(d), self.expected)
