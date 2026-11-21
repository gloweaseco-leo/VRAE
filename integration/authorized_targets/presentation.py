"""Bilingual delivery copy over verified DTO rows; no new facts or report authority."""

VERSION = 'vrae.diagnosis-presentation.v1'
TASK_LABELS = {
    'DISCOVER': ('找到目标产品', 'Find products'),
    'UNDERSTAND': ('理解型号与参数', 'Understand product information'),
    'TRUST': ('核对企业与产品资料', 'Check supplier information'),
    'INQUIRE': ('找到询价入口', 'Find an inquiry route'),
    'SEARCH_TECHNICAL': ('访问与页面结构', 'Access and page structure'),
}
RESULT_LABELS = {
    'PASS': ('本次有限检查已观察到', 'Observed in this bounded check'),
    'FAIL_WITH_EVIDENCE': ('发现有证据的异常', 'Issue supported by recorded evidence'),
    'UNKNOWN': ('本次尚未核实', 'Not verified in this check'),
    'ACCESS_BLOCKED': ('访问受限', 'Access blocked'),
    'NOT_APPLICABLE': ('本次不适用', 'Not applicable to this check'),
}
PASS_COPY = {
    'DISC-01': ('已记录首页导航到已采集分类页面的静态链接。',
                'A recorded homepage navigation link reached a captured category page.'),
    'DISC-02': ('已记录分类页面到已采集产品路径的静态链接；未核验产品身份。',
                'A recorded category link reached a captured product path; product identity is unverified.'),
    'CTA-02': ('已记录产品页面到询价路径的静态链接及目标响应；未提交表单或验证送达。',
               'A product-page inquiry link and target response were recorded; no form or delivery was tested.'),
    'INFO-01': ('已在产品路径页面记录显示名称和至少一组标签及值；型号身份、规格准确性、完整性和适用性未核验。',
                'A display name and a label-value pair were recorded on a product path; identity, accuracy, completeness and fit remain unverified.'),
    'SEO-01': ('已记录本次检查支持的页面标题及规范链接标签；不代表搜索引擎收录或排名。',
               'Supported title and canonical tags were recorded; indexing and ranking are unverified.'),
    'TRUST-01': ('已记录企业自述及公开介绍、联系资料；未核验主体身份或材料真实性。',
                 'Supplier-stated identity, introduction and contact context were recorded; authenticity is unverified.'),
}
REASONS = {
    'STATIC_PRODUCT_SCOPE_AMBIGUOUS': ('本次无法可靠归属产品正文区域，未将其他分类或产品的文字作为该产品资料。',
        'The product content region is unresolved; category or other-product text was not assigned to this product.'),
    'STATIC_PRODUCT_NAME_AMBIGUOUS': ('本次无法唯一识别产品名称或页面角色；不代表网站没有产品。',
        'The product name or page role could not be uniquely identified; website-wide product absence is unproven.'),
    'STATIC_HTML_AMBIGUOUS': ('本次静态结构存在解析歧义，相关内容仍需核对。',
        'The retained static structure is ambiguous to this parser and needs review.'),
    'STATIC_HTML_BOUND': ('此页的静态解析达到本次资源上限，未据此判断内容缺失。',
        'Static parsing reached the bounded resource limit; missing content is not established.'),
    'STATIC_FIELD_BOUND': ('候选字段超过本次解析上限，完整参数范围尚未核实。',
        'Candidate fields exceed the parsing bound; the full specification scope is unverified.'),
    'HTML_UNSUPPORTED_OR_AMBIGUOUS': ('本次静态解析无法唯一识别相关内容，不能据此判断网站缺失。',
        'The bounded static parser could not identify this content unambiguously; absence is not established.'),
    'FIELDS_MISSING_OR_AMBIGUOUS': ('本次未能唯一提取所需的参数对应关系；其他页面或资料尚未核实。',
        'Required field relationships were not unambiguously extracted; other pages or documents remain unverified.'),
    'NO_SUPPORTED_STATIC_CONTACT_HREF': ('本次保存的静态来源未建立支持的联系链接证据；不代表网站没有联系入口。',
        'No supported contact-link evidence was established in the retained scope; website-wide absence is unproven.'),
    'STATIC_HREF_OBSERVED_VISIBILITY_UNVERIFIED': ('已观察到静态联系或询价链接；可见性、目标可达性与送达均未完整核实。',
        'A static contact or inquiry link was observed; visibility, target availability and delivery remain unverified.'),
    'TARGET_NOT_OBSERVED': ('链接目标未得到本次可核实的响应证据，不能判定为坏链接。',
        'The target has no verifiable response in this capture; a broken link is not established.'),
    'TARGETS_OUTSIDE_CAPTURE_SCOPE': ('另有候选链接未访问，已折叠为范围限制，不作为网站缺陷。',
        'Other candidate links were not visited; this is a coverage limit, not a website defect.'),
    'SOURCE_ROLE_NOT_CAPTURED': ('本次未取得此路径步骤所需的代表页面。',
        'A representative source page for this path step was not captured.'),
    'SOURCE_RETAINED_HTML_REQUIRED': ('本次缺少可重放的来源正文，无法核实此项。',
        'Retained source HTML is unavailable for replay of this check.'),
    'PRODUCT_PATH_NOT_CAPTURED': ('本次没有可核实的产品路径页面证据。',
        'No supported product-path page was captured for this check.'),
    'PARTIAL_MISSING_AMBIGUOUS_OR_UNSUPPORTED_HEAD_SIGNALS': ('标题或规范链接等信号未被完整、唯一核实；不代表搜索表现差。',
        'Head signals were not fully and unambiguously verified; poor search performance is not established.'),
    'TRUST_PREREQUISITES_OR_CAPTURE_SCOPE_UNRESOLVED': ('企业自述、介绍或联系资料的证据范围尚未完整核实。',
        'The captured scope does not establish all required supplier identity, introduction and contact context.'),
}
RULE_LIMITS = {
    'DISC-03': ('尚无独立核实的行业或应用适用关系。', 'Industry or application relevance has not been independently verified.'),
    'INFO-02': ('行业适用要求及参数映射尚未核实，不能判定缺少必填参数。', 'Industry requirements and field applicability are unverified; missing mandatory fields cannot be inferred.'),
    'INFO-03': ('文字可理解性需要进一步审阅，本次没有作出确定的语言质量判断。', 'Comprehensibility needs review; no definitive language-quality judgment was made.'),
    'TRUST-02': ('材料上下文和真实性尚未核验；没有证书不等于缺少资质。', 'Proof context and authenticity are unverified; an absent certificate does not establish missing qualifications.'),
    'TRUST-03': ('尚未完成主体及公开联系资料的一致性核对。', 'Entity and public contact consistency have not been established.'),
    'CTA-03': ('本次未完成移动端可见性和布局观察。', 'Mobile visibility and layout were not observed in this check.'),
    'SEO-02': ('尚未完整核实产品文字及链接的可抓取性。', 'Product-text and link crawlability have not been fully verified.'),
    'TECH-01': ('现有元数据不足以形成此规则的完整证据判断；页面响应另见访问范围。', 'Existing metadata does not support a full rule judgment; page responses are listed in the capture scope.'),
    'TECH-02': ('本次未完成图片和基础可访问性的观察。', 'Image and basic accessibility checks were not completed.'),
}
OUTCOMES = {
    'COMPLETED_NO_RECOMMENDATIONS': ('自动分析已完成，本次未形成有充分依据的改善建议；已记录事实仍可查看。',
        'Analysis completed without a sufficiently supported improvement recommendation; recorded facts remain available.'),
    'PENDING': ('正在整理分析；已形成的规则事实可先查看。', 'Analysis is pending; existing rule facts can be viewed now.'),
    'NOT_RUN': ('本次页面检查未完成，AI 分析未运行。', 'Capture did not complete; AI analysis did not run.'),
    'COMPLETED': ('自动分析已完成，尚未经过正式人工审核。', 'Automated analysis completed; formal human review is still pending.'),
    'INSUFFICIENT_EVIDENCE': ('支持 AI 分析的证据不足；已核实的规则事实仍保留。', 'Evidence for AI analysis is insufficient; established rule facts remain available.'),
    'NOT_DISPATCHED': ('AI 请求未发出；已形成的规则事实仍可查看。', 'The AI request was not dispatched; existing rule facts remain available.'),
    'PROVIDER_FAILED': ('模型请求未完成；已形成的规则事实仍保留。', 'The model request failed; existing rule facts remain available.'),
    'VALIDATION_REJECTED': ('模型输出未通过校验；未采用该输出，已有规则事实仍保留。', 'Model output failed validation and was not used; existing rule facts remain available.'),
    'UNAVAILABLE': ('本次 AI 结果不可用；原因和费用以原回执为准。', 'AI output is unavailable; consult the original receipt for reason and cost status.'),
}
UNKNOWN = ('本次尚未核实此项，不能据此判断网站存在缺陷。',
           'This item remains unverified; no website defect is established.')


