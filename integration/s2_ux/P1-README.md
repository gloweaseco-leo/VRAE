# C2-P1 · 原签名SSR五维采购复核

Owner：Issue119#6953147682；accepted base `94a58b9867d96f104941874e07a2c4a4c84ec27f`。

后续Owner组合授权 PR124#6964152145：原分支已正常merge正式验收的PR121/main
`a5b8c30ccefb656c266d75e66f9f20ceb7df1080`。本P1运行/UI实现不变，
新增C2自有组合负例与新HEAD自然CI；父SHA/tree/冻结blob见 [COMBINED-MAIN.md](COMBINED-MAIN.md)。

新增页面 `/b5a/l2/r/<existing-report-id>/buyer-tasks` 直接进入原 DeepConsole 的
Directory.require → Ledger.read → 渲染后current重验流程，不另建服务器、身份、报告或审核账本。
导航中的“五维采购复核”以制造业买方的找型号、核规格/工况、核供应商资料、准备询价为顺序，
保留第五维 SEARCH_TECHNICAL 的真实未知，绝不将工业工况评估改称SEO分析。

## 实际读取和审核范围

`apps.operator_console.l2_buyer_views.reading/render` 只消费已由原账本核验的不可变DeepReport。
逐维关联原Finding、来源URL/采集时间/定位、原结果、原蓝图及标准/定制候选；
全部引用保留，默认先展示一条来源，其余可展开。原文候选只扫描保留quote，不扫描中文界面文案。
报告版本ID、完整display hash、source digest、industry配置/版本与原覆盖记录可核对；
当前报告未保留独立SourcePolicy版本时明确UNKNOWN，不用行业版本替代。
选定快照数量不是全站页数或受信采样分母，覆盖分母仍UNKNOWN。

原生工业六规则及逐型号结果映射其已有buyer_task；不抵扣原通用16规则。
通用16项分别列入五维，但当前报告没有新S2执行记录，保持未载入/UNKNOWN。
这不是宣告全局旧六条从未执行，也不是宣告新十条已启用。

| 四项范围 | 当前可运行子集 | 仍不支持的正/负结论 |
|---|---|---|
| INFO-03 | 来源原文中的中文/占位候选及原证据入口，UNKNOWN + HUMAN_REVIEW_REQUIRED | 语言质量、术语、翻译正确性、图片正文、买家流失 |
| CTA-01 | 原P0有界DOM文本候选可复用；本报告如无原href就标UNKNOWN | 实际可见href/可提交/送达 |
| CTA-03 | 原截图/来源边界及本SSR页面390/375/320/1280操作回归 | 被诊断网站的遮挡/几何/WCAG；不能用本SSR截图替代来源站观察 |
| TECH-02 | 原P0的标题/图片标签候选可复用，报告显示缺原字段的UNKNOWN | alt/src、对应资源加载、搜索排名或Lighthouse |

四项均没有新增Guard Observation或正式规则PASS/FAIL。阅读提示不新增原报告Finding/审核项，
不被旧回执“自动批准”。入口跳回原版本逐项审核、原蓝图和报告打印；
决定/修订/撤权/重启/旧版本/双hash校验均保留原实现。

## 可复验命令

```sh
python -B -m pytest -q integration/s2_ux integration/l2/test_l2.py integration/l2/test_codex1.py tests/evidence tests/rules --junitxml=<new-output>/native.xml
python -B -m integration.l2.lab <fresh-label> --s2-ui
node integration/s2_ux/browser.mjs <fresh-poc-label> --rich-poc
```

第二条实际启动**原B5B Application**及签名L2目录，通过Chrome登录、五维来源定位、原Controlled逐项审核、
错误版本/越权/撤权、追加版本、进程重启回读同报告hash与决定、原中文报告/蓝图PDF。
先跑原离线产物兼容，再自动跑同一应用的原生P40/V25组件来源；
这是实际SSR活体操作，不宣称新APP202/Worker COMMIT或S2整机已完成。
签名私钥在父进程，不给SSR或浏览器；没有真实客户访问。

第三条是独立富DOM离线POC。原生产者、pack、Guard、执行器和网络未改。
POC输出无生产权威、无ev-ref，不导入页面/执行器。精确缺口、拟议可信链和对抗验收见
[RICH-DOM-PROPOSAL.md](RICH-DOM-PROPOSAL.md)，需Owner批准才可开发/启用生产来源扩展。
390px捕获配置与可能被溢出扩展的CSS布局宽度分别记录；375/320仍仅回归。

## 保留与停止线

所有历史RED保持原件；独立环境缺依赖导致的收集错误、首轮class匹配错误、POC390/560差异均记录。
使用既有锁安装3.11/3.13依赖，不升级锁。原30秒Worker、pack blob、旧execution.py、Guard/SQL/RLS、
C2旧审核权威、C3 Gold和PG/Brief双权威不改。没有付费模型、外网、真实RFQ、正式人审或外发。
Gold0/26，无法计算真实质量精度。C1外层 `vrae.rules.s2` 已从accepted main正常合入；
不修改旧执行器，不把投影晋升原生结果；其他未合并Draft不复制。
本Draft只交C2-P1上述可运行范围，不是四规则完整启用或S2 EXIT。
