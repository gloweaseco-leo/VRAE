"""Bilingual delivery copy over verified DTO rows; no new facts or report authority.

Buyer wording and vrae.diagnosis-judgment.v1 are emitted only for
diagnostic_version l2-industrial-1.0.7. Older artifacts keep the original copy.
"""

VERSION = 'vrae.diagnosis-presentation.v1'
JUDGMENT_VERSION = 'vrae.diagnosis-judgment.v1'
FORBIDDEN_JUDGMENT_COPY = ('建议优先关注', '可以先这样改')
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
# Five buyer tasks. Each sentence keeps the unverified limit of the old PASS copy.
BUYER_PASS = {
    'DISC-01': ('这次从首页走到了已打开的分类页；其余没打开的栏目没有核对。',
                'This check walked from the home page to an opened category page; sections that were not opened were not checked.'),
    'DISC-02': ('这次从分类页走到了已打开的产品页；页面上的产品是不是要买的那一个，还没有核对。',
                'This check walked from a category page to an opened product page; whether that product is the one to buy remains unverified.'),
    'INFO-01': ('这次在产品页上看到了名称，以及至少一组标注和数值；型号、规格是否准确、是否齐全、是否适用，都还没有核验。',
                'A name and at least one label with a value were seen on the product page; model identity, specification accuracy, completeness and fit remain unverified.'),
    'TRUST-01': ('这次看到了企业自己写的名称、介绍和联系资料；主体是不是真的、材料是不是真实，都还没有核验。',
                 'The supplier-written name, introduction and contact details were seen; legal identity and authenticity remain unverified.'),
    'CTA-02': ('这次在产品页上看到了去询价页的链接，并记录了目标页的响应；没有提交表单，也没有验证消息是否送到。',
               'An inquiry link on the product page and the target response were recorded; no form was submitted and delivery was not tested.'),
    'SEO-01': ('这次看到了页面标题和规范链接；不代表搜索引擎已经收录，也不代表排名。',
               'A page title and canonical link were seen; indexing and ranking remain unverified.'),
    'CTA-01': ('这次看到了联系或询价链接；能不能看见、点开后是否可达、消息是否送到，都还没有核验。',
               'A contact or inquiry link was seen; visibility, reachability and delivery remain unverified.'),
    'DISC-03': ('这次看到了和应用相关的静态记录；行业或用途是否匹配，还没有单独核实。',
                'A static application-related record was seen; industry or use fit has not been independently verified.'),
}
BUYER_INFO_OBSERVED = (
    '已看到供方写的名称或描述；产品身份、参数对应关系、规格准确性和适用性仍未核验。',
    'The supplier-written name or description was seen; product identity, specification relationships, accuracy and fit remain unverified.',
)
BUYER_PASS_FALLBACK = (
    '这次有限检查看到了支持该项的记录；更广的范围仍未核验。',
    'This bounded check saw a supporting record; anything beyond that scope remains unverified.',
)
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


def observation_copy(rule_id, row, *, buyer=False):
    result = row['observation']['result']
    reason = row.get('reason')
    if result == 'PASS' and buyer:
        if rule_id == 'INFO-01' and row.get('source_text_presence') == 'OBSERVED':
            return BUYER_INFO_OBSERVED
        return BUYER_PASS.get(rule_id, BUYER_PASS_FALLBACK)
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
    version = diagnosis.get('diagnostic_version')
    buyer = version in ('l2-industrial-1.0.7', 'l2-industrial-1.0.8')
    groups = []
    for ti, task in enumerate(diagnosis.get('buyer_tasks', [])):
        items = []
        for ri, rule in enumerate(task['rules']):
            for oi, row in enumerate(rule['observations']):
                observation = row['observation']
                items.append({'rule_id': rule['rule_id'], 'observation_id': observation['observation_id'],
                    'result': observation['result'], 'status_text': bilingual(RESULT_LABELS[observation['result']]),
                    'text': bilingual(observation_copy(rule['rule_id'], row, buyer=buyer)),
                    'source_pointer': f'/deterministic_diagnosis/buyer_tasks/{ti}/rules/{ri}/observations/{oi}'})
                if version in ('l2-industrial-1.0.5', 'l2-industrial-1.0.6', 'l2-industrial-1.0.7', 'l2-industrial-1.0.8'):
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
    if version in ('l2-industrial-1.0.6', 'l2-industrial-1.0.7', 'l2-industrial-1.0.8'):
        output['procurement_review'] = diagnosis['procurement_review']
    if 'buyer_review' in result:
        output['buyer_review'] = result['buyer_review']
    if 'fact_review' in result:
        output['fact_review'] = result['fact_review']
    if version == 'l2-industrial-1.0.8' and groups:
        from .judgment_v2 import build as judgment_v2, technical_access
        output['judgment'] = judgment_v2(result)
        output['technical_access'] = technical_access(result)
    elif version == 'l2-industrial-1.0.7' and groups:
        output['judgment'] = judgment(result)
    return output


