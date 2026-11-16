"""Trusted C2 production adapter: accepted C1 replay -> existing L2 report.

Inputs come ONLY from C3's held signed current-task context. Neither a pack,
hash, dataclass nor this adapter grants task access or authenticates a Worker.
All replayed inputs are frozen; reconstitution after restart replays C1 again.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import copy
import re

from vrae.evidence import EvidencePack
from vrae.industry.l2_v1 import verify
from vrae.reviewing.canonical import canonical, parse
from .native_business import project
from .report import DeepReport, bounded, deny, encoded, sha, NATIVE_CONTRACT, revise_proposals

ASSURANCE='C1_NATIVE_EVIDENCE_GUARD_REPLAYED_C2_BUSINESS_PROJECTION_V1'
GUARANTEE='vrae.l2.native-producer-guarantee.v1'
VERSION='c2-l2-native-1.0.0'


@dataclass(frozen=True)
class NativeTask:
    """Independent server-held task/ref expectations, never browser JSON.

    C3 owns authenticating the real APP/Worker association and its live deadline.
    No task, job or assignment is generated here.
    """
    tenant_id: str
    request_id: str
    run_id: str
    job_id: str
    event_id: str
    source_ref: str
    native_pack_ref: str
    industry_ref: str
    diagnosis_ref: str
    source_bundle_sha256: str
    source_access_mode: str
    created_at: str


def evidence_projection(pack,data):
    doc=pack.document
    sources={s['source_ref']:s for s in doc['sources']}
    snapshots=[]
    for s in doc['snapshots']:
        original=sources[s['source_ref']]['document']
        page=original['pages'][int(s['locator'].split('/')[2])] if s['capture_mode']=='HTTP' else None
        for token in s['locator'].split('/')[1:]:
            original=original[int(token)] if isinstance(original,list) else original[token]
        snapshots.append({'id':s['snapshot_ref'],'url':s['url'],'captured_at':s['observed_at'],
            'http_status':page['http_status'] if page is not None else None,
            'content_type':original.get('content_type','UNKNOWN'),
            'source_ref':s['source_ref'],'locator':s['locator'],'original_snapshot':s})
    evs={e['evidence_ref']:e for e in doc['evidence']}
    result=[]
    for e in doc['evidence']:
        body=pack.objects.get(e['blob_ref'])
        result.append({'id':e['evidence_ref'],'snapshot_id':e['snapshot_ref'],
            'source_ref':e['source_ref'],'locator':e['locator'],'blob_ref':e['blob_ref'],
            'sha256':e['content_sha256'],'bytes':len(body) if body is not None else None,
            'quote':'','representation':'WHOLE_OBJECT_REFERENCE_NOT_INLINE_PRIVATE_BODY',
            'native_evidence':e})
    for fact in data['source_facts']:
        source=fact['source']
        c=source['citation']
        e=evs[c['evidence_ref']]
        body=pack.objects.get(e['blob_ref'])
        start,end=source['byte_start'],source['byte_end']
        if (body is None or sha(body)!=c['content_sha256'] or
                body[start:end]!=source['quote'].encode('utf-8')):
            deny('L2_NATIVE_QUOTE_MISMATCH')
        result.append({'id':fact['fact_ref'],'snapshot_id':c['snapshot_ref'],
            'url':c['url'],'source_ref':c['source_ref'],'locator':c['locator'],
            'blob_ref':e['blob_ref'],'content_sha256':c['content_sha256'],
            'byte_start':start,'byte_end':end,'quote':source['quote'],
            'sha256':sha(body[start:end]),'native_citation':c,'native_fact':fact})
    return snapshots,result


@dataclass(frozen=True,init=False)
class NativeSource:
    """A separate versioned producer, NOT an OfflineSource validation bypass."""
    expected: str
    _payload: bytes
    _diagnosis: bytes
    _pack: EvidencePack
    held: NativeTask
    controlled_only=True

    def __init__(self,pack,diagnosis,*,held: NativeTask):
        if type(held) is not NativeTask or type(pack) is not EvidencePack or type(diagnosis) is not dict:
            deny('L2_NATIVE_TRUSTED_INPUT_REQUIRED')
        for value in asdict(held).values():
            bounded(value,2000)
        for value,prefix in ((held.native_pack_ref,'ep-'),(held.industry_ref,'ip-'),(held.diagnosis_ref,'l2-')):
            if not re.fullmatch(prefix+'[a-f0-9]{64}',value):
                deny('L2_NATIVE_PIN_REQUIRED')
        if not re.fullmatch('[a-f0-9]{64}',held.source_bundle_sha256) or held.source_access_mode not in (
                'OFFLINE_SYNTHETIC','PUBLIC_READONLY_CAPTURE','CLIENT_PROVIDED'):
            deny('L2_NATIVE_SOURCE_SCOPE_REQUIRED')
        try:
            pack.verify(expected_ref=held.native_pack_ref)
            frozen=pack  # exact frozen class; bytes/tuple objects cannot change
            raw=canonical(diagnosis,limit=4_000_000)
            data=parse(raw,limit=4_000_000)
            if (frozen.document['tenant_id'],frozen.document['run_id'])!=(held.tenant_id,held.run_id):
                deny('L2_NATIVE_TASK_MISMATCH')
            if (data['tenant_id'],data['run_id'])!=(held.tenant_id,held.run_id):
                deny('L2_NATIVE_TASK_MISMATCH')
            # This is the accepted full replay, not inspect_export/schema/hash.
            verify(data,frozen,expected_result_ref=held.diagnosis_ref,
                   expected_pack_ref=held.native_pack_ref,expected_industry_ref=held.industry_ref)
        except Exception:
            deny('L2_NATIVE_REPLAY_DENIED')
        descriptor={'contract':GUARANTEE,'version':VERSION,'task':asdict(held),
            'diagnosis_sha256':sha(raw),'pack_ref':frozen.ref,
            'pack_document_sha256':sha(canonical(frozen.document,limit=8_000_000)),
            'objects':[{ 'sha256':k,'bytes':len(v)} for k,v in sorted(frozen.objects.items())]}
        expected=sha(encoded(descriptor))
        snapshots,evs=evidence_projection(frozen,data)
        findings,journey,blueprint,models,conflicts=project(data,{e['id']:e for e in evs})
        report_id='l2-native-'+expected[:32]
        doc={'contract':NATIVE_CONTRACT,'semantic_approval':False,'external_delivery_allowed':False,
            'formal_human_review':False,'meta':{'tenant_id':held.tenant_id,'run_id':held.run_id,
            'report_id':report_id,'version':1,'created_by':VERSION,'created_at':held.created_at,
            'title':'工业采购深度诊断与 Rebuild 蓝图 · '+(' / '.join(models) or '型号UNKNOWN'),
            'source_mode':'NATIVE_VERIFIED_PACK','source_policy_ref':frozen.document['policy_id'],
            'source_access_mode':held.source_access_mode},
            'producer':{'version':VERSION,'contract':GUARANTEE,'assurance':ASSURANCE,
                'native_diagnostic_version':data['diagnostic_version'],'source_descriptor':descriptor,
                'task_authority':'CALLER_HELD_SIGNED_CURRENT_TASK_REQUIRED_NOT_GRANTED_BY_ADAPTER',
                'native_execution_ref':data['native_execution_ref'],'native_package_ref':data['native_package_ref'],
                'source_guard_refs':data['source_guard_refs']},
            'native_context':asdict(held),'industry_pack':data['industry_pack'],
            'industry_pack_sha256':sha(encoded(data['industry_pack'])),
            'snapshots':snapshots,'evidence':evs,'findings':findings,'journey':journey,'blueprint':blueprint,
            'buyer':{'label':'工业采购任务：来源声明型号 '+(' / '.join(models) or 'UNKNOWN'),
                'scenario':'沿已保留的产品、规格、应用情景、供应商声明和RFQ要求准备采购复核。',
                'assumption':'工况与型号关联来自本次原生证据和行业配置，不是企业已确认的真实客户需求、工程批准或独立SKU认证。',
                'questions':[p['goal'] for p in journey]},
            'summary':f'本次完整重放产生{len(findings)}项工业评估，保留{conflicts}项配置情景标量冲突；这不是{conflicts}个网站故障或工程不适配结论。'
                '先让工程责任人核对工况和资料版本，再组织型号资料与询价上下文。供应商声明待独立核验，买方缺输入不计网站问题；未实际发送询价。',
            'priority_intro':'优先级是采购复核工作的次序，不是网站缺陷评分。保留每项PASS、配置冲突、NOT_APPLICABLE及UNKNOWN，不夸大经营影响。',
            'priority_title':'采购复核与资料准备优先级',
            'priority_labels':{'P1':'如有直接证实的路径阻碍','P2':'优先复核已记录比较及声明',
                'P3':'按企业确认安排','UNRANKED':'已观察基线、未适用与UNKNOWN（不计缺陷）'},
            'blueprint_intro':'从实际保留的来源提出资料组织、工程复核与询价准备动作。每项保留所依据的原生观察及事实引用；不预设已有路径失效，不自动改站或发送询价。',
            'service_catalog':{'verification':'信息组织/页面模板为标准Rebuild候选，按合同确认；工程选型/认证须企业或供应商独立核验，不默认属于网站服务或必需加购。',
                'price':'UNKNOWN','schedule':'UNKNOWN'},
            'limitations':['来源字节与Guard重放不构成网站属主授权、供应商验真或当前网站状态保证。',
                '型号来自原始声明，情景由当前配置定义，真实买方需求与工程适配保持UNKNOWN。',
                '共享供应商资料在蓝图合并处理；原生逐型号评估全部保留，不重复计成多个真实认证故障。',
                '未访问后台、未发送询价、未验证投递及经营结果；这些UNKNOWN不阻止其余分析。',
                'APP/Worker与真实任务关联、签名期限和COMMIT前权威由C3负责，本模块不产生任务授权。'],
            'procurement_chains':data['procurement_chains'],'rfq_packets':data['rfq_packets'],
            'industry_rule_coverage':data['industry_rule_coverage']}
        payload=encoded(doc)
        DeepReport(payload,expected).version
        object.__setattr__(self,'expected',expected)
        object.__setattr__(self,'_payload',payload)
        object.__setattr__(self,'_diagnosis',raw)
        object.__setattr__(self,'_pack',frozen)
        object.__setattr__(self,'held',held)

    def read(self):
        return DeepReport(self._payload,self.expected)

    def validate(self,d):
        initial=self.read().document
        normalized=copy.deepcopy(d)
        try:
            for key in ('version','created_by','created_at'):
                normalized['meta'][key]=initial['meta'][key]
            if len(normalized['blueprint'])!=len(initial['blueprint']):
                deny()
            for item,original in zip(normalized['blueprint'],initial['blueprint']):
                bounded(item['change'],2000)
                item['change']=original['change']
            if encoded(normalized)!=self._payload:
                deny()
            view=DeepReport(encoded(d),self.expected)
            view.version
        except Exception:
            deny('L2_NATIVE_SOURCE_FACTS_IMMUTABLE')

    def revision(self,previous,changes,actor_id,created_at):
        return revise_proposals(self,previous,changes,actor_id,created_at)

    def object_bytes(self,blob_ref):
        """Internal evidence read; caller must retain current signed authority."""
        if blob_ref not in self._pack.objects:
            deny('L2_NATIVE_OBJECT_UNAVAILABLE')
        return self._pack.objects[blob_ref]


@dataclass(frozen=True)
class NativeCurrent:
    pins: dict
    payload: dict
    review: dict
    blueprint: dict
    report_bytes: bytes
    report_content_hash: str
    authority_expires_at: datetime


@contextmanager
def current_report(ledger,sid,report_id):
    """C2 side of C3 CurrentReader. Hold through C3's actual Brief COMMIT.

    C3 MUST also hold/revalidate the original task signed-reader authority and
    use the MINIMUM original task deadline and this review-session deadline.
    This is not an APP assignment or a new authority/TTL.
    """
    source=ledger.source
    if type(source) is not NativeSource or ledger.directory.mode!='CONTROLLED':
        deny('L2_NATIVE_CONTROLLED_CONTEXT_REQUIRED')
    with ledger.directory.lock,ledger.transaction() as c:
        p=ledger.person(sid,report_id)
        if p.role not in ('OWNER','REVIEWER'):
            deny('L2_REVIEWER_REQUIRED')
        view=ledger._get(c,p.tenant_id,report_id)
        receipt,_=ledger._decision(c,p,report_id,view,require_approved=False)
        core=receipt['decision']
        expected_items={r['id'] for r in view.document['findings']+view.document['blueprint']}
        if (receipt['scope']!='CONTROLLED_REVIEW_SIMULATION' or receipt['formal_human_review'] is not False
                or receipt['external_delivery'] is not False or receipt['reviewer_attested'] is not True
                or set(receipt['items'])!=expected_items
                or any(v not in ('ACK','REJECT','REQUEST_CHANGES') for v in receipt['items'].values())
                or (core['action']=='APPROVE' and set(receipt['items'].values())!={'ACK'})):
            deny('L2_NATIVE_CONTROLLED_RECEIPT_REQUIRED')
        if (receipt['source_hash']!=source.expected or core['content_hash']!=view.version['content_hash']
                or core['report_version_id']!=view.version['report_version_id'] or core['version']!=view.version['version']):
            deny('L2_NATIVE_REVIEW_BINDING_DENIED')
        task=asdict(source.held)
        pins={k:task[k] for k in ('tenant_id','request_id','run_id','job_id','event_id','source_ref','native_pack_ref','diagnosis_ref','source_bundle_sha256')}
        payload=parse(source._diagnosis,limit=4_000_000)
        payload_hash=sha(canonical(payload,limit=1_000_000))  # retain C3's existing bound
        pins.update(report_ref=view.version['report_version_id'],report_version=str(view.version['version']),
            report_sha256=view.display_hash,industry_pack_sha256=view.document['industry_pack_sha256'],payload_sha256=payload_hash)
        review={'receipt_ref':core['decision_id'],'receipt_sha256':sha(encoded(receipt)),
            'report_version':pins['report_version'],'report_sha256':view.display_hash,
            'decision':{'APPROVE':'APPROVE_INTERNAL','REJECT':'REJECT_INTERNAL','REQUEST_CHANGES':'REVISE_INTERNAL'}[core['action']]}
        blueprint={'contract_version':'l2-native-blueprint-v1','report_version':pins['report_version'],
            'report_sha256':view.display_hash,'native_pack_ref':task['native_pack_ref'],
            'diagnosis_ref':task['diagnosis_ref'],'items':view.document['blueprint'],
            'internal_only':True,'customer_approval':False}
        session=ledger.directory.require(sid,report_id)
        yield NativeCurrent(pins,payload,review,blueprint,view.payload,view.version['content_hash'],
                            datetime.fromtimestamp(min(session.expires,ledger.directory.expires),timezone.utc))
        ledger.directory.require(sid,report_id)
