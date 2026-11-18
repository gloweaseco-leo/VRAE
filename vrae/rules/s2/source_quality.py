"""INFO-03 / TECH-02 source clues over a pinned S2 parent, never native rules.

HTTP markup is not rendered accessibility, language quality or image loading.
Only already retained objects and capture metadata are read; there is no IO port.
"""
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from html import unescape
from urllib.parse import urljoin, urlsplit

from vrae.collection.manifest import document_hash
from vrae.collection.policy import canonical_url
from vrae.evidence import EvidencePack
from vrae.industry.l2_v1.pack import IndustryPins, load_s2
from vrae.reporting.common import display_text
from vrae.rules.execution import _metadata, _records

from .contract import verify_s2_projection
from .static import StaticHTML, _cite, _evidence

VERSION = 's2-source-quality-1.0.0'
SOURCE_VERSION = 'retained-http-structure-1.0.0'
PARENT_VERSION = 's2-projection-1.2.0'
RULES = ('INFO-03', 'TECH-02')
SCOPE = ('tenant_id', 'run_id', 'policy_id', 'policy_version')


class SourceQualityError(ValueError):
    """Fixed error only; caller retains original signed current-task authority."""


def deny():
    raise SourceQualityError('S2_SOURCE_QUALITY_INTEGRITY')


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


@dataclass(frozen=True)
class PagePin:
    snapshot_ref: str
    url: str
    role: str
    observed_at: str
    model: str | None = None
    data_revision: str | None = None


@dataclass(frozen=True)
class SourceQualityPins:
    """Independent SERVER expectations, never HTTP/model data or authorization."""
    tenant_id: str
    run_id: str
    policy_id: str
    policy_version: int
    pack_ref: str
    parent_ref: str
    industry_pins: IndustryPins
    pages: tuple[PagePin, ...]
    observed_after: datetime
    observed_before: datetime
    parent_version: str = PARENT_VERSION
    quality_version: str = VERSION
    source_version: str = SOURCE_VERSION


class SourceHTML(StaticHTML):
    """Reuse the accepted conservative HTML subset and original UTF-8 offsets."""
    def __init__(self, raw):
        super().__init__(raw)
        self.nodes: list[dict] = []
        self.language: dict | None = None
        self.dynamic = False

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        token = self.get_starttag_text() or ''
        start = self.char_offset()
        span = self.span(start, start + len(token))
        if len(token.encode()) > 4096:
            self.ambiguous = True
        values = dict(attrs)
        if tag == 'html':
            if self.language is not None:
                self.ambiguous = True
            self.language = {'lang': values.get('lang'), 'span': span}
        if tag == 'script' and values.get('src'):
            self.dynamic = True
        if self.eligible() and (tag in ('img', 'abbr') or re.fullmatch('h[1-6]', tag)):
            self.nodes.append({'tag': tag, 'attrs': values, 'span': span})
            if len(self.nodes) > 128:
                self.ambiguous = True


def _time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        deny()
    return parsed


def _target(value, base):
    # Lookup only, NEVER fetch. No protocol/data URLs, credentials or cross-origin joins.
    if type(value) is not str or not value or len(value) > 2048 or any(ord(c) <= 32 for c in value):
        return None
    try:
        url = canonical_url(urljoin(base, value))
        parts = urlsplit(url)
        if (parts.scheme not in ('https', 'http') or parts.netloc != urlsplit(base).netloc
                or parts.username or parts.password or parts.fragment):
            return None
        return url
    except (ValueError, TypeError):
        return None


def _item(kind, state, reason, citations=(), **details):
    return {'kind': kind, 'state': state, 'reason': reason, 'citations': list(citations), 'details': details,
            'review': 'HUMAN_REVIEW_REQUIRED', 'native_fact_admission': 'NONE'}