MAIN_RULES = (
    ('DISC-01', 'DISCOVER'),
    ('DISC-02', 'DISCOVER'),
    ('INFO-01', 'UNDERSTAND'),
    ('TRUST-01', 'TRUST'),
    ('CTA-02', 'INQUIRE'),
    ('SEO-01', 'SEARCH_TECHNICAL'),
)
TARGET_LABELS = {
    'DISC-01': ('已打开的分类页', 'Opened category page'),
    'DISC-02': ('已打开的产品页', 'Opened product page'),
    'CTA-02': ('已打开的询价页', 'Opened inquiry page'),
}
UNJUDGED_COPY = {
    'DISC-01': ('找到产品：这次没有对首页到分类的这一步作出通过或异常判断。',
                'Finding products: the home-to-category step has no pass or failure judgment in this check.'),
    'DISC-02': ('找到产品：这次没有对分类到产品的这一步作出通过或异常判断。',
                'Finding products: the category-to-product step has no pass or failure judgment in this check.'),
    'INFO-01': ('看懂产品：这次没有对名称和参数作出通过或异常判断。',
                'Understanding the product: the name and specifications have no pass or failure judgment in this check.'),
    'TRUST-01': ('核对企业资料：这次没有对企业自述、介绍或联系资料作出通过或异常判断。',
                 'Checking the supplier: the stated identity, introduction and contact details have no pass or failure judgment in this check.'),
    'CTA-02': ('询价入口：这次没有对产品页到询价页的这一步作出通过或异常判断。',
               'Inquiry route: the product-to-inquiry step has no pass or failure judgment in this check.'),
    'SEO-01': ('访问与页面结构：这次没有对标题和规范链接作出通过或异常判断。',
               'Access and page structure: the title and canonical link have no pass or failure judgment in this check.'),
}
LEAD_CLEAR = (
    '这次预诊断不是正式报告，也没有经过人工审核。已访问的页面没有记录到有证据的障碍，因此本次没有确认具体缺陷。供方核对问题只供核对，不是优先改造。未访问的候选页面不是缺陷。',
    'This pre-diagnosis is not a formal report and has no human review. Visited pages recorded no evidence-backed obstacle, so no specific defect is confirmed. Supplier questions are for checking only and are not priority fixes. Unvisited candidate pages are not defects.',
)
LEAD_OBSTACLES = (
    '这次预诊断不是正式报告，也没有经过人工审核。已访问的页面记录了有证据的障碍；障碍数量不是评分，也不代表全站。供方核对问题只供核对，不是优先改造。未访问的候选页面不是缺陷。',
    'This pre-diagnosis is not a formal report and has no human review. Visited pages recorded evidence-backed obstacles; their count is not a score and does not represent the whole site. Supplier questions are for checking only and are not priority fixes. Unvisited candidate pages are not defects.',
)
HYPOTHESIS_COPY = {
    'REPAIR_RECORDED_ISSUE': (
        '下一步只核对本轮已经记录的障碍，不据此重建整个网站。',
        'The next check stays on the obstacle already recorded and does not rebuild the whole site.'),
    'CHECK_RECORDED_PRODUCT_PAGE': (
        '下一步只核对已经打开并记录的产品页，不把未访问页面算进本次判断。',
        'The next check stays on the product page already opened and recorded; unvisited pages are outside this judgment.'),
    'NO_BROADER_SCOPE': (
        '本次没有已记录的障碍，也没有已打开的产品页，不扩大到全站。',
        'This check recorded no obstacle and no opened product page, so the scope stays inside this sample.'),
}


