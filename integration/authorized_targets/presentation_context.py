"""Customer copy for independently retained subfacts; parent rule stays unchanged."""
from vrae.intelligence.qwen.source_values import value

COPY = {
    'ABOUT_TEXT': ('已在介绍路径页面保留静态正文；主体身份和内容真实性未核验。', 'Static text was retained on an about-path page; entity identity and authenticity are unverified.'),
    'SELF_DESCRIPTION': ('已记录供方自述的介绍文字；未认证企业资质。', 'Supplier-stated introduction text was retained; qualifications are not authenticated.'),
    'DECLARED_NAME': ('已记录供方明确标注的组织名称；未核验法定主体。', 'An explicitly supplier-stated organization name was retained; legal identity is unverified.'),
    'STATIC_CONTACT_LINK': ('已记录公开联系链接；可见性、消息送达和联系资料有效性未核验。', 'A public contact link was retained; visibility, message delivery and contact validity are unverified.'),
    'TITLE': ('已记录本次首页 HTML 的标题。', 'The title in the retained home-page HTML was recorded.'),
    'DESCRIPTION': ('已记录本次首页 HTML 的描述标签。', 'The description tag in the retained home-page HTML was recorded.'),
    'CANONICAL': ('已记录同站 canonical 标签；不代表收录或排名。', 'A same-site canonical tag was recorded; indexing and ranking are unverified.'),
}

LIMITS = {
    'NOT_IMPLEMENTED': ('本轮尚未实施此项自动检查，未据此评价网站。', 'This automated check is not implemented in this run; no website judgment is made.'),
    'APPLICABILITY_UNRESOLVED': ('本轮未建立此项所需的行业或应用适用关系。', 'Required industry or application applicability is unresolved.'),
    'HUMAN_REVIEW_REQUIRED': ('此项需要进一步人工核对，本轮未作确定判断。', 'This item requires further human review; no definitive judgment was made.'),
    'PARTIAL_EVIDENCE': ('已有部分来源观察；整体判断所需条件尚未全部核实。', 'Partial source observations are available; prerequisites for the complete check remain unverified.'),
    'VISIBILITY_OR_DELIVERY_UNVERIFIED': ('已有静态链接证据；可见性与询价送达未核验。', 'Static link evidence exists; visibility and inquiry delivery are unverified.'),
    'SOURCE_UNAVAILABLE': ('本轮未取得该项需要的可重放来源或代表页面。', 'Required replayable source or representative page was not captured.'),
    'PARSER_UNSUPPORTED': ('本轮静态解析方式无法完整核实此项，未据此判断内容缺失。', 'The bounded static parser cannot fully verify this item; missing website content is not established.'),
}


def limit(rule_id, row):
    if row['observation']['result'] != 'UNKNOWN':
        return None
    reason = row.get('reason', '')
    if rule_id in ('TRUST-02', 'TRUST-03', 'CTA-03', 'SEO-02', 'TECH-01', 'TECH-02'):
        kind = 'NOT_IMPLEMENTED'
    elif rule_id in ('DISC-03', 'INFO-02'):
        kind = 'APPLICABILITY_UNRESOLVED'
    elif rule_id == 'INFO-03':
        kind = 'HUMAN_REVIEW_REQUIRED'
    elif row.get('static_href_presence') == 'OBSERVED':
        kind = 'VISIBILITY_OR_DELIVERY_UNVERIFIED'
    elif 'HTML' in reason or 'PARSER' in reason or reason == 'STATIC_PRODUCT_SCOPE_AMBIGUOUS':
        kind = 'PARSER_UNSUPPORTED'
    elif reason in ('SOURCE_ROLE_NOT_CAPTURED', 'SOURCE_RETAINED_HTML_REQUIRED', 'PRODUCT_PATH_NOT_CAPTURED'):
        kind = 'SOURCE_UNAVAILABLE'
    else:
        kind = 'PARTIAL_EVIDENCE'
    return {'kind': kind, 'text': dict(zip(('zh', 'en'), LIMITS[kind]))}


def build(rule_id, row):
    result = []

    def add(kind, indexes, text):
        if indexes:
            result.append({'kind': kind, 'citation_indexes': indexes,
                           'text': dict(zip(('zh', 'en'), text)), 'is_rule_pass': False})

    if rule_id == 'TRUST-01':
        for fact in row.get('context_facts', []):
            if fact['kind'] in COPY:
                add(fact['kind'], fact['citation_indexes'], COPY[fact['kind']])
    if rule_id == 'CTA-01' and row.get('static_href_presence') == 'OBSERVED':
        add('STATIC_CONTACT_LINK', list(range(len(row['citations']))), COPY['STATIC_CONTACT_LINK'])
    if rule_id == 'SEO-01':
        for key in ('title', 'description', 'canonical'):
            if row.get('seo_signals', {}).get(key, {}).get('status') == 'OBSERVED':
                add(key.upper(), [i for i, c in enumerate(row['citations']) if c.get('fact_role') == key.upper()], COPY[key.upper()])
    if rule_id == 'INFO-01':
        pairs = {}
        names = set()
        for i, c in enumerate(row['citations']):
            text = value({'rule_id': 'INFO-01', 'source': {'citation': c}})
            if not text:
                continue
            if c.get('fact_role') == 'NAME':
                names.add(text)
                add('PRODUCT_NAME', [i], (f'已记录供方标注的名称：{text}；产品身份未核验。',
                    f'Supplier-stated name: {text}; product identity is unverified.'))
            elif c.get('fact_role') in ('SPEC_LABEL', 'SPEC_VALUE'):
                pairs.setdefault((c.get('product_scope_ref'), c['field_index']), {})[c['fact_role']] = (i, text)
        for pair in pairs.values():
            if set(pair) != {'SPEC_LABEL', 'SPEC_VALUE'}:
                continue
            (ki, label), (vi, val) = pair['SPEC_LABEL'], pair['SPEC_VALUE']
            if label.casefold() in ('item', 'product', 'product name', 'productname') and val in names:
                continue
            add('PRODUCT_FIELD', [ki, vi], (f'已记录供方标注：{label} = {val}；真实性及适用性未核验。',
                f'Supplier-stated {label} = {val}; accuracy and suitability are unverified.'))
    return result
