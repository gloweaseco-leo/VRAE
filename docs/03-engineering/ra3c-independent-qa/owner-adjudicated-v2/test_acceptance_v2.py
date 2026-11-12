"""OWNER_ADJUDICATED_RA3C_QA_V2; original V1/14 sources remain immutable."""
from copy import deepcopy
from datetime import datetime
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ra3c_v2_test_support',HERE/'support.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
v1 = support.v1
CASES,INPUT,NOW,SPECIAL_TEXT = support.CASES,v1.INPUT,v1.NOW,v1.SPECIAL_TEXT
canonical,HtmlAudit,pointer,safe_html = v1.canonical,v1.HtmlAudit,v1.pointer,v1.safe_html
integrity_hash = v1.integrity_hash
EvidencePack,document_hash = v1.EvidencePack,v1.document_hash
DomainError,validate_contract = v1.DomainError,v1.validate_contract
check_share,report_content_hash = v1.check_share,v1.report_content_hash
positive_context,attack_context,guard_claims = support.positive_context,support.attack_context,support.guard_claims


@pytest.fixture(scope='module')
def subject():
    with v1.no_external_effects():
        reporting = importlib.import_module('vrae.reporting')
        spec = importlib.util.spec_from_file_location('ra3c_v2_real_native_transport',HERE/'adapter_v2.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        native = module.bind(reporting)
    assert native.production_module is reporting
    assert native.rejection_types and all(t.__module__.startswith('vrae.') for t in native.rejection_types)
    return v1.GuardedSubject(native)


def field(subject,artifact,role,*,issue=None):
    return subject.read(artifact,role,issue=issue)


def build(subject,context,revision=1):
    before = canonical({k:context[k] for k in ('guard_inputs','pins')})
    artifact = subject.build(context,revision=revision,created_at=INPUT['report_time'])
    assert isinstance(artifact['document'],dict) and isinstance(artifact['html'],bytes)
    assert artifact['origin_module'].startswith('vrae.reporting')
    assert before == canonical({k:context[k] for k in ('guard_inputs','pins')})
    assert field(subject,artifact,'private') is True
    assert field(subject,artifact,'approval_status') in ('NOT_APPROVED','DRAFT','REVIEW_REQUIRED')
    assert field(subject,artifact,'shareable') is False
    assert len(field(subject,artifact,'issues')) <= 3
    def no_approval(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key in ('review_decision','share_grant','approved_by','approved_at'):
                    assert child is None
                no_approval(child)
        elif isinstance(value,list):
            for child in value:
                no_approval(child)
    no_approval(artifact['document'])
    return artifact


def mutate_json(artifact,path,value):
    doc = deepcopy(artifact['document'])
    head,token = path.rsplit('/',1)
    token = token.replace('~1','/').replace('~0','~')
    parent = pointer(doc,head)
    if isinstance(parent,list):
        parent[int(token)] = value
    else:
        assert token in parent
        parent[token] = value
    assert canonical(doc) != canonical(artifact['document']), 'V2_INVALID_NOOP_MUTATION'
    return doc


def mutate(subject,artifact,role,value):
    return mutate_json(artifact,subject.origins[role]['pointer'],value)


def load_rejects(subject,artifact,context,document=None,html=None,expected_digest=None):
    changed = deepcopy(artifact['document']) if document is None else document
    changed_html = artifact['html'] if html is None else html
    assert canonical(changed) != canonical(artifact['document']) or changed_html != artifact['html'], 'V2_INVALID_NOOP_MUTATION'
    with pytest.raises(subject.rejection_types):
        subject.load(changed,changed_html,context,expected_digest=artifact['digest'] if expected_digest is None else expected_digest)


def issue_field(subject,artifact,role):
    items = field(subject,artifact,'issues')
    assert items
    return field(subject,artifact,'issue.'+role,issue=items[0])


def observed(subject,artifact,case):
    filename = os.environ.get('VRAE_RA3C_QA_V2_OBSERVATIONS_PATH')
    assert filename, 'VISUAL_NOT_VERIFIED: actual V2 candidate dossier required'
    data = json.loads(Path(filename).read_text(encoding='utf-8'))
    assert data['candidate_sha'] == os.environ['VRAE_RA3C_QA_V2_CANDIDATE_SHA']
    assert data['html_sha256'] == hashlib.sha256(artifact['html']).hexdigest()
    assert data['not_customer_approval'] is True
    for width in (375,1280):
        view = data['viewports'][str(width)]
        assert view['width'] == width and view['external_requests'] == []
        path = Path(view['screenshot_path'])
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == view['screenshot_sha256']
    return data


@pytest.mark.parametrize('case',CASES,ids=[c['id']+'-'+c['name'] for c in CASES])
def test_owner_adjudicated_business_objective(subject,case,record_property):
    ctx = positive_context(case['scenario'])
    oracle = case['oracle']
    if oracle in ('cross_pack','guard_pins'):
        build(subject,ctx)  # require real valid baseline before attacking held pins
        if oracle == 'cross_pack':
            bad = deepcopy(ctx)
            bad['pack'] = positive_context('healthy200')['pack']
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
                               ('expected_package_ref','fp-'),('expected_guard_refs','cg-')):
                bad = deepcopy(ctx)
                bad['pins'][key] = [prefix+'0'*64] if key == 'expected_guard_refs' else prefix+'0'*64
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
    if oracle == 'false_claims':
        artifact = build(subject,ctx)  # real admissible source-backed report required
        attack = attack_context(case['scenario'],case['profile'])
        assert any(c['status'] == 'REJECTED' for c in guard_claims(attack))
        with pytest.raises(subject.rejection_types) as rejected:
            subject.build(attack,revision=1,created_at=INPUT['report_time'])
        assert str(rejected.value) == 'REPORT_CLAIM_REJECTED'
        assert len(str(rejected.value)) <= 256 and SPECIAL_TEXT not in str(rejected.value)
    elif case['id'] in ('E03','E04','E05','E07','E08'):
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
        assert not subject.score_fields(artifact)
        assert all(i['finding']['severity'] is None for i in items)
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
                   for c in guard_claims(ctx))
    elif oracle == 'false_claims':
        objective = '\n'.join(field(subject,artifact,'objective_texts'))
        assert not any(text in objective for text in INPUT['profiles'][case['profile']])
        admitted = {c['binding_ref'] for c in guard_claims(ctx) if c['status'] == 'SOURCE_FACT_BINDING_VERIFIED'}
        assert set(field(subject,artifact,'objective_binding_refs')) <= admitted
    elif oracle == 'roundtrip':
        integrity_hash(subject,artifact)
        loaded = subject.load(deepcopy(artifact['document']),artifact['html'],ctx,expected_digest=artifact['digest'])
        assert loaded['document'] == artifact['document'] and loaded['html'] == artifact['html']
        again = build(subject,positive_context(case['scenario']))
        assert again['document'] == artifact['document'] and again['html'] == artifact['html']
    elif oracle == 'tamper':
        if case['field'] == 'evidence':
            for leaf in ('evidence_ref','url'):
                path = '/issues/0/fact_claim/fact/source/citation/'+leaf
                old = pointer(artifact['document'],path)
                changed = mutate_json(artifact,path,old+'-foreign')
                changed['draft_ref'] = 'rd-'+hashlib.sha256(canonical({k:v for k,v in changed.items() if k != 'draft_ref'})).hexdigest()
                load_rejects(subject,artifact,ctx,changed)
                load_rejects(subject,artifact,ctx,changed,expected_digest=changed['draft_ref'])
        else:
            changed = deepcopy(items)
            assert changed
            path = subject.origins['issue.'+case['field']]
            assert path['kind'] == 'json'
            head,key = path['pointer'].rsplit('/',1)
            parent = pointer(changed[0],head)
            old = parent[key]
            parent[key] = str(old)+' 攻击性改写' if isinstance(old,str) else {'forged':'unrelated source'}
            load_rejects(subject,artifact,ctx,mutate(subject,artifact,'issues',changed))
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
            bundle = next(b for b in bad['guard_inputs'] if any(c['status'] == 'HUMAN_REVIEW_REQUIRED' for c in b['guard']['claims']))
            doc = bundle['guard']
            row = next(c for c in doc['claims'] if c['status'] == 'HUMAN_REVIEW_REQUIRED')
            row['status'] = 'SOURCE_FACT_BINDING_VERIFIED'
            doc['guard_ref'] = 'cg-'+document_hash({k:v for k,v in doc.items() if k != 'guard_ref'})
            assert bad['guard_inputs'] != ctx['guard_inputs'] and bad['pins'] == ctx['pins']
            with pytest.raises(subject.rejection_types):
                subject.build(bad,revision=1,created_at=INPUT['report_time'])
        if oracle == 'layout_tamper':
            old = field(subject,artifact,'language').encode('utf-8')
            token = b'lang="'+old+b'"'
            assert token in artifact['html']
            changed_html = artifact['html'].replace(token,b'lang="en-US"',1)
            load_rejects(subject,artifact,ctx,html=changed_html)
        roles = {'scope_tamper':['scope'], 'metadata_tamper':['captured_at','version','coverage'],
            'layout_tamper':['layout_version','asset_version'],
            'guard_tamper':['guard_ref'], 'approval_tamper':['approval_status','private','shareable']}[oracle]
        for role in roles:
            old = field(subject,artifact,role)
            value = not old if isinstance(old,bool) else old+1 if isinstance(old,int) else 'forged-codex1' if isinstance(old,str) else {'forged':True}
            if role == 'approval_status':
                value = 'APPROVED'
            load_rejects(subject,artifact,ctx,mutate(subject,artifact,role,value))
    elif oracle == 'version_pin':
        newer = build(subject,positive_context(case['scenario']),revision=2)
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
                zero = build(subject,positive_context('healthy200'))
                assert field(subject,zero,'issues') == [] and len(items) == 1
                integrity_hash(subject,zero)
                comparison = memo['comparison']
                assert comparison['one_html_sha256'] == hashlib.sha256(artifact['html']).hexdigest()
                assert comparison['zero_html_sha256'] == hashlib.sha256(zero['html']).hexdigest()
                assert comparison['zero_observed_quote'] in ''.join(HtmlAudit(zero['html']).parts)
                image = Path(comparison['zero_screenshot_path'])
                assert image.is_file() and hashlib.sha256(image.read_bytes()).hexdigest() == comparison['zero_screenshot_sha256']


# Owner retains all 53 original invalid-request denials and adds incomplete M08.
DENIALS = support.denied_nodes()+[dict(id='M08_INCOMPLETE',expected_code='REPORT_MISSING_OR_AMBIGUOUS_FACT')]
assert len(DENIALS) == 54
@pytest.mark.parametrize('denial',DENIALS,ids=[d['id'] for d in DENIALS])
def test_companion_original_invalid_request_denial(subject,denial):
    if denial['id'] == 'M08_INCOMPLETE':
        context = support.request_context('partial/duplicate_contact')
    else:
        case = next(c for c in CASES if c['id'] == denial['id'])
        context = support.original_context(case['scenario'],case.get('profile','truthful'))
    before = canonical({k:context[k] for k in ('guard_inputs','pins')})
    with pytest.raises(subject.rejection_types) as rejected:
        subject.build(context,revision=1,created_at=INPUT['report_time'])
    assert str(rejected.value) == denial['expected_code']
    assert len(str(rejected.value)) <= 256 and SPECIAL_TEXT not in str(rejected.value)
    assert before == canonical({k:context[k] for k in ('guard_inputs','pins')})
