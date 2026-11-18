# 来源候选五维采购复核：独立受控只读分包

Owner：[PR124 产品裁决](https://github.com/gloweaseco-leo/VRAE/pull/124#issuecomment-6966541983)。
当前 accepted main：`95ed55321775223e95cf0a1585220951cc692648`。
本分包直接从该 main 开始，未复制或合并未验收的 PR124 / PR123 / PR127。
只新增自己的 integration 目录与 workflow；没有修改原权限、Review/Guard、
报告生产器、pack、规则、SQL 或既有 workflow。

## 可操作的用户路径

1. 用原受控签名身份进入同一 B5B SSR，读取同一原 Ledger 的当前报告。
2. 依次找到产品型号、核规格工况、核供应商资料、准备询价、核搜索技术范围。
3. 参数候选显示 P40/V25 的资料版本 R1、来源条件与待补买方工况。
   证明及主体联系候选保留其来源展示边界，不认证证书或法定身份。
4. 每项显示实际候选结果、下一步与可点击的来源入口；来源页核对原 UTF-8
   字节、采集时间和 URL。原始 HTML 仅作为转义文字，不能执行。
5. 回到原报告、原 Rebuild 蓝图与原逐项 Controlled 审阅，实际保存本版本决定。
   候选不会自动新增原审核项，不影响原报告 payload/hash。

来源接口使用 main 已验收的 `evaluate_s2 / verify_s2_projection` 和独立
`IndustryPins`，消费 `s2-projection-1.2.0`。INFO-02 / TRUST-02 / TRUST-03
来自原工业来源投影，DISC-03 / SEO-02 / TECH-01 来自原静态投影。
引用 URL/时间通过同一个已验证 report snapshot 关联，适配原两类引用结构；
不为缺少 inline URL 的静态引用伪造信息。

展示是只读候选，不是新的 FindingPackage / DeepReport / Guard 事实。
原 6 工业评估、通用 16 条范围及新来源候选各自保留原语义；不互相抵扣，
不计算网站评分或全站通过率。新四项 UX 只显示其真实观察边界：INFO-03
语言质量待人工；CTA-01/03 提交性、遮挡与几何仍 UNKNOWN；TECH-02
图片属性/加载与搜索排名仍 UNKNOWN。未观察不升格 FAIL。

## 权限及来源绑定

页面路由为 `/b5a/l2/r/<existing-report-id>/source-tasks`，通过现有
`Application.native_business` 扩展口安装。安装器拒绝覆盖任何已有业务口或
native_tasks 权威，只允许 CONTROLLED + OFFLINE_SYNTHETIC 的原生来源。
这不是生产 M1/Worker 接线，也不绕过其双权威。

原 Application 的 Host/Origin/方法检查先执行。新视图继续在原目录锁内调用
`refresh → sid → DeepConsole.current`；原 require/read/access 控制仍决定
租户、角色、当前版本、过期、撤权及定向授权。渲染后再次 current，并核对版本
与 display hash。来源 pack 与原 NativeSource held pack、tenant/run、source
digest 绑定，候选通过原 verify 重算；浏览器不能提交 projection、角色或 pack。

同一来源的原静态引用与工业引用统一从 report snapshot 定位 URL/时间，
但不合并/升级其事实语义。每个引用页都先验证当前身份及整个候选，再重放字节。
审核与蓝图操作直接链接原接口，不建新决定表或新的自动批准路径。

## 验证及复现

```sh
python -m pytest -q integration/s2_buyer_workbench
python -B -m integration.s2_buyer_workbench.lab unique-local-label
```

使用既有锁定依赖。`lab` 的签名器保留在父进程；HTTP 子进程只有公钥 JWKS。
登录通过原 HTTP challenge/session 签名链取得 HttpOnly/SameSite cookie，
受控启动器再将其交给独立 Chrome profile；没有伪造 session 或用浏览器自报角色。
Chrome 实测 390/1280 主视口、375/320 回归、原文定位、原蓝图、原审核表单与实际
原决定提交，以及跨租户/无定向授权拒绝。页面没有脚本/外链抓取。
浏览器 profile、cookie、私钥和配置不在公开证据清单中。

最终本地 Chrome 活体：**19项检查通过，8张实图**；实际中文 glyph 与
四视口可见操作目标44px检查通过。原审核使用鼠标/键盘逐项操作并通过原表单提交，
保存的仍是原版本 Controlled 演练决定；浏览器/HTTP进程退出实际观察到。
[390px工作台](evidence/local-ui/source-tasks-390.png) ·
[1280px工作台](evidence/local-ui/source-tasks-1280.png) ·
[来源原文](evidence/local-ui/source-citation-390.png) ·
[原审核保存](evidence/local-ui/original-decision-390.png) ·
[浏览器回执](evidence/local-ui/browser.json)。

这些是本地提交前的受控实物；正式新HEAD/源码hash以自然CI的 source.json 为准。
本地已有Python环境补装原psycopg锁到本分包隔离target，未修改共享Python环境；
双minor CI使用原 requirements-ra4b-p1.lock 全锁。

13项原生测试覆盖候选验伪、原文转义、跨租户、未领取定向授权、无签名、POST、
过期、渲染中撤权、禁止覆盖现有业务权威、静态引用定位、配置不适用展示，以及原审核项不增加。
独立 CI 双 Python 同时保留相关 C1 来源/原 L2 回归与真实 Chrome 操作，既有
workflow 原样自然运行。首次本地调试 RED 保留：原 transport 测试缺少 Host、
两类引用格式差异、urllib 自动重定向转发 Authorization 被原权限拒绝、
受限环境第一次 renderer attach 超时；没有将这些记录改为通过。
补充组合首轮100项中98通过、2 RED：一项测试错误假定该合成fixture有DISC-03
引用（实际为UNKNOWN），另一项本地环境缺原锁psycopg。现改用实际有字节引用的
静态候选测试，并隔离安装原依赖；首轮RED XML保留在 .runtime/first-combined-red.xml。

本分包首轮官方CI `b605fc1` / run44228176135 的双minor原生100项均通过，
浏览器步骤在启动前被受限标签校验拒绝：workflow传入 `hosted-3.11/3.13` 含点号。
修正仅把workflow调用和工件路径换为固定slug `hosted-311/313`；保留原严格标签
校验、Chrome参数、时限与权限。不将该首轮RED改为PASS，也不手动重跑原HEAD。

## 边界

P40/V25 为 accepted C1 合成资料，URL 仅是内存来源标识；没有真实第三方访问。
工程适配、证明真伪、联系送达、全站分母均 UNKNOWN。没有 RFQ、付费模型、
正式人审、生产部署或客户分享；Gold 仍 0/26。

本分包不改变旧 PR123 39/40 / PR124 40/42 RED，也不解决其 Chrome 根因。
[D0 修订](https://github.com/gloweaseco-leo/VRAE/pull/127)仅得出有效观测但仍 UNKNOWN。
本分包提供给 Owner 独立验收，不代表 S2 EXIT 或新规则晋升。