def _resource(pack, record, src, records, held):
    target = _target(src, record[2]['final_url'])
    if target is None:
        return {'state': 'UNKNOWN', 'reason': 'UNSUPPORTED_OR_UNBOUND_RESOURCE_URL', 'actual_load': 'UNKNOWN'}
    matches = [r for r in records if r[0]['source_ref'] == record[0]['source_ref']
               and r[2]['url'] == target
               and held.observed_after <= _time(r[2]['observed_at']) <= held.observed_before]
    if len(matches) != 1:
        return {'state': 'UNKNOWN', 'reason': 'RESOURCE_NOT_UNAMBIGUOUSLY_CAPTURED', 'actual_load': 'UNKNOWN'}
    row = matches[0]
    ev, raw = _evidence(pack, pack.document, row)
    return {'state': 'CAPTURE_METADATA_ONLY', 'reason': 'RECORDED_GET_NOT_BROWSER_LOAD',
        'requested_url': target, 'response_metadata': _metadata(row),
        'metadata_authority': 'CAPTURE_MANIFEST_LOCATOR_NOT_AN_EVIDENCE_REF',
        'retained_body': raw is not None, 'retained_evidence_ref': ev['evidence_ref'] if ev else None,
        'retained_content_sha256': ev['content_sha256'] if ev else None, 'actual_load': 'UNKNOWN',
        'asset_format_and_decoding': 'UNKNOWN'}


