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
JUDGMENT_VERSION = 'vrae.diagnosis-judgment.v1'
BUYER_VERSION = 'l2-industrial-1.0.7'
BUYER_PASS = {
    'DISC-01': ('采购商可以从首页进入这次已打开的产品分类。',
                'A buyer can go from the home page to the product category opened in this check.'),
    'DISC-02': ('可以从该分类打开这一条产品页；还不能确认它是不是唯一对应的型号。',
                'The category opens this product page; that it is the only matching model is unverified.'),
    'CTA-02': ('可以从这款产品页走到联系页面，目标页面这次有响应；没有提交表单，也不能确认消息能送达。',
               'The product page reaches a contact page that responded in this check; no form was submitted and delivery is unverified.'),
    'INFO-01': ('产品页上能看到名称和至少一组供方标注的参数；型号是否对应、规格是否准确、是否适用，都还没核实。',
                'The product page shows a name and at least one supplier-stated specification; model identity, accuracy and suitability are unverified.'),
    'SEO-01': ('已看到页面标题和规范链接；这不代表已经被搜索引擎收录或有排名。',
               'A page title and canonical link were recorded; indexing and ranking are unverified.'),
    'TRUST-01': ('已看到供方自己写的企业介绍和公开联系资料；没有核验营业主体或材料真伪。',
                 'Supplier-written introduction and public contact details were recorded; legal identity and authenticity are unverified.'),
}
ROLE_LABELS = {
    'HOME': ('网站首页', 'Home'),
    'CATALOG': ('产品列表', 'Product list'),
    'CATEGORY': ('产品分类', 'Product category'),
    'PRODUCT': ('产品页', 'Product page'),
    'CONTACT': ('联系页面', 'Contact page'),
    'ABOUT': ('企业介绍', 'About'),
    'APPLICATION': ('应用页面', 'Application page'),
    'PAGE': ('已打开的页面', 'Opened page'),
}
STEP_TARGET_ROLE = {'DISC-01': 'CATEGORY', 'DISC-02': 'PRODUCT', 'CTA-02': 'CONTACT'}
PRIMARY_RULES = {
    'DISCOVER': ('DISC-01', 'DISC-02'),
    'UNDERSTAND': ('INFO-01',),
    'TRUST': ('TRUST-01',),
    'INQUIRE': ('CTA-02',),
    'SEARCH_TECHNICAL': ('SEO-01',),
}


def bilingual(pair):
    return dict(zip(('zh', 'en'), pair))


def observation_copy(rule_id, row, *, buyer=False):
    result = row['observation']['result']
    reason = row.get('reason')
    if result == 'PASS':
        copy = BUYER_PASS if buyer else PASS_COPY
        return copy.get(rule_id, ('本次记录了支持此有限检查的证据。', 'Evidence supports this bounded check.'))
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
        if buyer:
            return ('已看到供方写的名称或描述；它对应哪一款型号、参数是否成套，还没核实。',
                    'A supplier-stated name or description was recorded; model identity and how the values fit together remain unverified.')
        return ('已记录显示名称或描述；其产品身份及参数对应关系尚未核实。',
                'A display name or description was recorded; product identity and specification relationships remain unverified.')
    return REASONS.get(reason, RULE_LIMITS.get(rule_id, UNKNOWN))


def _plain_name(text):
    if type(text) is not str:
        return None
    text = ' '.join(text.split())
    if not text or len(text) > 160 or '<' in text or '>' in text:
        return None
    return text


def _product_names(diagnosis):
    names = {}
    for task in diagnosis.get('buyer_tasks', []):
        for rule in task['rules']:
            if rule['rule_id'] != 'INFO-01':
                continue
            for row in rule['observations']:
                for citation in row.get('citations') or []:
                    if citation.get('fact_role') != 'NAME':
                        continue
                    name = _plain_name(citation.get('text'))
                    if name and citation.get('url'):
                        names[citation['url']] = name
    return names


def _path_node(page, role, names):
    name = names.get(page.get('url')) if role == 'PRODUCT' else None
    label = (name, name) if name else ROLE_LABELS.get(role, ROLE_LABELS['PAGE'])
    return {'role': role, 'url': page['url'], 'snapshot_ref': page.get('snapshot_ref'),
            'label': bilingual(label)}


def _walked_nodes(diagnosis, names):
    journeys = diagnosis.get('buyer_journey') or []
    complete = [item for item in journeys if item.get('complete')]
    if complete:
        journey = complete[0]
    else:
        ranked = sorted(journeys, key=lambda item: sum(
            step.get('result') == 'PASS' for step in item.get('steps') or []), reverse=True)
        journey = ranked[0] if ranked and any(
            step.get('result') == 'PASS' for step in ranked[0].get('steps') or []) else None
    if journey is None:
        return []
    nodes = []
    for index, step in enumerate(journey.get('steps') or []):
        if step.get('result') != 'PASS':
            break
        source = step.get('source_page') or step.get('homepage')
        if index == 0 and source and source.get('url'):
            nodes.append(_path_node(source, 'HOME' if step.get('rule_id') == 'DISC-01' else 'PAGE', names))
        target = step.get('target_response')
        if target and target.get('url'):
            nodes.append(_path_node(target, STEP_TARGET_ROLE.get(step.get('rule_id'), 'PAGE'), names))
    return nodes


