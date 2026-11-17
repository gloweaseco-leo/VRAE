"""Five-dimensional reading of an authenticated existing report, not an evaluator.

Only immutable, ledger-validated DeepReport bytes are projected. No collection,
new finding, review item, source authority or persisted decision is created.
"""
import re

from vrae.l2.report import DeepReport, TASKS, deny
from vrae.rules.readiness import catalog
from .views import e, dump, link

VERSION = 'c2-buyer-reading-1.0.0'
LABELS = {'DISCOVER': '找到产品与型号', 'UNDERSTAND': '看懂规格与适用条件',
          'TRUST': '核对供应商声明与证明', 'INQUIRE': '准备产品上下文询价',
          'SEARCH_TECHNICAL': '检查搜索与技术观察边界'}
GOALS = {'DISCOVER': '从已保留的产品路径找到候选型号，不把未访问页面说成不存在。',
         'UNDERSTAND': '核对参数、单位、条件和资料版本；工程适配由工程责任人确认。',
         'TRUST': '核对材料声明的机构、范围与日期；来源声明不等于认证真实。',
         'INQUIRE': '整理型号、工况和买方待补项；没有提交RFQ或验证真实送达。',
         'SEARCH_TECHNICAL': '只呈现本次可复核范围；没有SEO评分、排名或全站无障碍结论。'}
RULE_LABELS = {'DISC-01': '首页到产品分类', 'DISC-02': '分类到产品型号', 'DISC-03': '行业与应用入口',
               'INFO-01': '基础规格', 'INFO-02': '行业关键资料', 'INFO-03': '英文与多语言原文候选',
               'TRUST-01': '企业信息上下文', 'TRUST-02': '证明材料展示上下文', 'TRUST-03': '联系资料一致性',
               'CTA-01': '可见联系与RFQ入口', 'CTA-02': '产品到联系路径', 'CTA-03': '移动视口操作观察',
               'SEO-01': '已记录搜索元数据', 'SEO-02': '产品文本与锚点',
               'TECH-01': '响应与阻断', 'TECH-02': '图片与标题结构候选'}
UX_REASONS = {'INFO-03': '原文候选需人工确认；语言表达质量仍UNKNOWN。',
              'CTA-01': '原DOM只保留文本，缺href与可交互可见性，保持UNKNOWN。',
              'CTA-03': '没有原生遮挡、命中或溢出几何，保持UNKNOWN；截图不替代测量。',
              'TECH-02': '缺原alt/src及逐图片加载对应，保持UNKNOWN；不评价排名或WCAG。'}
RESULTS = {'PASS': '原范围观察成立', 'FAIL_WITH_EVIDENCE': '原范围比较待优先复核',
           'UNKNOWN': 'UNKNOWN · 资料不足', 'NOT_APPLICABLE': 'NOT_APPLICABLE · 原配置不适用',
           'ACCESS_BLOCKED': 'ACCESS_BLOCKED · 访问受限'}


def reading(view):
    """No source lookup or inference from Chinese presentation statements."""
    if type(view) is not DeepReport:
        deny()
    d = view.document
    native = d.get('native_context')
    if native and (native['tenant_id'], native['run_id']) != (d['meta']['tenant_id'], d['meta']['run_id']):
        deny('L2_NATIVE_TASK_MISMATCH')
    evs = {item['id']: item for item in d['evidence']}
    snapshots = {item['id']: item for item in d['snapshots']}
    language = []
    for item in evs.values():
        quote = item['quote']
        if re.search(r'[\u3400-\u9fff]|\blorem ipsum\b|\bcoming soon\b|\bTODO\b', quote, re.I):
            language.append({'evidence_id': item['id'], 'quote': quote,
                             'snapshot_id': item['snapshot_id'], 'result': 'UNKNOWN',
                             'reason': 'HUMAN_REVIEW_REQUIRED'})
    rules = catalog()
    dims = []
    for task in TASKS:
        findings = [f for f in d['findings'] if f['task'] == task]
        dims.append({'task': task, 'findings': findings,
                     'generic_rules': [r for r in rules['rules'] if r['buyer_task'] == task],
                     'blueprints': [b for b in d['blueprint']
                                    if set(b['finding_ids']) & {f['id'] for f in findings}]})
    return {'version': VERSION, 'report_version': view.version, 'display_hash': view.display_hash,
            'source_digest': view.source_digest, 'dimensions': dims, 'catalog_version': rules['catalog_version'],
            'sources': snapshots, 'evidence': evs, 'language_candidates': language,
            'industry_pack': d['industry_pack'], 'whole_site_denominator': None,
            'industry_rule_coverage': d.get('industry_rule_coverage'),
            'native_context': native, 'producer': d['producer']}


