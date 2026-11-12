"""Escaped server-side presentation; navigation never fetches captured site URLs."""
from html import escape
import json
from urllib.parse import urlencode

from .contracts import STAGES


def e(value):
    return escape(str(value), quote=True)


def dump(value):
    return '<pre>' + e(json.dumps(value, ensure_ascii=False, indent=2)) + '</pre>'


def link(href, label, *, key=''):
    return f'<a class="action" href="{e(href)}" data-key="{e(key)}">{e(label)}<span aria-hidden="true"> →</span></a>'


def frame(prefix, title, content, trail='任务池'):
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{e(title)} · VEYFRONT 内部运营</title><link rel="stylesheet" href="{e(prefix)}style.css"></head><body>'
        '<a class="skip" href="#main">跳至主要内容</a>'
        '<div class="private-bar">PRIVATE · NOT APPROVED / 不可客户外发 · 合成测试，非真实身份认证</div>'
        '<header><div class="brand">VEYFRONT <small>运营工作区 / C0</small></div>'
        f'<nav aria-label="当前位置">{link(prefix,"诊断任务池",key="pool-nav")}<span>{e(trail)}</span></nav></header>'
        f'<main id="main" tabindex="-1">{content}</main><footer>只读应用层 · SYNTHETIC_TEST_ONLY · '
        '不保存核对结果，不产生审批或分享。<br>当前仅 6 条窄规则已启用 / 10 项覆盖缺口；人工 Gold 0/26；RA4 阶段出口仍为 NO_GO。</footer></body></html>')


def badge(task):
    return f'<span class="badge">{e(STAGES[task["stage"]][0])}</span>'


def pool(prefix, tasks, stage, query):
    options = '<option value="">全部阶段</option>'
    for key, (label, _) in STAGES.items():
        selected = ' selected' if key == stage else ''
        options += f'<option value="{key}"{selected}>{e(label)}</option>'
    rows = ''
    for t in tasks:
        rows += (f'<article class="task">{badge(t)}<h2>{e(t["title"])}</h2>'
            f'<p>{e(t["coverage_reason"])}</p><small>{e(t["task_id"])} · 合成分配范围</small>'
            + link(prefix+'tasks/'+t['task_id'], '查看任务', key=t['task_id']) + '</article>')
    if not tasks:
        rows = '<section class="notice"><h2>没有匹配的已分配任务</h2><p>尝试清除筛选条件。本视图不发现客户或真实网站。</p></section>'
    content = ('<section class="hero"><p class="eyebrow">INTERNAL OPERATIONS / 只读</p>'
        '<h1>从采购任务出发，<br>核对每一条诊断。</h1><p>先判断来源与覆盖，再查看已绑定事实。所有任务均为合成测试，不代表真实作业。</p></section>'
        '<form method="get" class="filters"><label>任务阶段<select name="stage">'+options+'</select></label>'
        f'<label>已分配任务内搜索<input name="q" maxlength="80" value="{e(query)}" placeholder="例如：工业泵"></label>'
        '<button type="submit">筛选任务</button></form>'
        f'<div class="section-heading"><h2>诊断任务池</h2><span>{len(tasks)} 项 · 最多 40 项</span></div><div class="tasks">{rows}</div>')
    return frame(prefix, '诊断任务池', content)


def review_url(prefix, task):
    return prefix+'tasks/'+task['task_id']+'/review?'+urlencode({
        'version': task['report_version'], 'draft': task['report_pins']['expected_draft_ref']})


def detail(prefix, task):
    ready = task['report_case'] is not None
    content = ('<p class="eyebrow">TASK DETAIL / 任务详情</p>'+badge(task)+f'<h1>{e(task["title"])}</h1>'
        '<section class="card"><h2>当前该做什么</h2>'+f'<p>{e(task["coverage_reason"])}</p>'
        + (link(review_url(prefix,task), '进入只读核对区', key='review') if ready else
           '<p class="neutral">尚无可验证报告。不能据此判断网站缺陷。</p>')+'</section>'
        '<section class="card"><h2>采购商任务</h2><p>从产品页寻找联系路径；先核对静态来源，再判断是否需要进一步研究。</p>'
        '<p>当前不提供真实审批、退回、拒绝、取消或客户外发。下一步由未来可信身份、持久任务及审核服务承接。</p></section>'
        '<details><summary>合成任务合同与原生状态</summary>'+dump(task)+'</details>'
        +link(prefix, '返回任务池', key='back-pool'))
    return frame(prefix, task['title'],content,'任务详情')


