"""Procurement wording over explicitly scoped offline measurements, not rule results."""
from apps.operator_console.views import e, link


def record(data, scenario, width):
    return next(row for row in data['records'] if row['scenario']==scenario and row['width']==width)


def target(row):
    return row['metrics']['targets'][0]


def route(root,scenario,width):
    return root+'/source-tasks/cta/'+scenario+'/'+str(width)


def overview(data,root):
    clean, hidden = record(data,'clean',390), record(data,'hidden',390)
    covered, overflow = record(data,'covered',390), record(data,'overflow',320)
    box=target(clean)['rect']
    html='<section class="card" data-key="cta-review-candidates"><h2>从看到产品到找到询价入口</h2>'
    html+='<p>以下是本次获准离线合成场景的受限观察，不属于原报告的 Guard 事实。来源为 synthetic.invalid，不能代表原报告中其它网站。</p>'
    html+='<article data-rule="CTA-01" data-admission="READ_ONLY_REVIEW_CANDIDATE"><h3>询价入口：有链接，不等于用户看得见</h3>'
    html+='<p><strong>看到什么：</strong>390px正常对照中，原始链接属性为 <code>'+e(target(clean)['href'])+'</code>，只读解析为 '+e(target(clean)['resolvedHref'])+'；按钮没有 href。</p>'
    html+='<p>同一入口在透明反例中：原v1脚本的宽高非零记录为 true，实际累计透明度为 '+e(target(hidden)['opacity'])+'。不能用原 visible 字段断言可见。</p>'
    html+='<p><strong>采购影响（待复核）：</strong>若入口不可辨识，买家可能难以继续准备询价；没有测量实际询盘损失。</p>'
    html+='<p><strong>Rebuild修复候选：</strong>让询价入口在产品资料附近可辨识，保留清楚的动作名称，检查链接目标与显示样式；在相同视口复核可见性，再由企业授权验证实际表单。</p>'
    html+='<p><strong>仍未知：</strong>目标响应、业务JS/样式在其它页面的行为、表单提交、询盘送达、转化结果与真实询盘均 UNKNOWN；本轮没有访问 /rfq。</p>'
    html+=link(route(root,'clean',390),'正常对照与真实href',key='cta-source-clean')+link(route(root,'hidden',390),'透明反例与原记录边界',key='cta-source-hidden')+'</article>'
    html+='<article data-rule="CTA-03" data-admission="READ_ONLY_REVIEW_CANDIDATE"><h3>手机操作：遮挡、横向溢出与点击目标</h3>'
    html+='<p><strong>看到什么：</strong>390px遮挡样本的入口中心命中原控件：'+e(target(covered)['centerOnTarget'])+'；320px溢出样本记录内容宽 '+e(overflow['metrics']['scrollWidth'])+'px / 可视宽 '+e(overflow['metrics']['clientWidth'])+'px。</p>'
    html+='<p>正常390px入口包围盒 '+e(round(box['width'],2))+' × '+e(round(box['height'],2))+' CSS px。44px只作受控复核对照，不据此给出全站或WCAG判定。</p>'
    html+='<p><strong>Rebuild修复候选（未写入原蓝图）：</strong>收窄或提供关闭遮挡层的路径，限制窄屏内容宽度，核对入口目标尺寸；用390/375/320复测。其它命中位置、键盘路径及真实业务效果仍 UNKNOWN。</p>'
    html+=link(route(root,'covered',390),'390px遮挡实物',key='cta-source-covered')+link(route(root,'overflow',320),'320px溢出实物',key='cta-source-overflow')
    html+=link(root+'/blueprint','带着候选核对原Rebuild蓝图',key='cta-original-blueprint')+'</article>'
    html+='<p>这些附加观察仅供受控复核，不改原报告当前版本、审核项及决定。</p></section>'
    return html


