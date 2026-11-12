"""Frozen business oracles, independent of the uninspected RA3C API layout.

No production implementation, stub, candidate fixture, skip or xfail lives here.
The later adapter is transport/extraction only; see SUBJECT_PROTOCOL.md.
"""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from html.parser import HTMLParser
import importlib
import importlib.util
import json
from pathlib import Path
import re
import os
from unittest.mock import patch

import pytest

from vrae.collection.collector import Collector
from vrae.collection.fetcher import SafeFetcher
from vrae.collection.http_transport import FetchResponse
from vrae.collection.limits import Limits
from vrae.collection.manifest import document_hash
from vrae.collection.policy import SourceAccess
from vrae.domain.contracts import validate_contract
from vrae.domain.errors import DomainError
from vrae.domain.reviews import check_share, report_content_hash
from vrae.evidence import EvidencePack, build_pack
from vrae.findings import build_findings
from vrae.interpretation import GuardResult, binding, catalog, validate as guard_validate
from vrae.rules import execute

FIXTURES = Path(__file__).parent/'fixtures'
CASES = json.loads((FIXTURES/'ra3c_codex1_cases.json').read_text(encoding='utf-8'))
INPUT_PATH = FIXTURES/'ra3c_codex1_inputs.json'
INPUT = json.loads(INPUT_PATH.read_text(encoding='utf-8'))
NOW = datetime(2026,11,10,12,tzinfo=timezone.utc)
SPECIAL_TEXT = 'SYNTHETIC_TENANT_SECRET_NOT_A_CREDENTIAL'
assert len(CASES) == 64 and len({c['id'] for c in CASES}) == 64


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')


class _DNS:
    async def resolve(self,host):
        assert host == 'example.org', 'Independent QA forbids real source lookup'
        return ('93.184.216.20',)


class _Transport:
    def __init__(self,routes):
        self.routes,self.calls = routes,[]

    async def exchange(self,url,method,ip,budget,max_bytes):
        assert url in self.routes and method == 'GET' and ip == '93.184.216.20'
        self.calls.append(url)
        status,kind,text = self.routes[url]
        raw = text.encode('utf-8')
        assert len(raw) <= max_bytes
        budget.consume(len(raw))
        return FetchResponse(url,status,{'content-type':kind},raw,ip)


@lru_cache(maxsize=None)
def _source(scenario):
    config = INPUT['scenarios'][scenario]
    routes = deepcopy(INPUT['routes'])
    routes.update(deepcopy(config.get('routes',{})))
    access = SourceAccess(deepcopy(INPUT['request']),lambda:deepcopy(INPUT['policy']),
                          terms_reference='terms-ra3c-codex1',now=lambda:NOW)
    transport = _Transport(routes)
    bundle = asyncio.run(Collector(SafeFetcher(_DNS(),transport)).capture(
        'run-ra3c-qa-'+scenario,access,
        limits=Limits(max_pages=config.get('max_pages',6),interval_seconds=0.01),
        retain_raw_html=config.get('retain_raw',True)))
    pack = build_pack([bundle])
    execution = execute(pack,expected_pack_ref=pack.ref,evaluator_version='ra2b6-1.0.0')
    package = build_findings(pack,execution,expected_pack_ref=pack.ref,
        expected_execution_ref=execution['execution_ref'],expected_evaluator_version='ra2b6-1.0.0',
        expected_builder_version='ra2c3-1.0.0')
    pins = dict(expected_pack_ref=pack.ref,expected_execution_ref=execution['execution_ref'],
        expected_package_ref=package.ref,expected_evaluator_version='ra2b6-1.0.0',
        expected_builder_version='ra2c3-1.0.0',expected_guard_version='ra3b-1.0.0',
        expected_scope={k:pack.document[k] for k in ('tenant_id','run_id','policy_id','policy_version')})
    return pack,execution,package,pins,transport.calls


