# VEYFRONT 离线人工审核演练台 · Phase 0.5

**离线交互模拟 · 非真实审核/审批/分享。PRIVATE / NOT APPROVED / 不可客户外发。**

直接用桌面 Chrome / Chromium 打开本目录的 [index.html](index.html)。不需要安装依赖、启动服务、联网或登录。所有操作只在页面内存中；刷新回到初始场景。手机布局可在浏览器设备模式选择 375 或 320 px。

这是 [Issue #51](https://github.com/gloweaseco-leo/VRAE/issues/51) 授权的可操作 UI 原型，目标是帮助未来 Reviewer 判断“原文支持什么、哪些仍是假设、何时必须停下”。已实现点击原文/返回、逐项核对、二次确认、附理由退回/拒绝、旧版本阻断、零问题内部范围确认。正向按钮的结果固定为“模拟满足审核条件，未形成真实 APPROVE”。它不是生产审核模块，也没有模拟的真实人名、认证、native decision 或 ShareGrant。

| 固定场景 | 可以亲手操作的路径 | 不能据此得出的结论 |
| --- | --- | --- |
| 01 / 一个 404 联系路径 | 点击证据，核对原始 quote、UTF-8 定位、href、响应与时间；逐项核对或附理由退回/拒绝 | 不证明网站当前状态、工厂资质、丢单或收入影响 |
| 02 / 200，零问题 | 核对独立 200 合成捕获及范围，完成内部范围确认 | native=null；没有报告批准入口，不证明表单送达或全站健康 |
| 03 / 版本变化 | 先完成核对，再改变版本/HTML/引用/摘要/页脚/布局/来源/租户；观察旧结果失效 | 不存在重哈希后继续的旁路。HTML/来源/引用完整性变化须重置固定夹具；合法样式/版本演练也要整份重核 |
| 04 / 拒绝 | 用键盘或触控切换跨租户、未分配、Guard REJECTED 三种固定拒绝视图 | UI 隐藏不是访问控制；静态合成夹具随文件可读，不可承载客户私密数据 |

范围限制明确显示 403 / WAF / UNKNOWN 和未检查部分；没有把访问受限变成缺陷。所有四个场景使用新写的 `sim-*` 夹具；这些标签不是实际 RA-2、Guard 或 ReportVersion 的产出。

开工基线是已验收 main `60dbe1e1acfc84ad0849e84f3abe3712ad8ebccd`。已完整阅读冻结 V1.1 产品纲领、总计划及已合并 Phase 0 六份设计，并补读采购商/运营旅程。[fixtures.json](fixtures.json) 保留当时原始 Git 文档的精确 SHA-256。开工时 PR #47 的 `e2f9466f06bb3e7afbaf2e55575562d9d6fb453e` 仅以只读 pins 作为暂定兼容参考，原型没有导入它的 API、报告 HTML 或生成器；原先 Phase 0 的历史引用不改。

交付前 Owner 对 PR #47 发出 [FINAL PASS](https://github.com/gloweaseco-leo/VRAE/pull/47#issuecomment-6818626466) 并正式合并。随后本分支普通 merge 最新已验收 main **`61b88eb31d1dec668e7e05495b88fe2d8a5b25fe`**，无冲突。新 main 的 1611 个原始文件 blob/mode 全保留；原型六份浏览器输入字节不变，不因功能已合并而调用其 API 或解锁真实人审。PR #48 仍由 Codex-1 负责。

入口和交付导航：

- [2–3 分钟中文交互演示脚本](DEMO.md)
- [Reviewer 阅读备忘录与未解决问题](REVIEWER_MEMO.md)
- [实际浏览器测试结果、失败记录与证据导航](RESULTS.md)
- [精确文件哈希及 main 原始 blobs/modes 保护证明](evidence/manifest.json)
- [四个固定合成场景](fixtures.json) / [独立 404 与 200 捕获记录](reference/synthetic-captures.json) / [惰性来源原文](reference/synthetic-product-source.txt)

复跑命令（在仓库根执行，Node 24+，预先安装的 Chromium 路径可用 `RA3D_CHROMIUM` 指定）：

```text
node docs/03-engineering/ra3d-phase05-prototype/prepare-fixtures.mjs
node --check docs/03-engineering/ra3d-phase05-prototype/workbench.js
node docs/03-engineering/ra3d-phase05-prototype/browser-test.mjs
node docs/03-engineering/ra3d-phase05-prototype/seal-evidence.mjs
```

`prepare-fixtures` 只读取 main 与 PR #47 精确 Git 对象，不调用生产生成器。`browser-test` 使用真实本地 Chromium/CDP，鼠标点击和键盘事件驱动，逐次生成独立原始证据目录，不覆盖历史失败。浏览器只加载本地文件，CSP connect-src none、CDP blocklist、黑洞代理与 DNS 阻断共同限制外联；测试程序连接的 loopback CDP 不是页面 API 请求。临时浏览器 profile 被本目录 gitignore 排除；原型没有读取/写入持久状态。

只有本目录新增文件。生产代码、既有合同、测试、CI、Phase 0、PR #47 / #48 均不修改。Phase 0 的 A01–A48 **仍是 NOT_RUN / IMPLEMENTATION_NOT_STARTED**；本轮通过的是离线 UI 交互断言。任何触发的 GitHub CI 仅证明 docs/main 回归，不证明真实审批、身份或持久性。

交付状态：等待 Owner 独立验收；保持 Draft。RA3D 生产、真实模型、客户报告/分享、部署与合并均未执行。Human Gold 0/26，实际审批/分享/客户访问/E2/E3 均为 0。
