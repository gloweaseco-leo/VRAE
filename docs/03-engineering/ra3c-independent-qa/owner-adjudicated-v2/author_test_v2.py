"""One-time auditable V1->Owner V2 authoring; never edits original source."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

PREFIX = '''"""OWNER_ADJUDICATED_RA3C_QA_V2; original V1/14 sources remain immutable."""
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


'''

COMPANIONS = '''

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
'''


def main():
    target = HERE/'test_acceptance_v2.py'
    assert not target.exists(), 'Never overwrite a versioned V2 test'
    original = (ROOT/'tests/reporting/test_ra3c_independent_acceptance.py').read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(original).hexdigest() == '300f3a877684c3a174fec7c8e0feb2fcc7809479f4ccd201098fed6ed61afedc'
    text = original.decode()
    node = next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name == 'test_independent_product_acceptance')
    lines = text.splitlines(keepends=True)
    before = ''.join(lines[node.decorator_list[0].lineno-1:node.end_lineno])
    after = before
    changes = []
    def replace(old,new,reason,count=1):
        nonlocal after
        assert after.count(old) == count, (reason,after.count(old))
        after = after.replace(old,new)
        changes.append(dict(reason=reason,before=old,after=new,replacements=count))
    def between(start,end,new,reason):
        old = after[after.index(start):after.index(end,after.index(start))]
        replace(old,new,reason)
    replace('def test_independent_product_acceptance(', 'def test_owner_adjudicated_business_objective(', 'Explicit new V2 name, all 64 original IDs preserved')
    replace("ctx = prepare_context(case['scenario'],case.get('profile','truthful'))", "ctx = positive_context(case['scenario'])", 'M02/M07/M08: explicit separate admissible request; original requests retained as companion denials')
    replace("    if oracle in ('cross_pack','guard_pins'):\n", "    if oracle in ('cross_pack','guard_pins'):\n        build(subject,ctx)  # require real valid baseline before attacking held pins\n", 'Non-vacuous guard/source attack baseline')
    replace("prepare_context('healthy200')", "positive_context('healthy200')", 'Explicit source-backed positive zero request',count=2)
    replace("('expected_guard_ref','cg-')", "('expected_guard_refs','cg-')", 'M01 native independently held plural guard refs')
    replace("bad['pins'][key] = prefix+'0'*64", "bad['pins'][key] = [prefix+'0'*64] if key == 'expected_guard_refs' else prefix+'0'*64", 'Tamper actual native ref collection, never derive held refs')
    start = "    if oracle == 'false_claims' or case['id'] in ('E03','E04','E05','E07','E08'):"
    end = "    record_property('acceptance_path','ACTUAL_DRAFT_INSPECTED')"
    between(start,end,"""    if oracle == 'false_claims':
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
""", 'M02 separate real report plus genuine-ID attack; original hostile-source refusal policy unchanged')
    replace("assert field(subject,artifact,'scores') in (None,[],{})", "assert not subject.score_fields(artifact)\n        assert all(i['finding']['severity'] is None for i in items)", 'M06 actual native structural absence, no manufactured null; preserve no invented severity')
    replace("for c in ctx['guard'].document['claims']", "for c in guard_claims(ctx)", 'M05 actual separately held native per-claim guard collections',count=2)
    replace("prepare_context(case['scenario'])", "positive_context(case['scenario'])", 'Deterministic and version positive requests remain separately pinned',count=2)
    start = "    elif oracle == 'tamper':"
    end = "    elif oracle == 'html_tamper':"
    between(start,end,"""    elif oracle == 'tamper':
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
""", 'M04 mutate actual nested citation with old and resealed ref; original editorial tamper gate retained')
    start = "        if oracle == 'guard_tamper':"
    end = "        roles = {'scope_tamper':"
    between(start,end,"""        if oracle == 'guard_tamper':
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
""", 'M03 real HTML language bytes; D08 real plural guard bundle and held refs, no JSON language invention')
    replace("'layout_tamper':['language','layout_version','asset_version']", "'layout_tamper':['layout_version','asset_version']", 'M03 HTML language already attacked; actual renderer/asset JSON still attacked')
    output = PREFIX+after+COMPANIONS
    compile(output,str(target),'exec')
    target.write_text(output,encoding='utf-8')
    (HERE/'V1_TO_V2_FUNCTION.diff').write_text(''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='V1_frozen_business_function',tofile='OWNER_ADJUDICATED_RA3C_QA_V2_business_function')),encoding='utf-8')
    (HERE/'V1_TO_V2_CHANGES.json').write_text(json.dumps(dict(version='OWNER_ADJUDICATED_RA3C_QA_V2',
        authority='PR48 issuecomment-6815825564',original_test_sha256=hashlib.sha256(original).hexdigest(),
        original_objectives=64,dropped_objectives=0,companion_denials=54,changes=changes),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('V2 source authored: 64 preserved objectives +54 explicit denial controls; original test unchanged')


if __name__ == '__main__':
    main()
