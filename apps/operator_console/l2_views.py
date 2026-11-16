"""Business-first L2 reading/review views on the existing signed SSR."""
from .views import e, frame, link, dump
from .proposal_views import hidden

PREFIX='/b5a/l2/'
TASK_NAMES={'DISCOVER':'找得到产品','UNDERSTAND':'看得懂技术信息','TRUST':'核对供应商可信资料',
            'INQUIRE':'准备并发起询价','SEARCH_TECHNICAL':'检查搜索与技术基础'}
KINDS={'OBSERVATION':'已记录观察','HYPOTHESIS':'待复核风险（假设）','UNKNOWN':'UNKNOWN · 尚无足够资料'}
ACTIONS={'APPROVE':'通过本版本','REJECT':'拒绝本版本','REQUEST_CHANGES':'请求修订／补证据'}


def layout(title,body,mode='CONTROLLED'):
    html=frame('/b5a/',title,body,'L2 深度诊断与 Rebuild')
    html=html.replace('</head>','<link rel="stylesheet" href="/b5a/l2/style.css"></head>',1)
    html=html.replace('<body>','<body class="l2-workspace" data-l2-mode="'+e(mode)+'">',1)
    html=html.replace('运营工作区 / C0','诊断与方案工作区',1)
    html=html.replace('href="/b5a/" data-key="pool-nav"','href="/b5a/l2/" data-key="pool-nav"',1)
    html=html.replace('诊断任务池','诊断工作区',1)
    start=html.index('<div class="private-bar">')
    end=html.index('</div>',start)+6
    label=('受控身份演练 · 非正式人审 · 定向访问仅限受控验证' if mode=='CONTROLLED'
           else '私有责任人工作区 · 精确版本审核 · 外部客户访问未开放')
    html=html[:start]+'<div class="private-bar">'+label+'</div>'+html[end:]
    footer=html.index('<footer>')
    return html[:footer]+('<footer>诊断、责任人审核、访问授权与商务交付分别记录。'
        '受控演练不代表正式人审或外部交付。不会自动报价、生成商机或发布网站。</footer></body></html>')


def navigation(view,person,section):
    m=view.document['meta']
    root=PREFIX+'r/'+m['report_id']
    body='<nav class="l2-nav" aria-label="L2 工作区">'
    for suffix,label in [('', '深度报告'),('/blueprint','Rebuild 蓝图'),('/evidence','证据与覆盖')]:
        body+=link(root+suffix,label,key='l2-'+(suffix[1:] or 'report'))
    if person.role in ('OWNER','REVIEWER'):
        body+=link(root+'/review','责任人审核',key='l2-review')
        body+=link(root+'/history','版本与决定',key='l2-history')
    if person.role=='OWNER':
        body+=link(root+'/access','受控定向访问',key='l2-access')
    return body+'</nav><p class="l2-context">'+e(section)+' · 版本 '+str(m['version'])+' · '+e(person.name)+'</p>'


def pins(view,csrf):
    return (hidden('_csrf',csrf)+hidden('version',str(view.version['version']))
            +hidden('content_hash',view.version['content_hash'])+hidden('display_hash',view.display_hash))


def provenance(view):
    d=view.document
    return ('<details class="l2-technical"><summary>技术详情：来源、行业包、版本与完整展示哈希</summary>'
            +dump({'source_mode':d['meta']['source_mode'],'source_policy_ref':d['meta']['source_policy_ref'],
                'source_bundle_sha256':view.source_digest,'display_hash':view.display_hash,
                'industry_pack':d['industry_pack'],'industry_pack_sha256':d['industry_pack_sha256'],
                'producer':d['producer'],'report_version':view.version})+'</details>')


def source_notice(view):
    d=view.document
    if d['meta']['source_mode']=='NATIVE_VERIFIED_PACK':
        return ('<p class="l2-source-note" data-source-mode="NATIVE_VERIFIED_PACK">报告版本 '+e(d['meta']['version'])
            +' · 原生EvidencePack及原Guard已完整重放；材料访问模式：'+e(d['meta']['source_access_mode'])
            +'。报告绑定服务端任务/来源及行业版本，字节一致性不是工程适配、供应商认证或网站授权。受控演练不构成正式人审。</p>')
    return ('<p class="l2-source-note" data-source-mode="'+e(d['meta']['source_mode'])+'">报告版本 '+e(d['meta']['version'])+' · '
        +('合成离线工业网站样本；没有访问真实企业网站。' if d['meta']['source_mode']=='SYNTHETIC_OFFLINE'
           else '合法持有的离线材料；资料来源与使用范围按当前来源记录核对。')
        +' 字节来源绑定不等于独立认证，观察、假设和未知项分别标记。</p>')