def review(prefix, task, dossier):
    d = dossier['document']
    base = review_url(prefix,task)
    evidence_base = prefix+'tasks/'+task['task_id']+'/evidence/'
    query = base.split('?',1)[1]
    blocks = ''
    for i, issue in enumerate(d['issues']):
        blocks += ('<section class="card issue"><p class="eyebrow">INQUIRE / 联系咨询</p>'
            f'<h2>联系路径返回 HTTP {e(issue["target_response"]["http_status"])}</h2>'
            '<div class="fact"><h3>观察事实 · 仅本次采集</h3>'
            '<p>记录中的产品页静态链接，指向的联系路径未返回成功页面。</p>'
            f'<p><code>{e(issue["fact_claim"]["fact"]["source"]["citation"]["raw_href"])}</code> → '
            f'HTTP {e(issue["target_response"]["http_status"])}</p>'
            f'<small>SOURCE_FACT_BINDING_VERIFIED · {e(issue["source_page"]["observed_at"])}</small></div>')
        blocks += link(evidence_base+str(i*4)+'?'+query, '回查观察事实的原始证据', key='evidence-primary')
        for role, label in [('impact','可能影响'),('action','建议动作'),('recheck','复验方法')]:
            claim = issue['proposals'][role]
            idx = next(j for j, ev in enumerate(dossier['evidence']) if ev['claim']['binding_ref']==claim['binding_ref'])
            blocks += (f'<div class="proposal"><h3>{label} <small>HUMAN_REVIEW_REQUIRED · 待人工判断</small></h3>'
                f'<p>{e(claim["text"])}</p>'+link(evidence_base+str(idx)+'?'+query,'查看该提议的来源绑定')+'</div>')
        blocks += '</section>'
    if not d['issues']:
        blocks += ('<section class="card"><span class="badge">0 条已证实问题</span><h2>核对覆盖范围，不添加问题</h2>'
            '<p>联系目标本次返回 HTTP 200；不能据此确认表单送达、询盘成功、业务效果或整个网站健康。</p>'
            '<p class="neutral">不能据此判断网站缺陷。CTA-02 的 PASS 是规则记录，没有 CTA Claim / Guard 绑定；不会补造绑定。</p>'
            +link(evidence_base+'capture?'+query,'回查 200 静态路径原始来源',key='evidence-primary')+
            '<details><summary>200 静态路径原生规则记录（非 Guard 结论）</summary>'+dump(dossier['contact_capture'])+'</details></section>')
    positives = ''
    for i, ev in enumerate(dossier['evidence']):
        if ev['pointer'].startswith('/positive_source_claims/'):
            positives += '<li>'+e(ev['claim']['text'])+link(evidence_base+str(i)+'?'+query,'回查来源',key='positive-evidence')+'</li>'
    content = ('<p class="eyebrow">READ-ONLY REVIEW / 原生报告只读核对</p>'+badge(task)
        +f'<h1>采购商能否从产品页找到联系路径？</h1><p class="lead">{len(d["issues"])} 条来源支持的问题 · 版本 {e(task["report_version"])} · 不记录审批</p>'
        +target_summary(prefix,task,dossier)
        +blocks+'<section class="card"><h2>已采集的其他静态线索</h2><p>网站自述仅证明来源存在该文字，不证明认证、资质或商业效果真实。</p><ul>'+positives+'</ul></section>'
        '<section class="notice"><h2>覆盖边界</h2><p>只涉及固定合成采集的静态链接与响应；没有表单提交、投递、流量、排名、收入或销售损失验证。未覆盖规则不等于通过。</p></section>'
        '<details><summary>展开原生完整报告 / Guard / 内容与 HTML 哈希</summary>'+dump(d)+dump(dossier['held'])+'</details>'
        +link(prefix+'tasks/'+task['task_id'],'返回任务详情',key='back-detail'))
    return frame(prefix, '只读核对',content,'原生报告')


