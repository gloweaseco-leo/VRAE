"""Unbound read-only interface draft; no candidate imports or output synthesis.

Owner preflight authority: PR48 issuecomment-6814793175. This is deliberately
not an executable Phase-B binding. See REPORT.md for actual mapping gaps.
"""

PROVISIONAL_SHA = '6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2'
SOURCE_KEYS = frozenset(('expected_pack_ref','expected_execution_ref',
    'expected_package_ref','expected_builder_version','expected_evaluator_version',
    'expected_scope','expected_guard_version','expected_guard_ref'))
REQUEST_PIN_KEYS = frozenset(('expected_metadata_sha256',
    'expected_reporting_version','expected_renderer_version'))
OPEN_GAPS = ('M01_REQUEST_METADATA','M02_PROPOSAL_VOCABULARY',
    'M03_LANGUAGE_MUTATION','M04_EVIDENCE_MUTATION',
    'M05_OBJECTIVE_COLLECTIONS','M06_ABSENT_SCORE','M07_EMPTY_GUARD',
    'M08_MULTI_PAGE_SINGLE_FACT')


def json_origin(pointer,*,root=None):
    result = {'kind':'json','pointer':pointer}
    if root is not None:
        result['root'] = root
    return result


# Only actual native document/item paths; there are no fabricated default fields.
JSON_ORIGINS = {role:json_origin(path) for role,path in {
    'issues':'/issues','native_report':'/native_report_version','private':'/private',
    'approval_status':'/approval_status','shareable':'/shareable',
    'coverage':'/recorded_coverage','unchecked':'/limitations',
    'captured_at':'/examined_pages/0/captured_at','scope':'/scope',
    'version':'/metadata/version','layout_version':'/renderer_version',
    'asset_version':'/renderer_asset_sha256','guard_ref':'/pins/expected_guard_refs/0',
    'issue.buyer_task':'/finding/buyer_task',
    'issue.target_status':'/target_response/http_status',
    'issue.fact':'/fact_claim/text','issue.finding_id':'/finding/finding_id',
    'issue.impact':'/proposals/impact/text','issue.impact_status':'/proposals/impact/status',
    'issue.action':'/proposals/action/text','issue.action_status':'/proposals/action/status',
    'issue.recheck':'/proposals/recheck/text',
}.items()}
JSON_ORIGINS['issue.evidence'] = {'kind':'object','members':{
    'pack_ref':json_origin('/pins/expected_pack_ref',root='document'),
    'observed_at':json_origin('/fact_claim/fact/source/citation/observed_at'),
    'evidence_ref':json_origin('/fact_claim/fact/source/citation/evidence_ref'),
    'byte_start':json_origin('/fact_claim/fact/source/byte_start'),
    'byte_end':json_origin('/fact_claim/fact/source/byte_end'),
    'quote':json_origin('/fact_claim/fact/source/quote'),
    'source_url':json_origin('/fact_claim/fact/source/citation/url'),
    'captured_scope':json_origin('/scope',root='document'),
    'target_status':json_origin('/target_response/http_status'),
    'href':json_origin('/fact_claim/fact/source/citation/raw_href'),
    'binding_ref':json_origin('/fact_claim/binding_ref'),
}}

# Selectors describe actual locations, not invented HTMLParser node indexes.
# Resolve only against actual candidate bytes at Phase B, with unambiguous DOM.
HTML_LOCATORS = {'main_text':'main#report','service_scope_text':'section.next',
    'privacy_text':'div.private-bar','language':'html[lang] attribute lang'}

# Native rd-ref hashes the complete document minus draft_ref; html_sha256 stays.
# Do not remove editorial_content_sha256 or html_sha256 or generate a new ref.
DIGEST_RECIPE = {'kind':'canonical_doc','self_digest_paths':['/draft_ref']}


class MappingNotBound(RuntimeError):
    """QA wiring limitation; never an expected production rejection type."""


def native_arguments(context,metadata,request_pins):
    """Structural singular-to-list wrapping only, with externally held metadata pins.

    No production call is made here. No missing metadata IDs/defaults are invented,
    no hashes recomputed, no claims filtered, no NOT_RUN guard dropped.
    """
    if set(context['pins']) != SOURCE_KEYS or set(request_pins) != REQUEST_PIN_KEYS:
        raise MappingNotBound('QA_MAPPING_NOT_BOUND:M01_REQUEST_METADATA')
    source = dict(context['pins'])
    held_guard = source.pop('expected_guard_ref')
    pins = dict(source,expected_guard_refs=[held_guard],**request_pins)
    bundles = [{'interpretation':context['interpretation'],'bindings':context['bindings'],
                'guard':context['guard'].document}]
    return context['pack'],context['package'],bundles,metadata,pins


def artifact(native,producer):
    """Exact output fields only; no renderer, rehashing or document augmentation."""
    return {'document':native.document,'html':native.html_bytes,
            'digest':native.ref,'origin_module':producer.__module__}


def native_build(reporting,context,metadata,request_pins):
    pack,package,bundles,metadata,pins = native_arguments(context,metadata,request_pins)
    native = reporting.build_draft(pack,package,bundles,metadata,**pins)
    return artifact(native,reporting.build_draft)


def native_load(reporting,document,html,context,metadata,request_pins,expected_digest):
    pack,package,bundles,metadata,pins = native_arguments(context,metadata,request_pins)
    native = reporting.ReportDraft.load(document,html,pack,package,bundles,metadata,
        expected_draft_ref=expected_digest,**pins)
    return artifact(native,reporting.ReportDraft.load)


def native_render(reporting,document,html,context,metadata,request_pins,expected_digest):
    pack,package,bundles,metadata,pins = native_arguments(context,metadata,request_pins)
    return reporting.render(document,html,pack,package,bundles,metadata,
        expected_draft_ref=expected_digest,**pins)


class DraftAdapter:
    def __init__(self,reporting):
        self.production_module = reporting
        self.rejection_types = (reporting.ReportError,)
        self.origins = JSON_ORIGINS
        self.digest_recipe = DIGEST_RECIPE
        self.mapping_state = 'QA_MAPPING_NOT_BOUND'
        self.open_gaps = OPEN_GAPS

    def build(self,context,revision=1,created_at=None):
        raise MappingNotBound('QA_MAPPING_NOT_BOUND:'+','.join(self.open_gaps))

    def load(self,document,html,context,*,expected_digest):
        raise MappingNotBound('QA_MAPPING_NOT_BOUND:'+','.join(self.open_gaps))


def bind(reporting):
    # Fail at fixture setup, rather than mislabelling mapping gaps as 64 business
    # failures. Do not point Phase-B pytest at this draft until Owner resolves gaps.
    raise MappingNotBound('QA_MAPPING_NOT_BOUND:'+','.join(OPEN_GAPS))