def report(view,person,*,review_state='尚无本版本决定'):
    d=view.document
    body=navigation(view,person,'深度报告')
    body+='<section class="card l2-hero"><p class="eyebrow">L2 DEEP AUDIT</p><h1>'+e(d['meta']['title'])+'</h1>'
    body+=source_notice(view)+'<p class="l2-lead">'+e(d['summary'])+'</p><p>审核状态：'+e(review_state)+'</p>'
    body+=link(PREFIX+'r/'+d['meta']['report_id']+'/report-print','查看／打印完整深度报告',key='l2-report-print')+'</section>'
    buyer=d['buyer']
    body+='<section class="card"><h2>工业采购商实际要完成什么</h2><h3>'+e(buyer['label'])+'</h3><p>'+e(buyer['scenario'])+'</p>'
    body+='<p class="neutral">'+e(buyer['assumption'])+'</p><ol>'
    body+=''.join('<li>'+e(q)+'</li>' for q in buyer['questions'])+'</ol></section>'
    body+='<section class="card"><h2>五段采购旅程：哪里有证据，哪里仍未知</h2><div class="l2-journey">'
    by_id={f['id']:f for f in d['findings']}
    for j in d['journey']:
        body+='<article><h3>'+e(j.get('label') or TASK_NAMES[j['task']])+'</h3><p><strong>买家任务：</strong>'+e(j['goal'])+'</p><p>'+e(j['assessment'])+'</p>'
        for key in j['finding_ids']:
            body+='<a class="action" href="#'+e(key)+'">'+e(by_id[key]['title'])+'</a>'
        body+='</article>'
    body+='</div></section><section class="card"><h2>'+e(d.get('priority_title','关键阻碍与优先级'))+'</h2><p>'+e(d.get('priority_intro','先处理可复验的直接阻碍，再处理待复核风险；UNKNOWN 不计为缺陷，不按臆测损失排序。'))+'</p>'
    for priority,label in [('P1','先修复明确阻碍'),('P2','补资料／走查后改进'),('P3','核对发布意图后处理'),('UNRANKED','需要企业补充，不阻止其余分析')]:
        label=d.get('priority_labels',{}).get(priority,label)
        body+='<h3>'+e(priority+' · '+label)+'</h3><ul>'
        body+=''.join('<li><a href="#'+e(f['id'])+'">'+e(f['title'])+'</a> · '+e(KINDS[f['kind']])+'</li>' for f in d['findings'] if f['priority']==priority)
        body+='</ul>'
    body+='</section>'
    evs={v['id']:v for v in d['evidence']}
    for f in d['findings']:
        body+='<article class="card l2-finding" id="'+e(f['id'])+'"><p class="badge">'+e(KINDS[f['kind']]+' · '+f['priority'])+'</p>'
        body+='<h2>'+e(f['title'])+'</h2><p class="fact">'+e(f['statement'])+'</p>'
        body+='<p><strong>检查范围：</strong>'+e(f['scope'])+'</p>'
        if f.get('context_evidence_ids'):
            body+='<p>以下为已记录上下文，不能把未覆盖字段的UNKNOWN提升为缺陷。</p>'
        for key in f.get('display_evidence_ids',f['evidence_ids']):
            item=evs[key]
            body+='<blockquote><strong>保留的来源原文：</strong><code>'+e(item['quote'])+'</code></blockquote>'
            body+=link(PREFIX+'r/'+d['meta']['report_id']+'/evidence/'+key,'核对该证据的页面、时间和定位',key='l2-source')
        for key,label in [('buyer_impact','可能影响（假设，不是经营结果）'),('priority_basis','为什么这样排序'),
                          ('uncertainty','尚不能确认什么'),('recommendation','建议动作'),('recheck','如何复验')]:
            body+='<h3>'+label+'</h3><p>'+e(f[key])+'</p>'
        body+='</article>'
    body+='<section class="card"><h2>企业资料不足时如何继续</h2><p>规格、资质、投递、私有经营数据分别标 UNKNOWN。公开或离线有据部分继续分析；补资料只针对依赖该资料的结论，不暂停整个 L2。</p><ul>'
    body+=''.join('<li>'+e(line)+'</li>' for line in d['limitations'])+'</ul></section>'+provenance(view)
    return body