def prepare_context(scenario,profile='truthful',*,check_pins=True):
    """Accepted-main capture/guard replay; independent held pins, no RA3C import."""
    pack,execution,package,pins,calls = _source(scenario)
    available = catalog(pack,package,**pins)
    eligible = [f for f in available['facts'] if f['rule_id'] == 'CTA-02'] or available['facts'][:1]
    fact = eligible[0] if eligible else None
    interpretation = dict(schema_version='1.0',tenant_id=pins['expected_scope']['tenant_id'],
        run_id=pins['expected_scope']['run_id'],interpretation_id='ai-ra3c-codex1-'+profile,
        observation_ids=[],evidence_ids=[],hypotheses=[],recommendations=[],missing_information=[],
        model_id=None,input_tokens=None,output_tokens=None,status='VALIDATED' if fact else 'NOT_RUN')
    bindings = []
    if fact:
        interpretation['observation_ids'] = [fact['observation_id']]
        interpretation['evidence_ids'] = [fact['source']['citation']['evidence_ref']]
        statements = [('hypotheses','OBJECTIVE_SOURCE_FACT',fact['statement']),
            ('hypotheses','HYPOTHESIS','采购人员可能无法沿这条已记录的路径继续联系，需人工复核实际情境。'),
            ('recommendations','RECOMMENDATION','建议先核对产品页联系链接与目标页面，再确认是否属于标准 Rebuild 候选范围。'),
            ('recommendations','RECOMMENDATION','复验时在相同已授权范围重新请求该联系路径，核对状态和页面，不提交表单。'),
            ('missing_information','MISSING_INFORMATION','尚未核实表单送达、工厂资质、搜索排名或实际销售结果。')]
        statements.extend(('hypotheses','OBJECTIVE_SOURCE_FACT',s) for s in INPUT['profiles'][profile])
        for field,kind,text in statements:
            pointer = f'/{field}/{len(interpretation[field])}'
            interpretation[field].append(text)
            bindings.append(binding(pointer=pointer,text=text,claim_type=kind,
                                    fact=deepcopy(fact),context=deepcopy(available['context'])))
    guard = guard_validate(interpretation,bindings,pack,package,**pins)
    actual = dict(**pins,expected_guard_ref=guard.ref)
    if check_pins:
        assert actual == INPUT['scenarios'][scenario]['pins'][profile], 'QA_INPUT_PIN_MISMATCH'
    findings = [r['finding'] for r in package.document['items'] if r['outcome'] == 'FAIL_WITH_EVIDENCE']
    return dict(pack=pack,execution=deepcopy(execution),package=package,guard=guard,
        interpretation=interpretation,bindings=bindings,pins=deepcopy(actual),
        verified_findings=findings,guard_facts=deepcopy(available['facts']),
        caller_scope=deepcopy(pins['expected_scope']),calls=list(calls),scenario=scenario,profile=profile)


class HtmlAudit(HTMLParser):
    """Independent inert-HTML/anchor parser, never executes source."""
    def __init__(self,raw):
        super().__init__(convert_charrefs=True)
        self.nodes,self.stack,self.parts = [],[],[]
        self.feed(raw.decode('utf-8',errors='strict'))
        self.close()

    def handle_starttag(self,tag,attrs):
        node = dict(tag=tag,attrs=dict(attrs),text=[],index=len(self.nodes))
        self.nodes.append(node)
        if tag not in {'meta','link','img','input','br','hr','source','wbr','area','base','embed','param','col'}:
            self.stack.append(node)

    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]
                break

    def handle_data(self,text):
        self.parts.append(text)
        for node in self.stack:
            node['text'].append(text)


def pointer(doc,path):
    if path == '':
        return doc
    assert path.startswith('/')
    for token in path[1:].split('/'):
        token = token.replace('~1','/').replace('~0','~')
        doc = doc[int(token)] if isinstance(doc,list) else doc[token]
    return doc


