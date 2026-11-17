# 富DOM最小可信证据链提案 · 尚未启用

Owner授权：Issue119#6953147682。这个提案和 `dom_v2_poc.mjs` 是独立的离线POC，
不修改原BrowserController、BrowserObservation、EvidencePack、Guard、网络权限或正式结果。
POC输出固定 `poc_only=true / authority=NONE_NO_EV_REF`；应用不导入它，不能将它重新封装成ev-ref。

## 原v1缺口与可运行对照

原生产者只保留title/url和最多128个tag/visible/text。visible只是矩形宽高非零。
P0已实测透明/遮挡CTA仍visible=true；没有href、alt/src、几何或逐图片加载对应。
`node integration/s2_ux/browser.mjs <fresh-label> --rich-poc` 在同一合成HTML、
原390/1280及仅回归375/320上同时保存v1 DOM、原截图和独立POC JSON。
所有额外请求拒绝，不点击CTA、不发RFQ。新几何字段、原链接属性和图片状态可以实测；
**这只证明测量方案可运行，不证明原任务中存在这些可信字段。**

## 拟议新增合同（需要Owner批准后才能实现生产链）

版本应另立，不改变v1回放语义。服务端固定已审producer源码SHA/合同版本和采样角色/范围，
不接受页面自称producer、浏览器提交的UUID/SHA/额外JSON或自签“证明”。
采集必须来自当前原签名任务、SourcePolicy允许的页面和原受限broker；
保留原tenant/run/policy/version、URL、采集时间、viewport、原始对象字节，
由原pack投影产生src-/page-/ev-引用。APP source_ref与pack src-不可互换。
pack一致性不替代原任务权限、分配、撤权、当前版本与会话期限。

| 字段 | 最小只读采集 | 原则与边界 |
|---|---|---|
| href | 原A节点getAttribute(href)、原索引 | 不点击/追链；静态属性不等于实际送达/可提交 |
| alt/src | 原IMG节点属性，明确null与空字符串 | 不OCR、不认证语义；不新增图片请求 |
| geometry/hit-test | 原视口、client/scrollWidth、有限rect、computed display/visibility/opacity、disabled/inert、视口内受限中心命中 | 数值有限、固定精度、最多128节点；不概括完整可用性/WCAG |
| image state | complete/naturalWidth加原broker资源记录的精确src对应 | complete不等于加载成功；阻断/未授权跨域保持ACCESS_BLOCKED/UNKNOWN，不计网站图片故障 |
| truncation | 节点列表截断与文本截断显式记录 | 截断或空列表不能推出整页没有CTA/标题/语言问题 |

POC的中心命中不完整覆盖父级透明、clip-path、阴影DOM、iframe、所有遮挡点、动画时间变化、
触屏手势与键盘/屏幕阅读器效果；不能据此下全站可访问性结论。
图片naturalWidth只是浏览器状态片段，必须与原网络结果区分；POC不具有原broker资源权威。
捕获配置视口与CSS布局视口必须分别保留：首轮真实POC已复现390px配置下，
溢出页面的innerWidth变为560，不能将两者混写或据此声称配置已改变。
POC的capture_viewport来自隔离驱动配置，viewport是原浏览器测量，仍无生产权威。

SourcePolicy无BROWSER许可、角色/页面不适用、无已审生产者、未运行真实浏览器、
来源/视口/时间不匹配时均不产正负结论。375/320仍只离线回归，未经明确授权不扩生产视口。
无需改变GET/HEAD、主机/IP/DNS/重定向/预算/下载/跨域/SSRF、30秒租约或Guard。

## 正式启用前最小对抗验收

1. v1原字节回放和旧规则/报告保持兼容；新增字段采用新producer/evaluator版本。
2. 错tenant/run/policy/source/URL/时间/viewport/producer、旧截图、篡改对象、
   self-rehash、伪ev-ref、截图与DOM来自不同观察均拒绝；source pin由原签名任务独立持有。
3. 透明、遮挡、offscreen、disabled/inert、溢出、动态替换、截断、空DOM、
   多语言/专业词/图片正文、图片403/跨域阻断/损坏与真正已获取资源分别验证。
4. 所有未授权子请求和真实RFQ提交仍拒绝。范围内有据FAIL需定位到本观察视口/对象；
   缺字段不能作正负事实，英语语义保持HUMAN_REVIEW_REQUIRED。
5. C1外层版本化投影合规合并后才接适配口；不修改冻结execution.py。
   新结果进入原报告前须有版本化、独立重算的桥接；不能修改旧ReportVersion/回执含义。
6. 原SSR下同任务/来源/版本、当前审核双权威与Brief COMMIT边界原样保留；
   不能由POC或UI阅读提示直接保存另一套审核决定。

当前可交付是现有签名SSR五维阅读、现有原文人工待核候选和明确未知范围；
不是四规则完整启用、Gold质量通过、SEO评分、真实送达或正式人工审核。