def evidence(prefix, task, dossier, ev, *, target_mode=False):
    c = ev['citation']
    content = ('<p class="eyebrow">NATIVE EVIDENCE / 原始证据回查</p><h1>回到原始采集片段</h1>'
        '<p>下列 URL 仅作为来源文字展示，页面不会连接原网站。原始内容始终以转义文本呈现。</p>'
        '<section class="card"><h2>来源与时间</h2><dl>'
        f'<dt>来源 URL</dt><dd><bdi>{e(c["url"])}</bdi></dd><dt>采集时间</dt><dd>{e(c["observed_at"])}</dd>'
        f'<dt>Evidence ref</dt><dd><code>{e(c["evidence_ref"])}</code></dd>'
        f'<dt>Guard 状态</dt><dd>{e(ev["claim"]["status"])}</dd></dl>'
        f'<h3>精确引用 · UTF-8 字节 [{ev["byte_start"]}, {ev["byte_end"]})</h3><pre class="quote">{e(ev["quote"])}</pre>'
        '<details><summary>完整原始来源字节（UTF-8 文本）与校验</summary>'
        f'<p>SHA-256 <code>{e(ev["body_sha256"])}</code></p><pre>{e(ev["body"])}</pre></details>'
        '<details><summary>完整 Claim、来源定位、响应与版本绑定</summary>'+dump(ev['claim'])+dump(ev['evidence'])+dump(dossier['held'])+'</details></section>'
        +source_return(prefix,task,dossier,target_mode))
    return frame(prefix,'原始证据',content,'来源回查')


def error(prefix, code):
    return frame(prefix,'请求未提供数据','<section class="notice"><h1>请求未提供数据</h1>'
        f'<p>{e(code)}</p><p>未验证、越界、版本或来源不一致的请求会停止显示报告。请由内部负责人核对任务上下文。</p></section>')


def capture(prefix, task, dossier, *, target_mode=False):
    s = dossier['capture_source']
    c = s['citation']
    row = dossier['contact_capture']
    content = ('<p class="eyebrow">NATIVE CAPTURE / 原始采集回查</p><h1>静态联系路径的来源记录</h1>'
        '<p class="neutral">这是原生规则来源回查，没有 CTA Claim / Guard 绑定；不能据此推断询盘成功或网站全面健康。</p>'
        '<section class="card"><h2>来源与响应</h2><dl>'
        f'<dt>来源 URL</dt><dd><bdi>{e(c["url"])}</bdi></dd><dt>采集时间</dt><dd>{e(c["observed_at"])}</dd>'
        f'<dt>目标 HTTP</dt><dd>{e(row["target_response"]["http_status"])}</dd><dt>静态 href</dt><dd>{e(c["raw_href"])}</dd>'
        f'<dt>Evidence ref</dt><dd><code>{e(c["evidence_ref"])}</code></dd></dl>'
        '<p>URL 仅为文字，不连接原网站。完整原文保留，引用位置以原生行列定位为准。</p>'
        '<details><summary>展开完整原始来源</summary>'+f'<pre>{e(s["body"])}</pre><p>SHA-256 <code>{e(s["body_sha256"])}</code></p></details>'
        '<details><summary>原生定位、目标响应与报告版本 / 哈希</summary>'+dump(row)+dump(s['evidence'])+dump(dossier['held'])+'</details></section>'
        +source_return(prefix,task,dossier,target_mode))
    return frame(prefix,'静态路径来源',content,'来源回查')


def target_url(prefix, task, dossier):
    return review_url(prefix,task).replace('/review?','/target?')+'&'+urlencode({
        'target':dossier['review_target']['target_digest']})