def _judgment(result, groups):
    diagnosis = result.get('deterministic_diagnosis') or {}
    names = _product_names(diagnosis)
    nodes = _walked_nodes(diagnosis, names)
    obstacles = [{'task': group['task'], 'rule_id': item['rule_id'],
        'observation_id': item['observation_id'], 'text': item['text'],
        'source_pointer': item['source_pointer'], 'is_defect_score': False}
        for group in groups for item in group['observations'] if item['result'] == 'FAIL_WITH_EVIDENCE']
    questions = []
    for index, claim in enumerate(result.get('claims') or []):
        if not isinstance(claim, dict) or not isinstance(claim.get('explanation'), str):
            continue
        questions.append({'claim_index': index, 'task': claim.get('task'), 'text': claim['explanation'],
            'questions': [q for q in claim.get('questions') or [] if isinstance(q, str)],
            'presented_as_priority_fix': False, 'is_confirmed_defect': False})
    unjudged = []
    for group in groups:
        primary = [item for item in group['observations'] if item['rule_id'] in PRIMARY_RULES.get(group['task'], ())]
        if any(item['result'] in ('PASS', 'FAIL_WITH_EVIDENCE') for item in primary):
            continue
        chosen = next((item for item in primary if item['result'] == 'UNKNOWN'), None)
        if chosen is None and primary:
            chosen = primary[0]
        if chosen is None:
            text = bilingual(('本次没有打开这个环节需要的代表页面。',
                              'This visit did not open a representative page for this task.'))
            pointer = None
        else:
            text, pointer = chosen['text'], chosen['source_pointer']
        unjudged.append({'task': group['task'], 'title': group['title'], 'text': text,
                         'source_pointer': pointer, 'is_defect': False})
    if nodes:
        joined = ' → '.join(node['label']['zh'] for node in nodes)
        path_text = (f'本次只走通了：{joined}。结论只覆盖这条路径。',
                     'This check only walked: ' + ' → '.join(node['label']['en'] for node in nodes) +
                     '. The conclusion covers that path only.')
    else:
        path_text = ('这次没有拼成一条已验证的采购路径。',
                     'This check did not assemble a verified procurement path.')
    product_seen = any(node['role'] == 'PRODUCT' for node in nodes)
    if obstacles:
        scope = ('REPAIR_RECORDED_ISSUE',
                 ('先处理已有证据的障碍所在页面。没有据此扩大到全站的依据。',
                  'Start with the pages that have a confirmed obstacle. This check gives no basis to widen the change to the whole site.'))
        lead = ('本次确认了有证据的障碍。需要供方确认的问题另行列出，不计入缺陷。',
                'This check confirmed evidence-backed obstacles. Questions for the supplier are listed separately and are not defects.')
    elif product_seen:
        scope = ('CHECK_RECORDED_PRODUCT_PAGE',
                 ('先核对这一条已打开的产品页上的选型资料。这次没有结构失败的证据，不能把改版范围扩大到全站。',
                  'Check the selection details on the product page opened in this visit. No structural failure was confirmed, so the change is not widened to the whole site.'))
        lead = ('本次没有已证实的网站缺陷。已走通的路径和需要供方确认的问题分开列出。',
                'No website defect was confirmed. The path that worked and questions for the supplier are listed separately.')
    else:
        scope = ('NO_BROADER_SCOPE',
                 ('这次没有足够的页面证据提出改版范围。没打开的页面不是缺陷。',
                  'This visit does not have enough page evidence to propose a change in scope. Unopened pages are not defects.'))
        lead = ('本次没有已证实的网站缺陷。已走通的路径和需要供方确认的问题分开列出。',
                'No website defect was confirmed. The path that worked and questions for the supplier are listed separately.')
    page_scope = result.get('page_scope') or {}
    summary = result.get('capture_summary') or {}
    fetched = summary.get('fetched_pages', len(page_scope.get('visited_pages') or []))
    unvisited = summary.get('unvisited_candidates', len(page_scope.get('unvisited_candidates') or []))
    failed = len(page_scope.get('failed_attempt_records') or [])
    return {'contract': JUDGMENT_VERSION, 'is_report': False, 'formal_human_review': False,
        'lead': bilingual(lead),
        'confirmed_obstacles': obstacles, 'confirmed_obstacle_count_is_score': False,
        'supplier_questions': questions,
        'walked_path': {'steps': nodes, 'summary': bilingual(path_text)},
        'unjudged': unjudged,
        'sample_boundary': {'fetched_pages': fetched, 'unvisited_candidates': unvisited,
            'failed_attempts': failed, 'unvisited_is_defect': False,
            'text': bilingual((
                f'本次打开了 {fetched} 个公开页面，另有 {unvisited} 个候选页面没有访问，{failed} 个访问没有取得内容。没访问的页面不是缺陷。',
                f'This visit opened {fetched} public pages, left {unvisited} candidates unvisited, and recorded {failed} attempts without content. Unvisited pages are not defects.'))},
        'scope_hypothesis': {'kind': scope[0], 'text': bilingual(scope[1]), 'whole_site_rebuild': False}}


def build(result):
    """Caller already checked current authority and original artifact/receipt bindings."""
    diagnosis = result.get('deterministic_diagnosis') or {}
    buyer = diagnosis.get('diagnostic_version') == BUYER_VERSION
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
    if 'fact_review' in result:
        output['fact_review'] = result['fact_review']
    if buyer and groups:
        output['judgment'] = _judgment(result, groups)
    return output
