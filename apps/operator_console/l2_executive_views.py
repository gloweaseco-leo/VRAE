"""Chinese decision summary on the original signed SSR and document fallback."""
from vrae.l2.executive import GROUPS, project
from .views import e, link
from .l2_views import navigation, provenance, source_notice


def render(view, person, state, *, document=False):
    s = project(view)
    root = '/b5a/l2/r/' + s['report_ref']
    body = '' if document else navigation(view, person, '管理层执行摘要')
    body += '<div class="l2-executive"><section class="card"><p class="eyebrow">L2 · 管理层执行摘要</p>'
    body += '<h1>本次采购复核，先决定什么</h1>' + source_notice(view)
    body += '<p data-key="executive-review">审核状态：' + e(state) + '</p>'
    count = s['d1_count']
    body += '<h2 data-key="executive-obstacles">' + (f'本次确认 {count} 项有限来源路径阻碍' if count else '本次未发现可确认的网站问题（0 项）') + '</h2>'
    body += '<p>只对保存的来源负责。工程标量冲突、资质声明、买方缺资料及 UNKNOWN 不计网站故障。实际营收、询盘损失和 ROI 未测。</p>'
    body += '<p>当前报告 ' + e(s['report_version']) + ' · ' + e(s['blueprint_count']) + ' 项原蓝图候选；服务范围 SERVICE_CATALOG_PENDING，价格与工期 UNKNOWN。</p>'
    if not document:
        body += link(root+'/executive-document', '打开文档回退／打印为 PDF', key='executive-document')
    body += '</section><section class="card"><h2>本次来源与五维覆盖</h2><p>分母是本报告保留的评估项；不是全站页面或规则覆盖率。全站分母 UNKNOWN。页面角色仅按原报告记录，不推定代表性。</p>'
    body += '<ul class="executive-coverage">' + ''.join('<li><strong>' + e(c['label']) + '</strong>：' + str(c['retained']) + ' 项；UNKNOWN ' + str(c['unknown']) + '；不适用 ' + str(c['not_applicable']) + '</li>' for c in s['coverage']) + '</ul>'
    body += '<p>来源政策：' + e(s['policy_ref']) + '；保留页面 ' + str(len(s['sources'])) + '；目标网站总体页数 UNKNOWN。</p>'
    body += '<p>来源示例：' + e('；'.join(x['url']+' · '+x['observed_at'] for x in s['sources'][:2])) + '。其余来源见原报告证据页。</p>'
    body += '<details><summary>目标 URL 与当次观察时间</summary><ul>' + ''.join('<li>' + e(x['url']) + ' · ' + e(x['observed_at']) + '</li>' for x in s['sources']) + '</ul></details></section>'
    body += '<section class="card"><h2>优先复验的有据阻碍（最多 3 项）</h2>'
    if not s['top_obstacles']:
        body += '<p>0 项；先处理资料核对与买方输入，不生成虚构问题或报价。</p>'
    for item in s['top_obstacles']:
        body += '<article><h3>' + e(item['title']) + '</h3><p>' + e(item['statement']) + '</p><p>采购影响 HYPOTHESIS：' + e(item['impact']) + '</p><p>反证／限制：' + e(item['uncertainty']) + '</p>'
        body += '<p>复验：' + e(item['recheck']) + '</p>' + link(root+'/evidence', '核对原始证据') + '</article>'
        body += '<p class="l2-scope">' + e('；'.join(x['url']+' ['+x['evidence_ref']+']' for x in item['locations'])) + '</p>'
    body += '</section><section class="card"><h2>六组决策与责任</h2><div class="executive-groups">'
    for key, label in GROUPS.items():
        rows = s['groups'][key]
        body += '<article data-group="' + key + '"><h3>' + key + ' · ' + label + ' · ' + str(len(rows)) + '</h3><p>'
        body += e('；'.join(x['title'] for x in rows[:2])) if rows else '本次无此类已记录条目。'
        body += '</p></article>'
    body += '</div><p>已观察正常原生基线 ' + str(len(s['normal_refs'])) + ' 项，保留在完整报告。商业影响均为 HYPOTHESIS；未取得独立反证不表示不存在反证。</p></section>'
    if not document:
        body += '<section class="card"><details><summary>逐条决策依据、目标 URL 与不确定性</summary>'
        for group in GROUPS:
            for item in s['groups'][group]:
                body += '<article><h3>'+group+' · '+e(item['title'])+'</h3><p>'+e(item['statement'])+'</p><p>'+e(item['limited_source'])+'</p>'
                body += '<p>'+e('；'.join(x['url']+' ['+x['evidence_ref']+']' for x in item['locations']) or '无原始 ev；仅列待补证任务')+'</p>'
                body += '<p>反证／不确定：'+e(item['counter_evidence']+' '+item['uncertainty'])+'</p><p>HYPOTHESIS：'+e(item['impact'])+'</p><p>行动：'+e(item['recommendation'])+'</p><p>复验：'+e(item['recheck'])+'</p></article>'
        body += '</details></section>'
    body += '<section class="card executive-next"><h2>下一步由谁准备</h2><p>企业工程／资质责任人核对技术资料与证明；买方补工况、数量和目的地；网站团队只在资料与用途获确认后组织页面。标准候选与定制评估以原蓝图逐项列明，企业自有责任不自动成为加购。</p>'
    body += link(root+'/blueprint', '逐项查看原蓝图：客户资料、责任、依赖、验收与复验', key='executive-blueprint')
    body += '<p>内部 Brief 不代表客户确认、E2/E3、正式报价、素材授权或外发。受控决定不是正式人审。</p>'
    body += '<p class="l2-scope">摘要版本 ' + e(s['version']) + '；摘要 SHA256 ' + e(s['summary_sha256']) + '；原报告内容 SHA256 ' + e(s['content_hash']) + '。摘要哈希不替代报告业务哈希。</p></section></div>'
    if document:
        body += '<section class="l2-print-tools"><p>使用浏览器打印为 PDF。文档与页面共用当前签名授权；不得通过打印对外分发。</p>' + link(root+'/executive', '返回交互阅读摘要') + '</section>'
    else:
        body += provenance(view)
    return body