def source_return(prefix, task, dossier, target_mode):
    if target_mode:
        return link(target_url(prefix,task,dossier),'返回精确核对对象',key='back-target')
    return link(review_url(prefix,task),'返回只读核对区',key='back-review')


def target_summary(prefix, task, dossier):
    v=dossier['review_target']
    note='1 条静态路径问题；影响及行动仍待人工判断。' if v['native_h0'] else '0 条问题 · native H0 = null；仅内部范围摘要，不能升级为已审核报告。'
    return ('<section class="card" id="target-summary"><h2>精确核对对象</h2>'
        '<p class="neutral">审核条件尚未满足 · 已绑定来源，不代表真实人工批准。</p>'
        f'<p>{e(note)}</p><p>对象指纹 <code>{e(v["target_digest"][:12])}…</code></p>'
        +link(target_url(prefix,task,dossier),'查看完整核对对象与逐条来源',key='target')+'</section>')


def target(prefix, task, dossier):
    v=dossier['review_target']
    t=v['target']
    query=urlencode({'version':task['report_version'],'draft':t['draft_ref'],'target':v['target_digest']})
    source_base=prefix+'tasks/'+task['task_id']+'/evidence/'
    labels={'ACK_LITERAL_FACT':'仅核对字面来源事实 · 不证明企业或资质真实',
            'ACCEPT_AS_HYPOTHESIS':'HUMAN_REVIEW_REQUIRED · 仅假设，不升级为事实',
            'ACCEPT_AS_PROPOSED_ACTION':'HUMAN_REVIEW_REQUIRED · 仅候选行动，未批准'}
    rows=''
    for i,claim in enumerate(t['claims']):
        # Accepted native manifest pointer, not a parallel set of claims.
        ev=next(ev for ev in dossier['evidence'] if ev['pointer']==claim['document_pointer'])
        index=dossier['evidence'].index(ev)
        rows+=(f'<li><h3>{e(labels[claim["allowed_acceptance"]])}</h3>'
               f'<p>{e(ev["claim"]["text"])}</p><small>{e(claim["document_pointer"])}</small>'
               +link(source_base+str(index)+'?'+query,'回查该项的精确原始字节',key='target-source')+'</li>')
    coverage=('<p>404 单问题；native H0 已保留，完整内容与 HTML、布局资产、来源和策略一起绑定。</p>'
              if v['native_h0'] else '<p>200 零问题；native H0 = null，native ReportVersion = null。仅内部覆盖核对，不证明询盘成功或网站全面健康。</p>')
    content=('<p class="eyebrow">SOURCE-BOUND TARGET / 只读</p><h1>精确核对对象</h1>'
        '<section class="notice"><h2>审核条件尚未满足</h2><p>这是已验收离线 D1/D2 对象的来源核验，不是审核会话、决定或分享授权。</p>'
        +coverage+'<ul>'+''.join('<li>'+e(c)+'</li>' for c in v['missing_conditions'])+'</ul></section>'
        '<section class="card"><h2>逐项事实与条件性提议</h2><p>下列处置类型只是原生允许的语义上限；没有任何项目被人工接受或批准。网站文字仍仅是网站自述。</p><ol>'+rows+'</ol>'
        +link(source_base+'capture?'+query,'回查静态联系路径记录（不补造 CTA Guard）',key='target-capture')+'</section>'
        '<details id="target-pins"><summary>完整 target digest、H0 / null、HTML / 布局 / 来源 / 策略 / Guard 绑定</summary>'
        +f'<p>Target digest <code>{e(v["target_digest"])}</code></p>'+dump(v)+'</details>'
        '<details id="target-limits"><summary>完整原生覆盖与限制</summary>'+dump(v['limitations'])+dump(v['recorded_coverage'])+dump(v['examined_pages'])+'</details>'
        +link(review_url(prefix,task),'返回原生只读核对区',key='target-back-review'))
    return frame(prefix,'精确核对对象',content,'核对对象')