def _guard(pair):
    for text in pair:
        if any(phrase in text for phrase in FORBIDDEN_JUDGMENT_COPY):
            raise ValueError('JUDGMENT_COPY_FORBIDDEN')
    return bilingual(pair)


def _clean_name(text):
    if not isinstance(text, str):
        return None
    text = ' '.join(text.split())
    return text or None


def _remember(index, ref, url, name):
    by_ref, by_url = index
    if isinstance(ref, str) and ref and ref not in by_ref:
        by_ref[ref] = name
    if isinstance(url, str) and url and url not in by_url:
        by_url[url] = name


def _product_names(diagnosis):
    index = ({}, {})
    for task in diagnosis.get('buyer_tasks') or []:
        for rule in task.get('rules') or []:
            if rule.get('rule_id') != 'INFO-01':
                continue
            for row in rule.get('observations') or []:
                source = row.get('source_page') if isinstance(row.get('source_page'), dict) else {}
                for citation in row.get('citations') or []:
                    if not isinstance(citation, dict) or citation.get('fact_role') != 'NAME':
                        continue
                    name = _clean_name(citation.get('text'))
                    if not name:
                        continue
                    _remember(index, citation.get('snapshot_ref'), citation.get('url'), name)
                    _remember(index, source.get('snapshot_ref'), source.get('url'), name)
    return index


def _count(summary, key, fallback):
    if isinstance(summary, dict):
        value = summary.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return fallback


def _has_product_page(diagnosis, page_scope, names):
    if names[0] or names[1]:
        return True
    for page in (page_scope or {}).get('visited_pages') or []:
        if isinstance(page, dict) and page.get('request_role') == 'PRODUCT':
            return True
    for path in diagnosis.get('buyer_journey') or []:
        for step in path.get('steps') or []:
            target = step.get('target_response')
            if step.get('rule_id') == 'DISC-02' and step.get('result') == 'PASS' and isinstance(target, dict) and target:
                return True
    for task in diagnosis.get('buyer_tasks') or []:
        for rule in task.get('rules') or []:
            if rule.get('rule_id') != 'INFO-01':
                continue
            for row in rule.get('observations') or []:
                if isinstance(row.get('source_page'), dict):
                    return True
    return False