def blueprint(view,person,csrf=None):
    d=view.document
    root=PREFIX+'r/'+d['meta']['report_id']
    body=navigation(view,person,'Rebuild 改造蓝图')
    body+='<section class="card"><h1>从诊断到可讨论的改造清单</h1>'+source_notice(view)
    body+='<p>'+e(d.get('blueprint_intro','先恢复已证实的入口与资料，再整理采购旅程。每项都指明责任、前置资料与复验标准；不是自动建站指令或客户已批准的交付 Brief。'))+'</p>'
    catalog=d['service_catalog']
    body+='<p class="neutral">'+e(catalog['verification'])+'</p><p>报价：UNKNOWN · 工期：UNKNOWN · 不承诺转化、排名或销售结果。</p>'
    body+=link(root+'/blueprint-print','查看／打印完整 Rebuild 蓝图',key='l2-blueprint-print')+'</section>'
    by_id={f['id']:f for f in d['findings']}
    for b in d['blueprint']:
        fit='标准 Rebuild 候选（按合同确认）' if b['service_fit']=='STANDARD_CANDIDATE' else '需定制评估 · 不默认必需购买'
        body+='<article class="card l2-blueprint" id="'+e(b['id'])+'"><p class="eyebrow">'+e(b['phase'])+'</p><h2>'+e(b['title'])+'</h2>'
        body+='<p class="badge">'+fit+'</p><p><strong>改善页面／信息：</strong>'+e(b['page'])+'</p>'
        body+='<h3>为什么要讨论这项改造</h3><ul>'
        for key in b['finding_ids']:
            f=by_id[key]
            body+='<li><a href="'+e(root+'#'+key)+'">'+e(f['title'])+'</a><p>'+e(f['buyer_impact'])+'</p></li>'
        body+='</ul><h3>建议怎么改</h3><p class="l2-change">'+e(b['change'])+'</p>'
        for key,label in [('customer_inputs','需要企业补充或确认'),('acceptance','如何复验改善结果')]:
            body+='<h3>'+label+'</h3><ul>'+''.join('<li>'+e(v)+'</li>' for v in b[key])+'</ul>'
        body+='<p><strong>责任角色：</strong>'+e(b['owner_role'])+'</p><p><strong>前置依赖：</strong>'+e(b['dependency'])+'</p>'
        body+='<p class="l2-scope"><strong>服务范围依据：</strong>'+e(b['service_basis'])+'</p>'
        if csrf is not None:
            body+='<details class="l2-editor"><summary>修订这项蓝图建议并创建新版本（不改原始证据）</summary>'
            body+='<form method="post" action="'+root+'/revise/'+e(b['id'])+'">'+pins(view,csrf[b['id']])
            body+='<label>修订建议<textarea name="change" maxlength="2000" required>'+e(b['change'])+'</textarea></label>'
            body+='<p>新版本需重新审核；旧版本及决定保留，旧访问授权不会自动迁移。</p><button data-key="l2-revise">保存为新版本，提交重新审核</button></form></details>'
        body+='</article>'
    return body+provenance(view)


def evidence(view,person,key=None):
    d=view.document
    body=navigation(view,person,'证据与覆盖')+'<section class="card"><h1>证据与观察边界</h1>'+source_notice(view)
    body+='<p>原始来源不可在审核界面编辑。下面是保留原文与字节定位，不是对真实网站资质或业务结果的独立认证。</p></section>'
    snapshots={s['id']:s for s in d['snapshots']}
    for item in d['evidence']:
        if key is not None and item['id']!=key:
            continue
        s=snapshots[item['snapshot_id']]
        body+='<article class="card"><h2>'+e(item['id'])+'</h2><p>来源：'+e(s['url'])+'</p><p>记录时间：'+e(s['captured_at'])+'</p>'
        body+='<p>HTTP '+e(s['http_status'])+' · '+e(s['content_type'])+'</p><blockquote><code>'+e(item['quote'])+'</code></blockquote>'
        body+='<p>定位：'+e(item['locator'])+'</p><details><summary>技术详情：字节与来源哈希</summary>'+dump({'evidence':item,'snapshot':s})+'</details></article>'
    return body


def review(view,person,csrf,mode):
    root=PREFIX+'r/'+view.document['meta']['report_id']
    controlled=mode=='CONTROLLED'
    body=navigation(view,person,'责任人审核')+'<section class="card"><h1>逐项审核当前版本</h1>'
    body+='<p><strong>当前签名身份：</strong>'+e(person.name)+' · '+e(person.role)+'</p>'
    body+=('<p class="neutral">当前是受控虚构身份演练，不能生成正式人审结论。合成审核不会升级成真实人工批准。</p>' if controlled
           else '<p>当前为已核验责任人目录。决定记录签名主体、目录核验引用、当前版本与完整展示哈希；姓名不能由表单冒填。</p>')
    body+='<p>认可 UNKNOWN 只代表认可“尚未核实”的边界，不代表认可事实缺陷。</p>'
    body+='<form method="post" action="'+root+'/review">'+pins(view,csrf)
    for item in view.document['findings']+view.document['blueprint']:
        body+='<fieldset><legend>'+e(item['title'])+'</legend><p>'+e(item.get('statement',item.get('change','')))+'</p>'
        body+='<label>本项核对<select name="item.'+e(item['id'])+'" required><option value="">请选择</option><option value="ACK">认可原文及其边界</option><option value="REQUEST_CHANGES">请求修订／补证据</option><option value="REJECT">拒绝该项表述</option></select></label></fieldset>'
    body+='<label>本版本决定<select name="action" required><option value="">请选择</option>'
    for value,label in ACTIONS.items():
        body+='<option value="'+value+'">'+('演练：' if controlled else '')+label+'</option>'
    body+='</select></label><label>决定理由／待补资料<textarea name="reason" maxlength="2000" required></textarea></label>'
    body+='<label class="check"><input type="checkbox" name="attest" value="yes" required><span>我已核对本页全部项目、证据范围和未知项；决定只针对当前版本。'+('本次仅演练，不构成正式人审。' if controlled else '')+'</span></label>'
    return body+'<button data-key="l2-save-review">保存本版本审核决定</button></form></section>'+provenance(view)