def field(subject,artifact,role,*,issue=None):
    """Every mapped scalar/object has an explicit actual JSON or HTML origin."""
    origin = subject.origins[role]
    if origin['kind'] == 'object':
        assert role not in ('native_report','issues'), 'Actual native objects/lists cannot be synthesized'
        class Mapped:
            origins = {role+'.'+k:v for k,v in origin['members'].items()}
        return {k:field(Mapped,artifact,role+'.'+k,issue=issue) for k in origin['members']}
    if origin['kind'] == 'absent_native':
        assert role == 'native_report' and issue is None
        def walk(v):
            if isinstance(v,dict):
                assert not {'report_version_id','finding_ids','approved_by'} <= set(v)
                for child in v.values():
                    walk(child)
            elif isinstance(v,list):
                for child in v:
                    walk(child)
        walk(artifact['document'])
        return None
    if origin['kind'] == 'json':
        root = issue if issue is not None and origin.get('root') != 'document' else artifact['document']
        return pointer(root,origin['pointer'])
    assert origin['kind'] == 'html', 'QA_MAPPING_NOT_BOUND: unsupported extraction'
    assert issue is None, 'QA_MAPPING_NOT_BOUND: HTML issue mapping requires native JSON item'
    node = HtmlAudit(artifact['html']).nodes[origin['node_index']]
    return node['attrs'][origin['attribute']] if 'attribute' in origin else ' '.join(''.join(node['text']).split())


@contextmanager
def no_external_effects():
    """Gate real candidate calls, not the accepted local capture's event loop."""
    attempts = []
    def deny(*args,**kwargs):
        attempts.append(True)
        raise AssertionError('QA_FORBIDDEN_NETWORK_OR_PROCESS')
    with patch('socket.getaddrinfo',deny), patch('socket.create_connection',deny), \
         patch('socket.socket.connect',deny), patch('socket.socket.connect_ex',deny), \
         patch('subprocess.Popen',deny):
        try:
            yield
        finally:
            assert not attempts, 'QA_FORBIDDEN_NETWORK_OR_PROCESS_ATTEMPT'


class GuardedSubject:
    def __init__(self,native):
        self.native = native

    def __getattr__(self,key):
        return getattr(self.native,key)

    def build(self,*args,**kwargs):
        with no_external_effects():
            return self.native.build(*args,**kwargs)

    def load(self,*args,**kwargs):
        with no_external_effects():
            return self.native.load(*args,**kwargs)


@pytest.fixture(scope='module')
def subject():
    # Genuine Phase-A RED: main has no reporting; no fake module or fallback.
    with no_external_effects():
        reporting = importlib.import_module('vrae.reporting')
    filename = os.environ.get('VRAE_RA3C_QA_ADAPTER_PATH')
    assert filename, 'QA_MAPPING_NOT_BOUND: exact-candidate public API mapping required'
    spec = importlib.util.spec_from_file_location('codex1_ra3c_transport',filename)
    module = importlib.util.module_from_spec(spec)
    with no_external_effects():
        spec.loader.exec_module(module)
        result = module.bind(reporting)
    assert result.production_module is reporting
    assert result.rejection_types and all(t.__module__.startswith('vrae.') for t in result.rejection_types)
    return GuardedSubject(result)