def judgment(result):
    """One pre-diagnosis judgment. Not a report, a score, or a priority-fix list."""
    diagnosis = result.get('deterministic_diagnosis') or {}
    pointers = {}
    seen = {rule_id: set() for rule_id, _task in MAIN_RULES}
    obstacles = []
    for ti, task in enumerate(diagnosis.get('buyer_tasks') or []):
        task_name = task.get('task')
        for ri, rule in enumerate(task.get('rules') or []):
            rule_id = rule.get('rule_id')
            for oi, row in enumerate(rule.get('observations') or []):
                observation = row.get('observation') or {}
                result_code = observation.get('result')
                pointer = f'/deterministic_diagnosis/buyer_tasks/{ti}/rules/{ri}/observations/{oi}'
                observation_id = observation.get('observation_id')
                if observation_id:
                    pointers[observation_id] = pointer
                if rule_id in seen and result_code in ('PASS', 'FAIL_WITH_EVIDENCE'):
                    seen[rule_id].add(result_code)
                if result_code != 'FAIL_WITH_EVIDENCE':
                    continue
                obstacles.append({
                    'rule_id': rule_id, 'task': task_name, 'observation_id': observation_id,
                    'result': 'FAIL_WITH_EVIDENCE',
                    'text': bilingual(observation_copy(rule_id, row, buyer=True)),
                    'source_pointer': pointer})
    questions = []
    for index, claim in enumerate(result.get('claims') or []):
        if not isinstance(claim, dict) or not isinstance(claim.get('questions'), list):
            continue
        for question in claim['questions']:
            if not isinstance(question, str) or not question.strip():
                continue
            questions.append({
                'claim_index': index, 'task': claim.get('task'), 'question': question,
                'presented_as_priority_fix': False, 'is_confirmed_defect': False})
    names = _product_names(diagnosis)
    steps = []
    emitted = set()
    for path in diagnosis.get('buyer_journey') or []:
        for step in path.get('steps') or []:
            if step.get('result') != 'PASS':
                continue
            observation_id = step.get('observation_id')
            if observation_id in emitted:
                continue
            if observation_id:
                emitted.add(observation_id)
            target = step.get('target_response') if isinstance(step.get('target_response'), dict) else {}
            rule_id = step.get('rule_id')
            if rule_id == 'DISC-02':
                product = names[0].get(target.get('snapshot_ref')) or names[1].get(target.get('url'))
                # Source product names stay verbatim. File names are never used as titles.
                label = bilingual((product, product)) if product else _guard(TARGET_LABELS['DISC-02'])
            else:
                label = _guard(TARGET_LABELS.get(rule_id, ('已打开的页面', 'Opened page')))
            url = target.get('url') if isinstance(target.get('url'), str) else None
            snapshot_ref = target.get('snapshot_ref') if isinstance(target.get('snapshot_ref'), str) else None
            steps.append({
                'rule_id': rule_id, 'observation_id': observation_id, 'result': 'PASS',
                'label': label, 'url': url, 'snapshot_ref': snapshot_ref,
                'source_pointer': pointers.get(observation_id)})
    page_scope = result.get('page_scope') if isinstance(result.get('page_scope'), dict) else {}
    summary = result.get('capture_summary') if isinstance(result.get('capture_summary'), dict) else {}
    visited = page_scope.get('visited_pages') or []
    failed = page_scope.get('failed_attempt_records') or []
    unvisited_rows = page_scope.get('unvisited_candidates') or []
    fetched = _count(summary, 'fetched_pages', len(visited) if isinstance(visited, list) else 0)
    unvisited = _count(summary, 'unvisited_candidates', len(unvisited_rows) if isinstance(unvisited_rows, list) else 0)
    if obstacles:
        hypothesis = 'REPAIR_RECORDED_ISSUE'
    elif _has_product_page(diagnosis, page_scope, names):
        hypothesis = 'CHECK_RECORDED_PRODUCT_PAGE'
    else:
        hypothesis = 'NO_BROADER_SCOPE'
    unjudged = [{
        'rule_id': rule_id, 'task': task_name, 'is_defect': False,
        'text': _guard(UNJUDGED_COPY[rule_id]),
    } for rule_id, task_name in MAIN_RULES if not seen[rule_id]]
    walked_summary = (
        ('这次沿着已打开的页面走通了下面这些步骤。没打开的页面不算进这条路径。',
         'These steps were walked on pages already opened. Pages that were not opened are not part of this path.')
        if steps else
        ('这次没有走通的页面步骤。', 'No page step was walked through in this check.'))
    return {
        'contract': JUDGMENT_VERSION, 'is_report': False, 'formal_human_review': False,
        'lead': _guard(LEAD_OBSTACLES if obstacles else LEAD_CLEAR),
        'confirmed_obstacles': {
            'items': obstacles, 'count': len(obstacles),
            'is_defect_score': False, 'confirmed_obstacle_count_is_score': False},
        'supplier_questions': {
            'items': questions, 'presented_as_priority_fix': False, 'is_confirmed_defect': False},
        'walked_path': {'steps': steps, 'summary': _guard(walked_summary)},
        'unjudged': {
            'items': unjudged, 'is_defect': False,
            'text': _guard(('这些环节这次没有通过或异常判断，不能当成缺陷。',
                           'These steps have no pass or failure judgment in this check and are not defects.'))},
        'sample_boundary': {
            'fetched_pages': fetched, 'unvisited_candidates': unvisited,
            'visited_page_count': len(visited) if isinstance(visited, list) else 0,
            'failed_attempt_count': len(failed) if isinstance(failed, list) else 0,
            'capture_summary_pointer': '/capture_summary', 'page_scope_pointer': '/page_scope',
            'unvisited_is_defect': False,
            'text': _guard((
                f'本次访问 {fetched} 页，另有 {unvisited} 个候选页面没有访问。没访问的页面不是缺陷。',
                f'This check visited {fetched} pages. {unvisited} candidate pages were not visited. Unvisited pages are not defects.'))},
        'scope_hypothesis': {
            'kind': hypothesis, 'whole_site_rebuild': False, 'text': _guard(HYPOTHESIS_COPY[hypothesis])},
    }