def render(view, person):
    from .l2_views import navigation, provenance
    d = view.document
    m = reading(view)
    root = '/b5a/l2/r/' + d['meta']['report_id']
    body = navigation(view, person, '五维采购复核')
    body += ('<section class="card l2-buyer-overview" data-report-sha="'+e(view.display_hash)
             +'" data-report-version="'+e(view.version['report_version_id'])+'">'
             '<p class="eyebrow">本报告的采购阅读视图</p><h1>从找到型号到准备询价</h1>'
             '<p>先找到型号，核对规格与证明，再整理询价资料。每项都能回到本次来源核对。</p><p>当前报告版本 '+e(d['meta']['version'])
             +' · '+e(d['meta']['title'])+'</p><p>来源快照 '+str(len(m['sources']))
             +' 个；全站覆盖分母 UNKNOWN，未访问范围不计为缺陷。</p>'
             '<details><summary>检查覆盖：工业评估与通用16规则分开记录</summary>'
             '<p>本报告未载入新的S2通用规则执行结果，不计算完成率或网站评分，'
             '也不将工业6规则当作通用16条完成。</p></details>'
             '<p class="neutral">CONTROLLED · 内部演练，非正式人审；客户外发未授权。'
             '阅读提示不会修改原报告或审核记录。</p>'
             '<nav class="l2-buyer-tabs" aria-label="五维采购任务">')
    for task in TASKS:
        body += '<a href="#buyer-'+task+'">'+e(LABELS[task])+'</a>'
    body += '</nav></section>'
    for dim in m['dimensions']:
        task = dim['task']
        body += '<section class="card l2-buyer-dimension" id="buyer-'+task+'" data-task="'+task+'">'
        body += '<h2>'+e(LABELS[task])+'</h2><p>'+e(GOALS[task])+'</p>'
        body += '<h3>本报告已保留的工业评估与上下文</h3>'
        if not dim['findings']:
            body += '<p class="neutral">UNKNOWN · 本维没有已载入的工业评估，不补造SEO或其他评价。</p>'
        for f in dim['findings']:
            result = f.get('native_result', 'UNKNOWN' if f['kind'] == 'UNKNOWN' else 'SOURCE_BOUND_OFFLINE_NOTE')
            body += '<article class="l2-buyer-item" data-result="'+e(result)+'"><h4>'+e(f['title'])+'</h4>'
            body += '<p>'+e(RESULTS.get(result, '来源绑定的离线编辑观察；不是原生规则结果'))+'</p>'
            body += '<p>'+e(f['statement'])+'</p>'
            refs = f.get('source_fact_refs', f.get('context_evidence_ids', []) + f['evidence_ids'])
            unique = list(dict.fromkeys(refs))
            for index, key in enumerate(unique):
                if index == 1:
                    body += '<details><summary>核对其余 '+str(len(unique)-1)+' 条来源引用</summary>'
                item = m['evidence'][key]
                snap = m['sources'][item['snapshot_id']]
                body += '<div class="l2-buyer-source"><p>来源：'+e(snap['url'])+'</p><p>采集时间：'+e(snap['captured_at'])+'</p>'
                if item['quote']:
                    body += '<blockquote>'+e(item['quote'])+'</blockquote>'
                body += link(root+'/evidence/'+key, '定位原证据与字节范围', key='buyer-evidence')+'</div>'
            if len(unique)>1:
                body += '</details>'
            body += link(root+'#'+f['id'], '查看原诊断、影响与复验建议', key='buyer-finding')+'</article>'
        body += '<details class="l2-generic-scope"><summary>本维通用检查范围（'+str(len(dim['generic_rules']))+'项待核）</summary><ul class="l2-buyer-rules">'
        for r in dim['generic_rules']:
            body += '<li data-rule="'+e(r['rule_id'])+'"><strong>'+e(RULE_LABELS[r['rule_id']])+'</strong>'
            body += '<p>UNKNOWN · '+e(UX_REASONS.get(r['rule_id'], '本报告未载入此规则的新版本执行记录，不从工业评估推导。'))+'</p>'
            body += '<details><summary>规则及版本</summary><p>'+e(r['rule_id'])+' · '+e(r['rule_version'])+'</p></details></li>'
        body += '</ul></details>'
        if task == 'UNDERSTAND':
            body += '<h3>原文待人工确认</h3><p>仅在本报告保留的原文片段中查找中文/占位候选，不扫描中文界面文案。'
            body += '未命中也不代表英语清晰或全站无中文。</p>'
            for c in m['language_candidates']:
                body += '<article class="l2-language-candidate"><p>HUMAN_REVIEW_REQUIRED · UNKNOWN</p><blockquote>'+e(c['quote'])+'</blockquote>'
                body += link(root+'/evidence/'+c['evidence_id'], '复核此原文的来源与时间', key='buyer-language-source')+'</article>'
            if not m['language_candidates']:
                body += '<p>当前保留片段未提出候选；正文/图片/术语/翻译冲突与英语表达质量仍UNKNOWN。</p>'
        if dim['blueprints']:
            body += '<h3>有据改造讨论入口</h3>'
            for b in dim['blueprints']:
                fit = '标准Rebuild候选，按合同确认' if b['service_fit']=='STANDARD_CANDIDATE' else '需定制评估，不默认加购'
                body += '<p>'+e(fit)+' · '+link(root+'/blueprint#'+b['id'], b['title'], key='buyer-blueprint')+'</p>'
        body += '</section>'
    body += '<section class="card"><h2>行业适用性、来源与版本</h2>'
    body += '<p>来源策略：'+e(d['meta']['source_policy_ref'])+'；策略版本 UNKNOWN（当前报告未保留独立版本字段）。</p>'
    body += '<p>行业包 '+e(m['industry_pack'].get('industry_id', 'UNKNOWN'))+' · 版本 '+e(m['industry_pack'].get('version', 'UNKNOWN'))+'</p>'
    body += '<p>适用性按原行业配置和逐项结果核对；NOT_APPLICABLE不计缺陷，UNKNOWN/ACCESS_BLOCKED不升级为失败。'
    body += '通用规则覆盖与工业规则覆盖分别核算。</p><details><summary>行业配置与原覆盖记录</summary>'
    body += dump({'industry_pack': m['industry_pack'], 'industry_rule_coverage': m['industry_rule_coverage']})+'</details>'
    body += '<details><summary>来源清单：URL、时间与观察状态</summary>'
    for s in m['sources'].values():
        body += '<p>'+e(s['url'])+' · '+e(s['captured_at'])+' · '+e(s.get('original_snapshot', {}).get('status', 'UNKNOWN'))+'</p>'
    body += '</details><p>继续在原报告版本内核对证据和逐项审核；本页不保存另一套决定。</p>'
    body += link(root+'/review', '进入本版本原有逐项审核', key='buyer-review') if person.role in ('OWNER', 'REVIEWER') else ''
    body += link(root+'/report-print', '查看本版本原报告／中文打印', key='buyer-print')+'</section>'
    return body+provenance(view)