def bilingual(pair):
    return dict(zip(('zh', 'en'), pair))


def observation_copy(rule_id, row):
    result = row['observation']['result']
    reason = row.get('reason')
    if result == 'PASS':
        return PASS_COPY.get(rule_id, ('本次记录了支持此有限检查的证据。', 'Evidence supports this bounded check.'))
    if result == 'FAIL_WITH_EVIDENCE':
        if rule_id in ('DISC-01', 'DISC-02', 'CTA-02'):
            return ('来源链接在采集时返回 HTTP 404 或 410；不代表全站或当前可用性。',
                    'The recorded source link returned HTTP 404 or 410 at capture time; whole-site and current availability are unverified.')
        return ('本次规则检查记录了异常证据，请结合来源和检查范围复核。',
                'This check recorded evidence of an issue; review its source and bounded scope.')
    if result == 'ACCESS_BLOCKED':
        return ('本次访问受限，未据此评价网站业务质量。', 'Access was blocked; website business quality was not assessed from this failure.')
    if result == 'NOT_APPLICABLE':
        return ('按本次规则适用范围，此项不适用。', 'This check is not applicable under the recorded rule scope.')
    if rule_id == 'INFO-01' and row.get('source_text_presence') == 'OBSERVED':
        return ('已记录显示名称或描述；其产品身份及参数对应关系尚未核实。',
                'A display name or description was recorded; product identity and specification relationships remain unverified.')
    return REASONS.get(reason, RULE_LIMITS.get(rule_id, UNKNOWN))


