"""Actual native transport / audited read-only projections. No incoming repair."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ra3c_v2_adapter_source',HERE/'support.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
v1 = support.v1


def origin(pointer,root=None):
    result = dict(kind='json',pointer=pointer)
    if root:
        result['root'] = root
    return result


ORIGINS = {role:origin(path) for role,path in {
    'issues':'/issues','native_report':'/native_report_version','private':'/private',
    'approval_status':'/approval_status','shareable':'/shareable','scope':'/scope',
    'coverage':'/recorded_coverage','unchecked':'/limitations',
    'captured_at':'/examined_pages/0/captured_at','version':'/metadata/version',
    'layout_version':'/renderer_version','asset_version':'/renderer_asset_sha256',
    'guard_ref':'/pins/expected_guard_refs','issue.buyer_task':'/finding/buyer_task',
    'issue.target_status':'/target_response/http_status','issue.fact':'/fact_claim/text',
    'issue.impact':'/proposals/impact/text','issue.impact_status':'/proposals/impact/status',
    'issue.action':'/proposals/action/text','issue.action_status':'/proposals/action/status',
    'issue.recheck':'/proposals/recheck/text','issue.finding_id':'/finding/finding_id',
}.items()}


class Adapter:
    def __init__(self,reporting):
        self.production_module = reporting
        self.rejection_types = (reporting.ReportError,)
        self.origins = deepcopy(ORIGINS)
        self.digest_recipe = dict(kind='canonical_doc',self_digest_paths=['/draft_ref'])
        self.binding = json.loads((HERE/'fixtures/candidate-binding.json').read_text(encoding='utf-8'))
        assert self.binding['candidate_sha'] == os.environ['VRAE_RA3C_QA_V2_CANDIDATE_SHA']
        for name,info in self.binding['reporting_files'].items():
            path = Path(reporting.__file__).parent/name
            assert hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest() == info['sha256'], name

    def arguments(self,context,revision,created_at=None,submitted=False):
        rows = self.binding['requests'][context['scenario']]
        held = deepcopy(rows.get(str(revision),rows['1']))
        metadata = held['metadata']
        if submitted:
            metadata['version'] = revision
            metadata['created_at'] = created_at
        # Source/guard refs are externally held in the request, not recovered
        # from submitted guard/document bytes. No string or binding substitution.
        pins = dict(deepcopy(context['pins']),**held['pins'])
        return context['pack'],context['package'],context['guard_inputs'],metadata,pins

    @staticmethod
    def artifact(native,producer):
        return dict(document=native.document,html=native.html_bytes,digest=native.ref,
            origin_module=producer.__module__)

    def build(self,context,revision=1,created_at=None):
        pack,package,bundles,metadata,pins = self.arguments(context,revision,created_at,True)
        native = self.production_module.build_draft(pack,package,bundles,metadata,**pins)
        return self.artifact(native,self.production_module.build_draft)

    def load(self,document,html,context,*,expected_digest,request_revision=None):
        revision = context['request_revision'] if request_revision is None else request_revision
        pack,package,bundles,metadata,pins = self.arguments(context,revision)
        native = self.production_module.ReportDraft.load(document,html,pack,package,bundles,
            metadata,expected_draft_ref=expected_digest,**pins)
        return self.artifact(native,self.production_module.ReportDraft.load)

    def render(self,artifact,context,request_revision=1):
        pack,package,bundles,metadata,pins = self.arguments(context,request_revision)
        return self.production_module.render(artifact['document'],artifact['html'],pack,package,
            bundles,metadata,expected_draft_ref=artifact['digest'],**pins)

    @staticmethod
    def html_nodes(artifact,tag,key=None,value=None):
        return [n for n in v1.HtmlAudit(artifact['html']).nodes if n['tag'] == tag and
            (key is None or (value in n['attrs'].get(key,'').split() if key == 'class' else n['attrs'].get(key) == value))]

    def read(self,artifact,role,issue=None):
        if role in self.origins:
            entry = self.origins[role]
            root = issue if issue is not None else artifact['document']
            return v1.pointer(root,entry['pointer'])
        if role == 'language':
            nodes = self.html_nodes(artifact,'html')
            assert len(nodes) == 1
            return nodes[0]['attrs']['lang']
        selectors = {'main_text':('main','id','report'),'privacy_text':('div','class','private-bar'),
            'service_scope_text':('section','class','next')}
        if role in selectors:
            nodes = self.html_nodes(artifact,*selectors[role])
            assert len(nodes) == 1
            return ' '.join(''.join(nodes[0]['text']).split())
        if role in ('objective_texts','objective_binding_refs'):
            key = 'text' if role == 'objective_texts' else 'binding_ref'
            return [row[key] for row in self.objective_projection(artifact)]
        if role == 'issue.evidence':
            assert issue is not None
            source = issue['fact_claim']['fact']['source']
            cite = source['citation']
            return dict(pack_ref=artifact['document']['pins']['expected_pack_ref'],
                observed_at=cite['observed_at'],evidence_ref=cite['evidence_ref'],
                byte_start=source['byte_start'],byte_end=source['byte_end'],quote=source['quote'],
                source_url=cite['url'],captured_scope=artifact['document']['scope'],
                target_status=issue['target_response']['http_status'],href=cite['raw_href'],
                binding_ref=issue['fact_claim']['binding_ref'])
        raise AssertionError('V2_UNMAPPED_NATIVE_ROLE:'+role)

    @staticmethod
    def objective_projection(artifact):
        doc = artifact['document']
        claims = [(f'/issues/{i}/fact_claim',item['fact_claim']) for i,item in enumerate(doc['issues'])]
        claims += [(f'/positive_source_claims/{i}',claim) for i,claim in enumerate(doc['positive_source_claims'])]
        rows = []
        for pointer,claim in claims:
            assert v1.pointer(doc,pointer) == claim
            assert isinstance(claim['text'],str) and isinstance(claim['binding_ref'],str)
            rows.append(dict(pointer=pointer,text=claim['text'],binding_ref=claim['binding_ref']))
        return rows

    @staticmethod
    def score_fields(artifact):
        forbidden = {'score','scores','site_score','whole_site_score','roi','google_rank','sales_loss','confidence'}
        def walk(value,path=''):
            if isinstance(value,dict):
                return [path+'/'+k for k in value if k.lower() in forbidden]+[
                    p for k,v in value.items() for p in walk(v,path+'/'+k)]
            if isinstance(value,list):
                return [p for i,v in enumerate(value) for p in walk(v,path+'/'+str(i))]
            return []
        return walk(artifact['document'])


def bind(reporting):
    return Adapter(reporting)