def _analyze(pack, record, held, profile):
    doc = pack.document
    ev, raw = _evidence(pack, doc, record)
    if record[2]['status'] == 'ACCESS_BLOCKED':
        return None, 'ACCESS_BLOCKED', 'SOURCE_ACCESS_BLOCKED'
    if record[1]['http_status'] != 200 or ev is None or raw is None or not raw:
        return None, 'UNKNOWN', 'RETAINED_HTTP_200_BYTES_REQUIRED'
    if len(raw) > 131072:
        return None, 'UNKNOWN', 'SOURCE_BYTE_BOUND'
    try:
        parsed = SourceHTML(raw)
        display_text(parsed.text, 131072)
        parsed.finish()
        if parsed.ambiguous:
            return None, 'UNKNOWN', 'AMBIGUOUS_OR_UNSUPPORTED_HTML'
    except Exception:  # noqa: BLE001 -- unsupported parser inputs yield no negative finding
        return None, 'UNKNOWN', 'UNSUPPORTED_UTF8_OR_SOURCE_TEXT'
    info, tech = [], []
    def cite(span):
        return _cite(ev, span) | {'url': record[2]['url'], 'observed_at': record[2]['observed_at']}
    if parsed.language and parsed.language['lang'] is not None:
        info.append(_item('DECLARED_LANGUAGE', 'OBSERVED', 'AUTHOR_DECLARATION_NOT_LANGUAGE_QUALITY',
            [cite(parsed.language['span'])], declared_language=parsed.language['lang']))
    text_spans = parsed.texts
    aliases = sorted({name for names in profile['labels'].values() for name in names})
    unit_names = set(profile['units'])
    for span in text_spans:
        text = unescape(span['quote'])
        acronyms = sorted(set(re.findall(r'\b[A-Z][A-Z0-9]{1,9}\b', text)) - unit_names
                          - {'DO', 'NOT', 'NO', 'NA', 'TBD'})
        terms = [term for term in aliases if re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)', text, re.IGNORECASE)]
        if acronyms or terms or re.search(r'[\u3400-\u9fff]', text):
            info.append(_item('TECHNICAL_TEXT_REVIEW', 'REVIEW_REQUIRED', 'SOURCE_CLUE_NOT_SEMANTIC_JUDGMENT',
                [cite(span)], acronyms=acronyms, configured_term_labels=terms,
                has_cjk_source_text=bool(re.search(r'[\u3400-\u9fff]', text)),
                english_quality='UNKNOWN', terminology_correctness='UNKNOWN'))
    for node in parsed.nodes:
        attrs = node['attrs']
        if node['tag'] == 'abbr':
            info.append(_item('ABBREVIATION_TITLE', 'REVIEW_REQUIRED', 'TITLE_PRESENCE_NOT_CORRECT_DEFINITION',
                [cite(node['span'])], source_title=attrs.get('title'), definition_correctness='UNKNOWN'))
    if not info:
        info.append(_item('TEXT_AVAILABILITY', 'UNKNOWN', 'NO_SUPPORTED_TECHNICAL_TEXT_CLUE'))
    headings = [n for n in parsed.nodes if n['tag'].startswith('h')]
    for i, node in enumerate(headings):
        previous = int(headings[i - 1]['tag'][1]) if i else None
        level = int(node['tag'][1])
        citations = [cite(node['span'])]
        if previous is not None and level > previous + 1:
            citations.insert(0, cite(headings[i - 1]['span']))
        tech.append(_item('HEADING_SOURCE_ORDER', 'REVIEW_REQUIRED',
            'SOURCE_LEVEL_SKIP' if previous is not None and level > previous + 1 else 'HEADING_TAG_OBSERVED',
            citations, level=level, previous_level=previous, visual_hierarchy='UNKNOWN',
            accessibility_conformance='UNKNOWN'))
    images = [n for n in parsed.nodes if n['tag'] == 'img']
    records = _records(doc)
    for node in images:
        attrs = node['attrs']
        kind = ('ALT_ATTRIBUTE_ABSENT' if 'alt' not in attrs else 'ALT_EMPTY_PURPOSE_REVIEW'
                if not (attrs['alt'] or '').strip() else 'ALT_TEXT_PRESENT_MEANING_UNREVIEWED')
        tech.append(_item('IMAGE_ALT_SOURCE', 'REVIEW_REQUIRED', kind, [cite(node['span'])],
            alt=attrs.get('alt'), declared_role=attrs.get('role'), accessible_name='UNKNOWN',
            decorative_intent='UNKNOWN', declared_hidden='hidden' in attrs,
            resource=_resource(pack, record, attrs.get('src'), records, held),
            srcset_selection='UNKNOWN' if 'srcset' in attrs else 'NOT_RECORDED'))
    if not images:
        tech.append(_item('IMAGE_ALT_SUBSET', 'NOT_APPLICABLE', 'NO_LITERAL_IMG_IN_COMPLETE_SELECTED_SOURCE',
            [cite(parsed.span(0, min(256, len(parsed.text))))],
            scope='LITERAL_IMG_SUBSET_ONLY', css_svg_canvas_and_js_images='UNKNOWN'))
    if not headings:
        tech.append(_item('HEADING_SUBSET', 'UNKNOWN', 'NO_HEADING_IN_SUPPORTED_SOURCE_SUBSET'))
    if parsed.dynamic:
        info.append(_item('RENDERED_TEXT', 'UNKNOWN', 'JAVASCRIPT_RENDERING_NOT_OBSERVED'))
        tech.append(_item('RENDERED_RESOURCES', 'UNKNOWN', 'JAVASCRIPT_ASSETS_AND_LOAD_NOT_OBSERVED'))
    if len(info) > 128 or len(tech) > 128:
        return None, 'UNKNOWN', 'ITEM_BOUND_NO_PARTIAL_NEGATIVE_JUDGMENT'
    return {'INFO-03': info, 'TECH-02': tech}, 'SOURCE_CLUES_ONLY', 'RETAINED_HTTP_SOURCE_SUBSET'