def detail(row,root):
    t=target(row)
    m=row['metrics']
    base=route(root,row['scenario'],row['width'])
    labels={'clean':'正常对照','hidden':'透明入口反例','covered':'遮挡反例','overflow':'横向溢出反例'}
    html='<section class="card" data-key="cta-source-detail"><h1>'+e(labels[row['scenario']])+' · '+str(row['width'])+'px</h1>'
    html+='<p>来源：'+e(row['url'])+' · 观察时间：'+e(row['observedAt'])+'</p>'
    html+='<p>这是获准离线HTML的实际Chrome渲染；没有抓取真实网站。响应/提交/送达仍 UNKNOWN。</p>'
    html+='<p>本次证据是独立合成对照，不是当前工业任务网站的观察。采购障碍与修复建议需先在获准的真实页面复核；表单提交、询盘送达及转化结果 UNKNOWN。</p>'
    html+='<p>原DOM脚本仅保留 tag / text / 宽高非零 visible。href与以下几何在独立sidecar，未成为Guard证据。</p>'
    html+='<p>375/320仅为受控离线回归；原BrowserObservation v1原有390/1280视口不扩大。符合尺寸也不表示取得原生采集或签名来源权威。</p>'
    html+='<p>原始 href：<code>'+e(t['href'])+'</code>；只读解析：'+e(t['resolvedHref'])+'。没有请求该目标。</p>'
    html+='<p>累计透明度 '+e(t['opacity'])+'；包围盒 '+e(round(t['rect']['width'],2))+' × '+e(round(t['rect']['height'],2))+' CSS px；采样中心命中原目标 '+e(t['centerOnTarget'])+'。</p>'
    html+='<p>内容宽 '+e(m['scrollWidth'])+' / 可视宽 '+e(m['clientWidth'])+' CSS px；其它页面/时点/全站情况 UNKNOWN。</p>'
    html+='<ul data-key="cta-targets">'
    for item in m['targets']:
        html+='<li data-target="'+e(item['id'])+'">'+e(item['tag'])+' · '+e(item['text'])+'：href '+e(item['href'])+'；显示 '+e(item['display'])+' / '+e(item['visibility'])+'；视口内 '+e(item['inViewport'])+'；中心命中 '+e(item['centerOnTarget'])+'；包围盒 '+e(round(item['rect']['width'],2))+' × '+e(round(item['rect']['height'],2))+' CSS px。</li>'
    html+='</ul>'
    advice = {
        'clean': ('此对照中入口可见且中心可命中，不能据此推断真实网站询盘通畅。', '保留清楚的入口文案与位置；核对href，再按原授权范围验证后续表单。'),
        'hidden': ('宽高非零的入口仍可能透明，采购商可能看不到下一步。', '核对入口及祖先的透明度和显示样式，确保产品页上的询价动作可辨识。'),
        'covered': ('遮挡层截获本次中心命中，采购商可能无法点到入口。', '调整遮挡层范围与堆叠顺序，并提供可用的关闭路径；复测实际点击位置与键盘路径。'),
        'overflow': ('本次窄屏内容超出可视宽度，采购商可能遗漏屏外入口或资料。', '约束内容宽度、允许长文本换行并采用响应式排版；在320/375/390实际视口复测两个点击目标。'),
    }
    obstacle, repair = advice[row['scenario']]
    html+='<p data-key="cta-buyer-obstacle"><strong>采购商可能遇到的障碍：</strong>'+e(obstacle)+'</p>'
    html+='<p data-key="cta-rebuild-advice"><strong>对应Rebuild修复候选：</strong>'+e(repair)+' 尚未改写原蓝图或审核决定。</p>'
    html+=link(base+'/image','打开本次原始Chrome截图',key='cta-original-image')
    html+='<nav class="l2-nav">'+''.join(link(route(root,row['scenario'],w),str(w)+'px') for w in (390,375,320,1280))+'</nav>'
    html+=link(root+'/source-tasks','返回五维复核')+link(root+'/blueprint','在原蓝图中核对修复候选')+'</section>'
    return html
