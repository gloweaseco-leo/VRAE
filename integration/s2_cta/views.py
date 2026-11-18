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
    html+='<p><strong>仍未知：</strong>目标响应、业务JS/样式在其它页面的行为、表单提交、邮件送达与真实询盘均 UNKNOWN；本轮没有访问 /rfq。</p>'
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
    html+='<p>原DOM脚本仅保留 tag / text / 宽高非零 visible。href与以下几何在独立sidecar，未成为Guard证据。</p>'
    html+='<p>375/320仅为受控离线回归；原BrowserObservation v1原有390/1280视口不扩大。符合尺寸也不表示取得原生采集或签名来源权威。</p>'
    html+='<p>原始 href：<code>'+e(t['href'])+'</code>；只读解析：'+e(t['resolvedHref'])+'。没有请求该目标。</p>'
    html+='<p>累计透明度 '+e(t['opacity'])+'；包围盒 '+e(round(t['rect']['width'],2))+' × '+e(round(t['rect']['height'],2))+' CSS px；采样中心命中原目标 '+e(t['centerOnTarget'])+'。</p>'
    html+='<p>内容宽 '+e(m['scrollWidth'])+' / 可视宽 '+e(m['clientWidth'])+' CSS px；其它页面/时点/全站情况 UNKNOWN。</p>'
    html+=link(base+'/image','打开本次原始Chrome截图',key='cta-original-image')
    html+='<nav class="l2-nav">'+''.join(link(route(root,row['scenario'],w),str(w)+'px') for w in (390,375,320,1280))+'</nav>'
    html+=link(root+'/source-tasks','返回五维复核')+link(root+'/blueprint','在原蓝图中核对修复候选')+'</section>'
    return html
