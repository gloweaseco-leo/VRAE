# Phase 0.6 P1 · 中文审核员优先阅读

**离线合成演练 / NOT APPROVED / 不可客户外发。** 对应 [Issue #55](https://github.com/gloweaseco-leo/VRAE/issues/55)，开工基线 main `a1321dac611ac2a38dca3b4785d71b0256d92136`，已验收原版 PR54 精确功能 SHA `489c5e973f6d67b4d7252503f0bde7a37966cb94`。

直接在本地 Chromium 打开 [工作台入口](../index.html)。新版先显示采购任务、固定捕获的联系目标状态、影响假设、候选动作和复验方法；首屏有一个明确的原始证据入口。中文事实描述显著标为“阅读辅助 · 不是原生 Guard 陈述”，原生英文事实、候选文字与源字节保持不变。

完整原生陈述、逐条确认、Guard、SHA、JSON 和原始 HTML 默认折叠；需要时展开，不删除字段。产品页 URL、联系目标 HTTP 和原始捕获时间仍在摘要直接可读。200 明确“0 项问题不等于全站健康/表单有效/送达”，原生 ReportVersion 仍 null。阅读和回查不会自动勾选；原七项核对与全部 native claim acknowledgement、二次确认均保留。

只修改授权的 `../index.html`、`../bridge-view.js`、`../bridge.css`。新测试/文档/证据全部在本目录；没有新证据引擎、第二套工作台、生产修改或新原生报告。原 dossier/HTML/JSON、exporter、held pins、旧 170 测试、历史失败/截图/manifest、Phase0.5、QA、Guard、CI 和 Gold 保留原 blob/mode。

- [旧版与新版实际首屏对比、操作说明和遗留问题](VISUAL_REVIEW.md)
- [真实测试计数及保留的非通过记录](RESULTS.md)
- [原 170 检查的版本化兼容差异](reference/suite-compatibility.json)
- [完整文件/源字节/原始记录 manifest](evidence/manifest.json)

本环境复跑（仓库根，Node 24+；原有 Chromium 路径可用 `RA3D_CHROMIUM` 指定）：

```text
node docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/prepare-suite.mjs
node docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/compat-170-plus.mjs
node docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/seal.mjs
node docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/audit.mjs
```

`--baseline` 只控制附加摘要测试和输出标签，**不会把新版界面变回旧版**；本轮旧版基线确实在修改三个 UI 文件之前执行，输入快照与 main 原始 Git bytes 一致。不要在当前新版误用该标签来宣称获得旧版截图。要再次拍旧版，需单独检出 accepted main；不覆盖已有本轮旧版记录。

兼容 suite 从固定 Git 对象读取原 170 源码，六类有限适配可逐项逆变换回完整原文件：定位当前父目录、将所有输出限于本目录、用真实鼠标展开目标祖先 details、鼠标动作前等待布局稳定、增加首屏截图和新增测试/执行源码记录。原 170 条断言的 ID/表达式/预期不改，未 skip/xfail，不重试失败断言。原网络与异常检查仍在全部操作后执行。新旧原始运行和所有 ERROR/FAIL 原样保留。

实际结果：旧版 170 PASS；最终新版 **原 170 + 新增 123 = 293 PASS**，0 FAIL/ERROR/SKIP，1280/375/320px、404/200，42 张新截图；页面外部请求和 Runtime 异常均为 0。四项 hosted CI 的最终精确 HEAD、原始日志与 checkout parents 在 Draft PR 记录，不能用 CI 替代 UI 实测或生产人审。

仍无真实身份、持久决定、ReviewTarget/事务、ShareGrant、客户访问或分享。未做真人理解率/耗时研究、真机/微信/读屏器完整验收；测试数量不代表商务效果。Human Gold 0/26，RA3D production NO_GO。完成后保持 Draft，停止等待 Owner 审计。