def build(result):
    """Caller already checked current authority and original artifact/receipt bindings."""
    diagnosis = result.get('deterministic_diagnosis') or {}
    groups = []
    for ti, task in enumerate(diagnosis.get('buyer_tasks', [])):
        items = []
        for ri, rule in enumerate(task['rules']):
            for oi, row in enumerate(rule['observations']):
                observation = row['observation']
                items.append({'rule_id': rule['rule_id'], 'observation_id': observation['observation_id'],
                    'result': observation['result'], 'status_text': bilingual(RESULT_LABELS[observation['result']]),
                    'text': bilingual(observation_copy(rule['rule_id'], row)),
                    'source_pointer': f'/deterministic_diagnosis/buyer_tasks/{ti}/rules/{ri}/observations/{oi}'})
                if diagnosis.get('diagnostic_version') in ('l2-industrial-1.0.5', 'l2-industrial-1.0.6', 'l2-industrial-1.0.7'):
                    from .presentation_context import build as context_copy, limit
                    items[-1]['context_facts'] = context_copy(rule['rule_id'], row)
                    items[-1]['limit'] = limit(rule['rule_id'], row)
        groups.append({'task': task['task'], 'title': bilingual(TASK_LABELS[task['task']]), 'observations': items,
            'ai_claim_indexes': [i for i, claim in enumerate(result['claims']) if claim['task'] == task['task']]})
    analysis = OUTCOMES[result['analysis_outcome']]
    if result['state'] == 'CAPTURE_PENDING':
        analysis = ('正在读取获准公开页面，尚未形成诊断结论。', 'Authorized public pages are being captured; no diagnosis is available yet.')
    output = {'contract': VERSION, 'is_report': False, 'formal_human_review': False,
        'artifact_sha256': result.get('artifact_sha256'), 'rules_available': bool(groups),
        'analysis_text': bilingual(analysis),
        'tasks': groups, 'scope_pointer': '/page_scope', 'counts_pointer': '/capture_summary',
        'unknown_is_defect': False, 'missing_ai_claim_is_defect': False}
    if diagnosis.get('diagnostic_version') in ('l2-industrial-1.0.6', 'l2-industrial-1.0.7'):
        output['procurement_review'] = diagnosis['procurement_review']
    if 'buyer_review' in result:
        output['buyer_review'] = result['buyer_review']
    return output