def build(subject,context,revision=1):
    before = canonical({k:v for k,v in context.items() if k in ('interpretation','bindings','pins')})
    artifact = subject.build(context,revision=revision,created_at=INPUT['report_time'])
    assert isinstance(artifact['document'],dict) and isinstance(artifact['html'],bytes)
    assert artifact['origin_module'].startswith('vrae.reporting')
    assert before == canonical({k:v for k,v in context.items() if k in ('interpretation','bindings','pins')})
    assert field(subject,artifact,'private') is True
    assert field(subject,artifact,'approval_status') in ('NOT_APPROVED','DRAFT','REVIEW_REQUIRED')
    assert field(subject,artifact,'shareable') is False
    assert len(field(subject,artifact,'issues')) <= 3
    def no_approval(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key in ('review_decision','share_grant','approved_by','approved_at'):
                    assert child is None, 'Report assembly cannot create approval authority'
                no_approval(child)
        elif isinstance(value,list):
            for child in value:
                no_approval(child)
    no_approval(artifact['document'])
    return artifact


def load_rejects(subject,artifact,context,document=None,html=None):
    changed = deepcopy(artifact['document']) if document is None else document
    changed_html = artifact['html'] if html is None else html
    assert canonical(changed) != canonical(artifact['document']) or changed_html != artifact['html'], 'QA_INVALID_NOOP_MUTATION'
    with pytest.raises(subject.rejection_types):
        subject.load(changed,changed_html,context,expected_digest=artifact['digest'])


def mutate(subject,artifact,role,value):
    origin = subject.origins[role]
    assert origin['kind'] == 'json' and origin['pointer'], 'QA_MAPPING_NOT_BOUND: native JSON mutation path required'
    doc = deepcopy(artifact['document'])
    path = origin['pointer'].rsplit('/',1)
    parent = pointer(doc,path[0])
    key = path[1].replace('~1','/').replace('~0','~')
    if isinstance(parent,list):
        parent[int(key)] = value
    else:
        parent[key] = value
    assert canonical(doc) != canonical(artifact['document'])
    return doc


def issue_field(subject,artifact,role):
    items = field(subject,artifact,'issues')
    assert items
    return field(subject,artifact,'issue.'+role,issue=items[0])


def safe_html(artifact):
    parsed = HtmlAudit(artifact['html'])
    ids = [n['attrs']['id'] for n in parsed.nodes if 'id' in n['attrs']]
    assert len(ids) == len(set(ids))
    for n in parsed.nodes:
        assert n['tag'] not in {'script','iframe','object','embed','base','form'}
        assert not any(k.lower().startswith('on') for k in n['attrs'])
        assert not (n['tag'] == 'meta' and n['attrs'].get('http-equiv','').lower() == 'refresh')
        for key in ('href','action','formaction','poster','srcset'):
            if key in n['attrs']:
                assert key == 'href' and n['attrs'][key].startswith('#')
                assert n['attrs'][key][1:] in ids
        if 'src' in n['attrs']:
            assert n['tag'] == 'img' and re.fullmatch(r'data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=]+',n['attrs']['src'])
        css = n['attrs'].get('style','') + (''.join(n['text']) if n['tag'] == 'style' else '')
        assert not re.search(r'url\s*\(|@import|expression\s*\(',css,re.I)
        if n['tag'] in ('button','input','select','textarea'):
            assert 'disabled' in n['attrs']
    return parsed


def integrity_hash(subject,artifact):
    """Independent full-document + rendered-byte binding, never RA0-only hash."""
    doc = deepcopy(artifact['document'])
    for path in subject.digest_recipe['self_digest_paths']:
        assert path.startswith('/') and '/' not in path[1:]
        key = path[1:]
        assert re.fullmatch(r'(?:[a-z0-9-]+-)?[0-9a-f]{64}',doc[key])
        del doc[key]
    kind = subject.digest_recipe['kind']
    if kind == 'canonical_doc':
        payload = canonical(doc)
        assert artifact['html'].decode('utf-8') in list_strings(doc) or hashlib.sha256(artifact['html']).hexdigest() in list_strings(doc)
    else:
        assert kind == 'canonical_doc_plus_html'
        separator = subject.digest_recipe['separator'].encode('ascii')
        assert len(separator) <= 16
        payload = canonical(doc)+separator+artifact['html']
    assert hashlib.sha256(payload).hexdigest() == re.search(r'([0-9a-f]{64})$',artifact['digest'])[1]


def list_strings(value):
    if isinstance(value,str):
        return [value]
    if isinstance(value,dict):
        return [s for v in value.values() for s in list_strings(v)]
    if isinstance(value,list):
        return [s for v in value for s in list_strings(v)]
    return []


def observed(subject,artifact,case):
    """Actual browser/reading dossier, external QA-only; absent != visual PASS."""
    filename = os.environ.get('VRAE_RA3C_QA_OBSERVATIONS_PATH')
    assert filename, 'VISUAL_NOT_VERIFIED: genuine candidate-bound browser dossier required'
    data = json.loads(Path(filename).read_text(encoding='utf-8'))
    assert data['candidate_sha'] == os.environ['VRAE_RA3C_EXPECTED_CANDIDATE_SHA']
    assert data['html_sha256'] == hashlib.sha256(artifact['html']).hexdigest()
    assert data['not_customer_approval'] is True
    for width in (375,1280):
        view = data['viewports'][str(width)]
        assert view['width'] == width and view['external_requests'] == []
        image = Path(view['screenshot_path'])
        assert image.is_file() and hashlib.sha256(image.read_bytes()).hexdigest() == view['screenshot_sha256']
    return data


@pytest.mark.parametrize('case',CASES,ids=[c['id']+'-'+c['name'] for c in CASES])
def test_independent_product_acceptance(subject,case,record_property):
    ctx = prepare_context(case['scenario'],case.get('profile','truthful'))
    oracle = case['oracle']
    if oracle in ('cross_pack','guard_pins'):
        if oracle == 'cross_pack':
            bad = deepcopy(ctx)
            bad['pack'] = prepare_context('healthy200')['pack']
            assert bad['pack'].ref != ctx['pack'].ref
            with pytest.raises(subject.rejection_types):
                subject.build(bad,revision=1,created_at=INPUT['report_time'])
            # Raw-source corruption and a separately resealed projection retain
            # original caller pins. Rehashing is not independent provenance.
            source = ctx['pack']
            blobs = dict(source.objects)
            key = next(iter(blobs))
            blobs[key] += b' forged source'
            bad = deepcopy(ctx)
            bad['pack'] = EvidencePack(canonical(source.document),tuple(sorted(blobs.items())))
            assert dict(bad['pack'].objects) != dict(source.objects)
            with pytest.raises(subject.rejection_types):
                subject.build(bad,revision=1,created_at=INPUT['report_time'])
            doc = source.document
            doc['tenant_id'] += '-foreign'
            doc['pack_ref'] = 'ep-'+document_hash({k:v for k,v in doc.items() if k != 'pack_ref'})
            bad['pack'] = EvidencePack(canonical(doc),tuple(sorted(source.objects.items())))
            assert bad['pack'].ref != source.ref
            with pytest.raises(subject.rejection_types):
                subject.build(bad,revision=1,created_at=INPUT['report_time'])
        else:
            for key,prefix in (('expected_pack_ref','ep-'),('expected_execution_ref','rx-'),
                               ('expected_package_ref','fp-'),('expected_guard_ref','cg-')):
                bad = deepcopy(ctx)
                bad['pins'][key] = prefix+'0'*64
                assert bad['pins'] != ctx['pins']
                with pytest.raises(subject.rejection_types):
                    subject.build(bad,revision=1,created_at=INPUT['report_time'])
            for key in ('tenant_id','run_id','policy_id','policy_version'):
                bad = deepcopy(ctx)
                scope = bad['pins']['expected_scope']
                scope[key] = scope[key]+1 if isinstance(scope[key],int) else scope[key]+'-foreign'
                assert bad['pins'] != ctx['pins']
                with pytest.raises(subject.rejection_types):
                    subject.build(bad,revision=1,created_at=INPUT['report_time'])
        return
    if oracle == 'false_claims' or case['id'] in ('E03','E04','E05','E07','E08'):
        try:
            artifact = build(subject,ctx)
        except subject.rejection_types as error:
            assert len(str(error)) <= 256 and SPECIAL_TEXT not in str(error)
            record_property('acceptance_path','DEFENSIVE_REFUSAL_NOT_VISUAL_PASS')
            return
    else:
        artifact = build(subject,ctx)
    record_property('acceptance_path','ACTUAL_DRAFT_INSPECTED')
    items = field(subject,artifact,'issues')
    if oracle in ('one_issue','dedupe'):
        assert len(items) == 1
        assert issue_field(subject,artifact,'buyer_task') == 'INQUIRE'
        assert issue_field(subject,artifact,'target_status') == (410 if case['scenario'] == 'broken410' else 404)
        trust = next(r for r in ctx['execution']['executions'] if r['rule_id'] == 'TRUST-01')
        assert all(r['observation']['result'] == 'UNKNOWN' for r in trust['observations'])
    elif oracle in ('zero_issues','positives'):
        assert items == [] and field(subject,artifact,'native_report') is None
        assert field(subject,artifact,'coverage') and field(subject,artifact,'unchecked')
    elif oracle == 'padding':
        assert len(items) == 1
        load_rejects(subject,artifact,ctx,mutate(subject,artifact,'issues',items*4))
    elif oracle == 'layers':
        layers = [issue_field(subject,artifact,k) for k in ('fact','impact','action','recheck')]
        assert all(isinstance(x,str) and x.strip() for x in layers) and len(set(layers)) == 4
        assert all(x in artifact['html'].decode('utf-8') or x in ''.join(HtmlAudit(artifact['html']).parts) for x in layers)
    elif oracle in ('impact','action'):
        assert issue_field(subject,artifact,oracle+'_status') == 'HUMAN_REVIEW_REQUIRED'
        modal = '假设|可能|待.*复核|待.*审核' if oracle == 'impact' else '建议|候选|待.*批准|待.*审核|待.*复核'
        assert re.search(modal,issue_field(subject,artifact,oracle))
    elif oracle == 'recheck':
        text = issue_field(subject,artifact,'recheck')
        assert re.search('复验|重新|再次|核对',text) and re.search('状态|链接|路径|页面',text)
        assert not re.search('提交表单即可|已发送询盘',text)
    elif oracle == 'buyer_task':
        assert issue_field(subject,artifact,'buyer_task') == 'INQUIRE'
    elif oracle == 'coverage':
        coverage = field(subject,artifact,'coverage')
        assert coverage and field(subject,artifact,'unchecked')
        source_times = {datetime.fromisoformat(s['observed_at'].replace('Z','+00:00')) for s in ctx['pack'].document['snapshots']}
        assert datetime.fromisoformat(field(subject,artifact,'captured_at').replace('Z','+00:00')) in source_times
        captured_urls = {s['url'] for s in ctx['pack'].document['snapshots']}
        declared_urls = set(re.findall(r'https://[A-Za-z0-9._~:/%#?&=+-]+',json.dumps(coverage,ensure_ascii=False)))
        assert declared_urls <= captured_urls
        assert field(subject,artifact,'scope') == ctx['caller_scope']
    elif oracle == 'chinese':
        assert re.search(r'[\u4e00-\u9fff]',field(subject,artifact,'main_text'))
        assert '404' in issue_field(subject,artifact,'fact')
    elif oracle == 'service_scope':
        text = issue_field(subject,artifact,'action')+' '+field(subject,artifact,'service_scope_text')
        assert re.search('核对|检查|修复|确认',text) and re.search('待|建议|候选|讨论|范围',text)
        assert not re.search('保证|必然|承诺.*(?:提升|交付)|自动.*(?:报价|签约)',text)
    elif oracle in ('no_scores','no_lead','no_testimonials'):
        objective = '\n'.join(field(subject,artifact,'objective_texts'))
        assert not re.search('全站评分|网站得分|保证.*提升|损失.*(?:美元|元)|已确认商机|已收到询盘|真实客户案例|客户证言',objective)
        assert field(subject,artifact,'scores') in (None,[],{})
    elif oracle == 'finding':
        original = {r['finding_id']:r for r in ctx['verified_findings']}
        assert items and all(field(subject,artifact,'issue.finding_id',issue=i) in original for i in items)
    elif oracle in ('quote','source_edge'):
        ev = issue_field(subject,artifact,'evidence')
        assert ev['pack_ref'] == ctx['pack'].ref and ev['observed_at']
        resolved = ctx['pack'].resolve(ev['evidence_ref'],expected_pack_ref=ctx['pack'].ref)
        assert resolved['content'][ev['byte_start']:ev['byte_end']] == ev['quote'].encode('utf-8')
        assert ev['source_url'] == resolved['snapshot']['url'] and ev['captured_scope'] == ctx['caller_scope']
        assert ev['target_status'] in (404,410) and ev['href'] == '/contact'
        assert any(c['binding_ref'] == ev['binding_ref'] and c['status'] == 'SOURCE_FACT_BINDING_VERIFIED'
                   for c in ctx['guard'].document['claims'])
    elif oracle == 'false_claims':
        objective = '\n'.join(field(subject,artifact,'objective_texts'))
        assert not any(text in objective for text in INPUT['profiles'][case['profile']])
        admitted = {c['binding_ref'] for c in ctx['guard'].document['claims'] if c['status'] == 'SOURCE_FACT_BINDING_VERIFIED'}
        assert set(field(subject,artifact,'objective_binding_refs')) <= admitted
    elif oracle == 'roundtrip':
        integrity_hash(subject,artifact)
        loaded = subject.load(deepcopy(artifact['document']),artifact['html'],ctx,expected_digest=artifact['digest'])
        assert loaded['document'] == artifact['document'] and loaded['html'] == artifact['html']
        again = build(subject,prepare_context(case['scenario']))
        assert again['document'] == artifact['document'] and again['html'] == artifact['html']
    elif oracle == 'tamper':
        role = 'issues'
        changed = deepcopy(items)
        assert changed
        field_name = 'issue.'+case['field']
        path = subject.origins[field_name]
        assert path['kind'] == 'json'
        relative = path['pointer'].rsplit('/',1)
        parent = pointer(changed[0],relative[0])
        key = relative[1]
        old = parent[key]
        parent[key] = (str(old)+' 攻击性改写') if isinstance(old,str) else {'forged':'unrelated source'}
        load_rejects(subject,artifact,ctx,mutate(subject,artifact,role,changed))
    elif oracle == 'html_tamper':
        load_rejects(subject,artifact,ctx,html=artifact['html']+b'\n<p>forged unreviewed statement</p>')
    elif oracle in ('scope_tamper','metadata_tamper','layout_tamper','guard_tamper','approval_tamper'):
        if oracle == 'scope_tamper':
            original_scope = field(subject,artifact,'scope')
            assert original_scope == ctx['caller_scope']
            for key in ('tenant_id','run_id','policy_id','policy_version'):
                scope = deepcopy(original_scope)
                scope[key] = scope[key]+1 if isinstance(scope[key],int) else scope[key]+'-foreign'
                load_rejects(subject,artifact,ctx,mutate(subject,artifact,'scope',scope))
        if oracle == 'guard_tamper':
            bad = deepcopy(ctx)
            doc = ctx['guard'].document
            row = next(c for c in doc['claims'] if c['status'] == 'HUMAN_REVIEW_REQUIRED')
            row['status'] = 'SOURCE_FACT_BINDING_VERIFIED'
            doc['guard_ref'] = 'cg-'+document_hash({k:v for k,v in doc.items() if k != 'guard_ref'})
            bad['guard'] = GuardResult(canonical(doc))
            assert bad['guard'].ref != ctx['guard'].ref and bad['pins'] == ctx['pins']
            with pytest.raises(subject.rejection_types):
                subject.build(bad,revision=1,created_at=INPUT['report_time'])
        roles = {'scope_tamper':['scope'], 'metadata_tamper':['captured_at','version','coverage'],
            'layout_tamper':['language','layout_version','asset_version'],
            'guard_tamper':['guard_ref'], 'approval_tamper':['approval_status','private','shareable']}[oracle]
        for role in roles:
            old = field(subject,artifact,role)
            value = not old if isinstance(old,bool) else old+1 if isinstance(old,int) else 'forged-codex1' if isinstance(old,str) else {'forged':True}
            if role == 'approval_status':
                value = 'APPROVED'
            load_rejects(subject,artifact,ctx,mutate(subject,artifact,role,value))
    elif oracle == 'version_pin':
        newer = build(subject,prepare_context(case['scenario']),revision=2)
        assert newer['digest'] != artifact['digest'] and canonical(newer['document']) != canonical(artifact['document'])
        load_rejects(subject,artifact,ctx,newer['document'],newer['html'])
    elif oracle in ('native_hash','share_denied'):
        native = field(subject,artifact,'native_report')
        if native is not None:
            validate_contract('ReportVersion',native)
            assert native['status'] in ('DRAFT','REVIEW_REQUIRED') and native['approved_by'] is None and native['approved_at'] is None
            assert native['content_hash'] == report_content_hash(native,ctx['verified_findings'])
            record_property('native_report','PRESENT_RA0_HASH_VERIFIED')
        else:
            integrity_hash(subject,artifact)
            record_property('native_report','NOT_INCLUDED_ALLOWED_NO_RA0_APPROVAL_OBJECT')
        if oracle == 'share_denied':
            if native is not None:
                decision = dict(tenant_id=native['tenant_id'],action='APPROVE',reviewer_id='forged-reviewer')
                grant = dict(tenant_id=native['tenant_id'])
                actor = dict(actor_id='synthetic-owner',tenant_id=native['tenant_id'],role='OWNER')
                with pytest.raises(DomainError) as denied:
                    check_share(native,decision,grant,actor,native['version'],NOW,'L1',findings=ctx['verified_findings'])
                assert denied.value.code == 'REPORT_NOT_APPROVED'
            for key in ('review_decision','share_grant'):
                modified = deepcopy(artifact['document'])
                modified[key] = {'forged_authority':True}
                load_rejects(subject,artifact,ctx,modified)
    elif oracle in ('safe_html','internal_links','unsafe_links','anchors','no_forms'):
        safe_html(artifact)
    elif oracle == 'bounded_html':
        safe_html(artifact)
        assert len(artifact['html']) < 1_000_000, 'Bounded draft required; inspect actual reading separately'
    elif oracle == 'bidi':
        assert not re.search('[\u202a-\u202e\u2066-\u2069]',field(subject,artifact,'privacy_text'))
        assert field(subject,artifact,'shareable') is False
    elif oracle == 'pii':
        parsed = safe_html(artifact)
        for node in parsed.nodes:
            for key,value in node['attrs'].items():
                if key in ('href','src','action','data-url'):
                    assert not any(s in value for s in (SPECIAL_TEXT,'private.qa@synthetic.invalid','00000000000'))
    elif oracle == 'not_debug':
        text = field(subject,artifact,'main_text')
        assert not ('"rule_execution"' in text and '"objects_base64"' in text)
        assert not (text.strip().startswith('{') and 'binding_ref' in text)
    elif oracle == 'document_state':
        parsed = safe_html(artifact)
        assert any(n['tag'] == 'html' and n['attrs'].get('lang','').startswith('zh') for n in parsed.nodes)
        assert any(n['tag'] == 'meta' and n['attrs'].get('charset','').lower() == 'utf-8' for n in parsed.nodes)
        assert re.search('未批准|NOT.?APPROVED|待审核|未审核',field(subject,artifact,'privacy_text'),re.I)
        assert re.search('合成|synthetic|内部|private',field(subject,artifact,'privacy_text'),re.I)
    else:
        data = observed(subject,artifact,case)
        mobile,desktop = data['viewports']['375'],data['viewports']['1280']
        if oracle in ('mobile','desktop'):
            view = mobile if oracle == 'mobile' else desktop
            assert view['scroll_width'] <= view['client_width']+1
            assert view['body_font_px'] >= 14 and view['main_heading_count'] == 1
            assert view['visible_layer_labels'] >= 4
        elif oracle == 'click_evidence':
            assert data['evidence_clicks'] and all(c['internal'] and c['resolved'] and c['correct_quote'] for c in data['evidence_clicks'])
        elif oracle == 'visible_state':
            assert all(v['privacy_above_fold'] and v['privacy_font_px'] >= 12 for v in (mobile,desktop))
        elif oracle == 'screenshots':
            assert data['capture_tool'] and data['candidate_sha'] and all(v['browser_version'] for v in (mobile,desktop))
        else:
            assert oracle in ('reading_memo','scope_memo','value_memo')
            memo = data['business_review'][oracle]
            assert memo['qa_only'] is True and memo['decision'] == 'QA_OBSERVED_PASS'
            assert memo['observed_quote'] in ''.join(HtmlAudit(artifact['html']).parts)
            assert len(memo['reasoning']) >= 80 and memo['screenshot_refs']
            assert memo['not_report_approval'] is True
            if oracle == 'value_memo':
                zero = build(subject,prepare_context('healthy200'))
                assert field(subject,zero,'issues') == [] and len(items) == 1
                integrity_hash(subject,zero)
                comparison = memo['comparison']
                assert comparison['one_html_sha256'] == hashlib.sha256(artifact['html']).hexdigest()
                assert comparison['zero_html_sha256'] == hashlib.sha256(zero['html']).hexdigest()
                assert comparison['zero_observed_quote'] in ''.join(HtmlAudit(zero['html']).parts)
                image = Path(comparison['zero_screenshot_path'])
                assert image.is_file() and hashlib.sha256(image.read_bytes()).hexdigest() == comparison['zero_screenshot_sha256']