def receipt(view,person,item):
    core=item['decision']
    label=('受控演练决定已保存（不是正式人审）' if not item['formal_human_review'] else '责任人审核决定已保存')
    body=navigation(view,person,'审核保存结果')+'<section class="card l2-success"><h1>'+label+'</h1>'
    body+='<p class="l2-lead">'+e(ACTIONS[core['action']])+'</p><p>责任人：'+e(item['reviewer_name'])+' · 版本 '+e(core['version'])+'</p>'
    body+='<p>理由：'+e(core['reason'])+'</p><p>时间：'+e(core['decided_at'])+'</p>'
    body+=link(PREFIX+'r/'+view.document['meta']['report_id'],'返回深度诊断报告',key='l2-primary-report')
    body+='<details><summary>技术详情：版本化决定与身份绑定</summary>'+dump(item)+'</details></section>'
    return body


def history(view,person,versions,decisions):
    root=PREFIX+'r/'+view.document['meta']['report_id']
    body=navigation(view,person,'版本与决定')+'<section class="card"><h1>版本和责任人决定</h1><p>修订只追加版本，原证据和历史决定不被覆盖。旧决定不能授权新版本。</p>'
    for version,_ in versions:
        body+=link(root+'/v/'+str(version),'查看版本 '+str(version),key='l2-version')
    body+='</section>'
    for item in decisions:
        c=item['decision']
        body+='<article class="card"><h2>版本 '+e(c['version'])+' · '+e(ACTIONS[c['action']])+'</h2><p>'+e(item['reviewer_name'])+' · '+e(c['decided_at'])+'</p><p>'+e(c['reason'])+'</p>'
        body+='<p>'+('已核验责任人决定' if item['formal_human_review'] else '受控演练记录，不是正式人审')+'</p><details><summary>完整决定</summary>'+dump(item)+'</details></article>'
    return body


def access(view,person,csrf,recipients,grants,revoke_actions):
    root=PREFIX+'r/'+view.document['meta']['report_id']
    body=navigation(view,person,'受控定向访问')+'<section class="card"><h1>为指定受控身份验证报告访问</h1>'
    body+='<p class="neutral">这里只允许预置的受控接收者；不向真实外部客户发放或发送报告。必须先通过当前版本演练审核。令牌只显示一次且只存哈希，接收者仍须签名登录。</p>'
    body+='<p>撤销或过期会阻止后续在线读取；不能远程收回已经下载的文件。不得将受控测试授权说成客户交付。</p>'
    body+='<form method="post" action="'+root+'/access">'+pins(view,csrf)+'<label>指定接收者<select name="recipient" required>'
    for r in recipients:
        body+='<option value="'+e(r.actor_id)+'">'+e(r.name)+'</option>'
    body+='</select></label><button data-key="l2-issue-grant">创建受控访问授权（10分钟）</button></form></section>'
    for g in grants:
        target=root+'/revoke/'+g['grant_id']
        body+='<section class="card"><h2>指定版本的访问记录</h2><p>'+e(g['subject_ref'])+' · '+e(g['status'])+'</p><p>到期：'+e(g['expires_at'])+'</p>'
        if g['status']=='ACTIVE':
            body+='<form method="post" action="'+e(target)+'">'+hidden('_csrf',revoke_actions[g['grant_id']])+'<button data-key="l2-revoke-grant">撤销此访问</button></form>'
        body+='<details><summary>授权技术记录</summary>'+dump(g)+'</details></section>'
    return body


def export(view,person,kind,mode,review_state):
    body=report(view,person,review_state=review_state) if kind=='report-print' else blueprint(view,person)
    return layout('L2 '+('深度报告' if kind=='report-print' else 'Rebuild 蓝图')+' · 打印',
        '<p class="l2-print-tools">浏览器打印／保存 PDF，纸张 A4，关闭浏览器页眉页脚。本报告按深度内容自然分页。</p>'+body,mode).replace('<body class="l2-workspace"','<body class="l2-workspace l2-print"',1)
