"""Owner-scoped actual transport; unchanged proposals/guards, no output synthesis."""
from copy import deepcopy
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('codex1_preflight_shapes',HERE.parent/'adapter-preflight-v1/adapter_draft.py')
shapes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shapes)
MappingNotBound = shapes.MappingNotBound


class Origins(dict):
    def __missing__(self,key):
        gaps = {'objective_texts':'M05','objective_binding_refs':'M05','scores':'M06'}
        raise MappingNotBound('QA_MAPPING_NOT_BOUND:'+gaps.get(key,'UNMAPPED')+':'+key)


class Nodes(HTMLParser):
    def __init__(self,html):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.feed(html.decode('utf-8'))

    def handle_starttag(self,tag,attrs):
        self.nodes.append((tag,dict(attrs)))


class Adapter:
    def __init__(self,reporting):
        self.production_module = reporting
        self.rejection_types = (reporting.ReportError,)
        self.origins = Origins(deepcopy(shapes.JSON_ORIGINS))
        self.digest_recipe = deepcopy(shapes.DIGEST_RECIPE)
        self.requests = json.loads((HERE/'request-pins.json').read_text(encoding='utf-8'))['records']
        self.held_requests = {}

    def request(self,context,revision,created_at):
        # Select externally held valid revision pins; submitted malformed values
        # are passed through against those pins, never repaired or rehashed.
        records = self.requests[context['scenario']]
        held = deepcopy(records.get(str(revision),records['1']))
        metadata = deepcopy(held['metadata'])
        metadata['version'] = revision
        metadata['created_at'] = created_at
        return metadata,held['pins']

    def extract(self,native,producer):
        output = shapes.artifact(native,producer)
        nodes = Nodes(output['html']).nodes
        locations = {'main_text':('main','id','report'),
            'privacy_text':('div','class','private-bar'),
            'service_scope_text':('section','class','next'),
            'language':('html','lang','zh-CN')}
        for role,(tag,key,value) in locations.items():
            indices = [i for i,(t,attrs) in enumerate(nodes) if t == tag and
                (value in attrs.get(key,'').split() if key == 'class' else attrs.get(key) == value)]
            if len(indices) != 1:
                raise MappingNotBound('QA_MAPPING_NOT_BOUND:HTML_ORIGIN:'+role)
            self.origins[role] = dict(kind='html',node_index=indices[0])
            if role == 'language':
                self.origins[role]['attribute'] = 'lang'
        return output

    def build(self,context,revision=1,created_at=None):
        metadata,request_pins = self.request(context,revision,created_at)
        pack,package,bundles,metadata,pins = shapes.native_arguments(context,metadata,request_pins)
        native = self.production_module.build_draft(pack,package,bundles,metadata,**pins)
        self.held_requests[native.ref] = (deepcopy(metadata),deepcopy(request_pins))
        return self.extract(native,self.production_module.build_draft)

    def load(self,document,html,context,*,expected_digest):
        if expected_digest not in self.held_requests:
            raise MappingNotBound('QA_MAPPING_NOT_BOUND:UNKNOWN_CALLER_REQUEST')
        metadata,request_pins = deepcopy(self.held_requests[expected_digest])
        pack,package,bundles,metadata,pins = shapes.native_arguments(context,metadata,request_pins)
        native = self.production_module.ReportDraft.load(document,html,pack,package,bundles,
            metadata,expected_draft_ref=expected_digest,**pins)
        return self.extract(native,self.production_module.ReportDraft.load)

    @staticmethod
    def project_objective_collection(document,field):
        # Owner M05: diagnostic projection only. Frozen field() cannot consume
        # this method; do not monkeypatch it or add fields to native JSON.
        if field not in ('text','binding_ref'):
            raise MappingNotBound('QA_MAPPING_NOT_BOUND:COLLECTION_FIELD')
        claims = [i['fact_claim'] for i in document['issues']]+document['positive_source_claims']
        return [c[field] for c in claims]


def bind(reporting):
    return Adapter(reporting)
