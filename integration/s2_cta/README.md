# CTA-01 / CTA-03 受限证据候选

Refs [Issue119 Owner CODE GO](https://github.com/gloweaseco-leo/VRAE/issues/119#issuecomment-6969477769)、Issue137、Issue134、PR141。原分支已正常 merge Owner 新验收 main `d38fd7263ea0d8ce357de54ef22cda90cdb86b9b`，合并提交 `81cbc610068ed7493339797d6518de79dabbe9af`；保留 S2 五维签名工作台与 S4 管理摘要、PG Brief、合成 VF 内部接单。不 force/rebase，不等待或改动 Codex3 的 S5 分支。

## 本轮主干整合

原组件入口之外，当前真实工业任务经既有 NativeBusiness → s2_acceptance_sources.bind，将固定合成参考资料绑定到原 SourceBinding；仍由原 Workbench.handle 检查任务权限、当前报告、租户、来源与版本。没有替换 NativeBusiness/NativeTasks，没有新建 SSR 或身份系统。

两张 CTA 卡可从原五维页面的询价任务进入。详情并列显示 A / BUTTON 的原始 href、可视范围、尺寸、显示属性、透明度、中心命中与真实截图；按正常、透明、遮挡、溢出四种场景分别说明采购商可能遇到的障碍及对应 Rebuild 修复候选。没有观测的表单提交、询盘送达和转化结果始终 UNKNOWN。

`evidence/cta-main-d38/` 是对既有批准 DOM 的新一次 Chrome 测量：四场景 × 四视口，共16记录、49采样检查；固定 receipt SHA256 和每张截图哈希在每次读取时重放。输入固定为批准 Git blob 的 UTF-8 原文，避免宿主换行差异；原 BrowserObservation v1 / DOM_SCRIPT 未修改。生产页面展示的来源仍明确为 synthetic.invalid 独立合成参考，**不是当前工业任务网站的实测结果**，不晋升当前 pack / Guard 事实，也不推断转化损失。新的报告版本不会自动继承旧 CTA 引用。

原同任务 APP202/Worker/PG/Chrome 旅程新增 CTA 原界面、真实鼠标跳转、四场景来源、受保护 PNG 与手机视口检查，再继续原七包、Controlled、PG Brief、S4 ACK和重启验收。新原生专项覆盖主干接线、两目标、原 S2/S4 保留及未登录、跨租户、撤权、过期、旧版、任务拒绝和证据篡改。自然 CI 以新 HEAD 的首次结果及工件为准。

历史 head `794866e` 的 RA4B P1 3.13 Docker 构建失败继续保留，底层 stderr 未公开、根因 UNKNOWN；本轮正常主干合入后提交新 HEAD 触发自然 CI，不重复旧 HEAD 测试刷绿。

整合复核发现并修复可选参考的隔离问题：原报告显式修订后，旧 CTA 引用失效时曾连带拒绝整个 S2 工作台。现在仍拒绝旧 CTA 详情/PNG，原有权限内的五维及两张来源卡继续可读、询价观察回到 UNKNOWN；篡改 CTA 参考同样不抹掉有效的原来源。原任务、身份与来源校验均仍在参考读取之前执行。新原生及真实旅程直接验证该边界。

## 使用

原受控五维页面 `/b5a/l2/r/{原report_id}/source-tasks` 的「本轮：核对询价入口与手机障碍」可直接跳转到询价任务。两张候选卡链接正常／透明／遮挡／溢出场景、390/375/320/1280 原观察与受保护截图。原报告、原蓝图与 Controlled 审阅仍走原入口；附加候选不加入 Finding、原审核项或蓝图事实。

复验入口：`python -B -m integration.s2_buyer_workbench.lab <唯一标签>`。使用原签名 HTTP 登录与原 B5B SSR，父进程保留签名私钥，SSR 子进程仅接收公钥。Chrome 可用 `RA4C0_CHROMIUM` 指定；CI 使用 `/usr/bin/google-chrome`。

## 当次具体观察

已有批准合成 DOM：`integration/s2_ux/fixture.html`，Git blob `6b1e3d606de594e8359c8f08a64b11d7378d9637`。未改 DOM、原 `DOM_SCRIPT`、Guard、EvidencePack 或旧浏览器入口／超时。四场景分别在 390、375、320、1280 渲染，共 **16** 条实际 Chrome 记录和 **49** 项采样检查。

| 场景 | 本次记录 | 边界 |
| --- | --- | --- |
| 正常 390 | A 的原 href `/rfq`，只读解析 `https://synthetic.invalid/rfq`；目标约 149.06 × 44 CSS px；BUTTON 无 href | 未请求目标，不验证业务 JS 或投递 |
| 透明 390 | 原 v1 宽高非零 `visible=true`，累计 opacity=0，中心仍可命中控件 | 原 visible 不能证明人眼可见 |
| 遮挡 375 | 同一控件中心命中为 false；截图能看到遮挡层 | 仅测试中心，不覆盖所有点击点或键盘路径 |
| 溢出 320 | scrollWidth=560 / clientWidth=320 | 仅本次场景，不推断其它页面或全站 |

来源 URL 是离线渲染的虚拟 origin `synthetic.invalid`，**不是原报告中的 example.org 网站**。采样只把原合成 HTML 字节交给 Chrome；其它请求阻断，不访问 `/rfq`。原报告 SourcePolicy 的 id/version 只用于当前报告关联与读取校验，不表示扩大其允许的远程主机或采集权限。Owner 已批准此离线 DOM 及受控 Chrome；未作真实站点采集。

href、样式、命中与几何保存在独立附加记录中。原 BrowserObservation v1 结构不扩展，390/1280 的 `legacyV1DimensionsOnly` 仅说明尺寸符合旧视口，不主张取得原生采集权威；375/320 仅为受控离线回归。没有 Guard 引用的观察仅为 `READ_ONLY_REVIEW_CANDIDATE`；不伪造 ev-ref 或 FAIL_WITH_EVIDENCE。

卡片给出采购影响假设与 Rebuild 修复候选：调整遮挡层、限制窄屏内容宽、核对入口目标并按同一范围复验。目标响应、业务 JS/样式在其它页面的行为、表单提交、邮件送达、真实询盘、排名与损失均 UNKNOWN。44px 只是此演练复核对照，不作为全站 WCAG 结论。

## 当前权限和版本

附加记录由可信启动器独立保存 SHA256、采样时间窗和原 tenant/run/policy/pack/report/version/content/display/行业配置绑定。每次读取先走原 `DeepConsole.current`，重放原只读候选、字节／图像哈希与边界校验，输出前再次检查原当前权限与版本。截图由相同保护路径提供，未改原 CSP。

未登录、跨租户、无定向授权 Reader、POST、撤权、过期或报告修订后的旧附加记录均拒绝；原报告历史字节与原 Controlled 决定保持不变。安装器拒绝覆盖已有 NativeBusiness/NativeTasks，未建立第二应用、登录系统、审核引擎或事实库。

## 原独立组件验证历史（不替代本轮主干验收）

最终代码验证提交 `2b96b09ab69ca017f198e5ecc3e5fe7bc2ec5ddd`，与 [source.json](evidence/cta-live-02/source.json) 内 head 一致。

- **177 PASS**：新增 25 项附加记录／原权限与版本负例 + 原候选、签名与 C1/C2 相关合同。单位测试中的构造 PNG 明确不是浏览器证据。
- **38 PASS**：真实 Chrome、原签名 SSR、两候选、真实鼠标跳转到询价任务、来源详情、受保护 PNG、原 Controlled 审阅提交、跨租户和未授权 Reader 拒绝；14 张 SSR 截图。
- **16 个 Chrome 样本／49 PASS**：原 DOM 脚本与补充测量并列，16 张原场景截图。
- Ruff / Node 语法检查通过；两次完整 live 均成功。第二次仅修正采证工具截图前重置滚动的问题，并增加实际锚点导航验证，不把页顶图当询价区证据。

证据：[`evidence/cta-live-02/`](evidence/cta-live-02/) 与 [`native-311.xml`](evidence/native-311.xml)。公开留存仅允许名单内结果、源文件哈希及合成图像；不含 Cookie、私钥、浏览器 profile 或临时数据库。真实 Chrome/SSR 与临时 profile/服务退出见 cleanup。

此为原 C2 受控组件，不是 C3 的 APP202→Worker 同任务整机证明，也不冒充 PG Brief 或真实客户反馈。自然 CI 以最终 PR head 为准，不手动重跑。历史 PR124/127 RED 保留。INFO03、TECH02、真实未观察范围及 S5 统一分层验收责任保留。