def evaluate_source_quality(pack: EvidencePack, parent: dict, *, held: SourceQualityPins) -> dict:
    """No parent/S3/native contract shape is modified; all identities are held."""
    try:
        if (type(pack) is not EvidencePack or type(held) is not SourceQualityPins
                or type(held.industry_pins) is not IndustryPins or held.parent_version != PARENT_VERSION
                or held.quality_version != VERSION or held.source_version != SOURCE_VERSION
                or type(held.pages) is not tuple or not 1 <= len(held.pages) <= 8
                or type(held.policy_version) is not int
                or any(type(getattr(held, k)) is not str for k in ('tenant_id', 'run_id', 'policy_id', 'pack_ref', 'parent_ref'))
                or any(type(t) is not datetime or t.utcoffset() is None for t in
                       (held.observed_after, held.observed_before)) or held.observed_after > held.observed_before):
            deny()
        scope = {k: getattr(held, k) for k in SCOPE}
        verify_s2_projection(parent, pack, expected_pack_ref=held.pack_ref, trusted_scope=scope,
            expected_projection_ref=held.parent_ref, expected_projection_version=held.parent_version,
            industry_pins=held.industry_pins)
        config = load_s2(tenant_id=held.tenant_id, version=held.industry_pins.version,
                         profile_id=held.industry_pins.profile_id)
        if config['industry_ref'] != held.industry_pins.industry_ref:
            deny()
        snapshots = {s['snapshot_ref']: s for s in pack.document['snapshots']}
        records = {r[2]['snapshot_ref']: r for r in _records(pack.document)}
        if len({p.snapshot_ref for p in held.pages if type(p) is PagePin}) != len(held.pages):
            deny()
        rows, coverage = [], []
        for selected in held.pages:
            if type(selected) is not PagePin or any(type(getattr(selected, k)) is not str
                    for k in ('snapshot_ref', 'url', 'role', 'observed_at')):
                deny()
            snap = snapshots[selected.snapshot_ref]
            if snap['url'] != selected.url or snap['observed_at'] != selected.observed_at or not (
                    held.observed_after <= _time(snap['observed_at']) <= held.observed_before):
                deny()
            record = records.get(selected.snapshot_ref)
            if record is None:
                if selected.role != 'BROWSER_CAPTURE' or selected.model is not None or selected.data_revision is not None:
                    deny()
                analyzed, state, reason = None, 'UNKNOWN', 'BROWSER_V1_ALT_RESOURCE_FULL_HIERARCHY_NOT_RETAINED'
                meta = {'snapshot_ref': selected.snapshot_ref, 'url': selected.url, 'observed_at': selected.observed_at,
                        'source_ref': snap['source_ref'], 'authority': 'CAPTURE_METADATA_ONLY'}
                retained = False
            else:
                if record[1]['role'] != selected.role:
                    deny()
                if selected.model is not None or selected.data_revision is not None:
                    if type(selected.model) is not str or type(selected.data_revision) is not str:
                        deny()
                    matching = [r for r in parent['industrial_projection']['rows']
                        if r['observation']['rule_id'] == 'INFO-02' and r['model'] == selected.model
                        and any(p['snapshot_ref'] == selected.snapshot_ref for p in r['source_pages'])
                        and r['details'].get('data_revision') == selected.data_revision]
                    if len(matching) != 1:
                        deny()
                analyzed, state, reason = _analyze(pack, record, held, config['profile'])
                meta = _metadata(record)
                retained = _evidence(pack, pack.document, record)[1] is not None
            coverage.append({'snapshot_ref': selected.snapshot_ref, 'role': selected.role,
                             'raw_http_retained': retained, 'supported_source': analyzed is not None})
            for rule in RULES:
                row = {'rule_id': rule, 'quality_version': VERSION, 'source_version': SOURCE_VERSION,
                    'scope': scope, 'pack_ref': held.pack_ref, 'parent_s2p_ref': held.parent_ref,
                    'selection': asdict(selected), 'response_metadata': meta, 'state': state, 'reason': reason,
                    'items': analyzed[rule] if analyzed else [_item('INPUT_COVERAGE', state, reason)],
                    'native_fact_admission': 'NONE', 'semantic_quality': 'UNKNOWN',
                    'buyer_impact': ('技术缩写、术语或语言切换可能增加采购核对工作，是否影响理解须人工确认。'
                        if rule == 'INFO-03' else '替代文字、源码标题组织或资源响应线索可能影响资料获取，实际障碍与影响须复核。'),
                    'questions': ('请企业工程责任人提供面向目标买家的英文术语展开、型号/版次和工况说明。'
                        if rule == 'INFO-03' else '请确认图片用途、合适的替代文字、标题关系及实际资源；未采集资产不判为坏图。'),
                    'rebuild_proposal': {'status': 'HUMAN_REVIEW_REQUIRED', 'target_url': selected.url,
                        'owner': '企业工程资料责任人/编辑与前端实施人员',
                        'action': ('按已确认资料组织术语表、英文参数说明和版本关联。' if rule == 'INFO-03'
                                   else '逐张确认图片用途后补充恰当alt，按实际内容组织标题并核对获准资源响应。'),
                        'acceptance': '人工确认后在同型号/新资料版本的获准来源重新采证，记录原文与定位；不代签语义或WCAG合规。',
                        'service_fit': '标准资料组织/页面模板候选；额外工程或交互系统需另审',
                        'price': None, 'schedule': None}}
                row['candidate_id'] = 's2qc-' + document_hash(row)
                rows.append(row)
        result = {'kind': 'S2SourceQualityCandidate', 'quality_version': VERSION, 'source_version': SOURCE_VERSION,
            'authority': 'READ_ONLY_SOURCE_CLUES_NOT_RULEEXECUTION_FINDING_OR_GUARD',
            'pack_ref': held.pack_ref, 'parent_s2p_ref': held.parent_ref, 'parent_version': held.parent_version,
            'scope': scope, 'industry_ref': held.industry_pins.industry_ref, 'rows': rows,
            'coverage': {'unit': 'EXPLICITLY_SELECTED_CAPTURE_SNAPSHOT', 'selected': len(coverage),
                'raw_http_retained': sum(p['raw_http_retained'] is True for p in coverage),
                'supported_source': sum(p['supported_source'] is True for p in coverage), 'pages': coverage,
                'unselected_snapshots': len(snapshots) - len(coverage), 'whole_site_denominator': None},
            'quality': {'status': 'NOT_EVALUABLE', 'independent_gold': 0, 'precision': None},
            'limitations': ['SOURCE_HTML_NOT_RENDERED_DOM', 'NO_LANGUAGE_SEMANTIC_OR_READER_INTENT_APPROVAL',
                'NO_ASSET_CAPTURE_BROWSER_LOADING_OR_NETWORK_EXPANSION', 'NO_WCAG_SEO_RANKING_OR_SITE_WIDE_SCORE',
                'RECORDED_SCOPE_NOT_CURRENT_SIGNED_AUTHORIZATION', 'PARENT_S2P_AND_LEGACY_ENABLED_RULES_UNCHANGED'],
            'private': True, 'shareable': False, 'is_report': False}
        if len(encode(result)) > 1_000_000:
            deny()
        result['quality_ref'] = 's2q-' + document_hash(result)
        return json.loads(encode(result))
    except SourceQualityError:
        raise
    except Exception:  # noqa: BLE001 -- fail closed without source or identity details
        raise SourceQualityError('S2_SOURCE_QUALITY_INTEGRITY') from None


def verify_source_quality(value, pack, parent, *, held, expected_quality_ref):
    try:
        if type(expected_quality_ref) is not str or not re.fullmatch(r's2q-[0-9a-f]{64}', expected_quality_ref):
            deny()
        expected = evaluate_source_quality(pack, parent, held=held)
        if expected['quality_ref'] != expected_quality_ref or encode(value) != encode(expected):
            deny()
    except Exception:  # noqa: BLE001 -- fail closed without source or identity details
        raise SourceQualityError('S2_SOURCE_QUALITY_INTEGRITY') from None
