# 原生工业数据到现有L2报告/蓝图

本轮增加的是C3可调用的运行时生产适配器，基于已验收C1原生verify，不是MP25静态报告替换文字。接口见 [NATIVE-v1.md](NATIVE-v1.md)。不改C3/APP/Worker/PG/原身份/Guard及冻结代码，也不独立宣称Worker整机E2E。

先看 [P40/V25原生深度报告](example/native/l2-deep-report.pdf)、[有据Rebuild蓝图](example/native/l2-rebuild-blueprint.pdf)及[审核页面](example/native/review-operable.png)。正文另有 [报告Markdown](example/native/l2-deep-report.md)、[蓝图Markdown](example/native/l2-rebuild-blueprint.md)。这些是实际Collector→EvidencePack→C1诊断/完整Guard重放→C2报告→现有SSR/持久审核的**受控组件复验**，不是新APP202/真实Worker同任务整机。

来源8页、81条原始事实、19项原生评估全部保留。当前样本有两项压力标量冲突；供应商日期的两条型号记录共用一份资料，只形成一份证明资料工作包。它们不是四个网站故障、工程不适配或真实认证否定。RFQ缺交付目的地属于买方待补。7项蓝图明确实际页面/原引用、条件式修改、企业资料、责任、验收与标准信息组织候选/外部工程复核边界，没有把现有已观察路径说成坏掉，也没有造出曲线404。

新NativeSource冻结真实服务端输入并执行原C1完整verify；旧OfflineSource的合同/保证和validate仍独立，不能改常量把任意JSON升级为原生结果。证据保留原SHA、路径、引用和字节切片，完整display/report hash包含业务解释及蓝图；原ReportVersion hash与诊断hash均不是这个完整报告hash。

已有账本逐项审核、拒绝/修订、版本化决定、受控定向访问撤销和重启回读继续使用。C3消费的review DTO来自真实持久决定，current_report保留目录锁与SQLite事务到C3实际Brief COMMIT；C3必须同时保留原任务签名、期限、撤销、pack/run/版本权威。DTO、示例job字符串或本模块不是授权，正式人审/外发/生产均未启用。

## 复验与操作

```powershell
python -B -m pytest -q integration/l2/test_l2.py integration/l2/test_codex1.py
python -B -m integration.l2.lab native-owner-unique --native-component --interactive
```

第二条命令打开现有同一B5B签名SSR的受控原生组件；Ctrl+C停止。专用浏览器用虚构受控Owner，不是正式Owner身份，签名私钥留在父进程，浏览器和SSR无私钥。

既有双Python CI入口保持不变：test_l2.py加入原生正反例；既有lab先验旧离线样例，再用相同SSR实现实际运行新的原生P40/V25场景，各自独立来源和数据库，不能互冒。官方工件的主要新报告在 `native/l2-deep-report.pdf`、蓝图在 `native/l2-rebuild-blueprint.pdf`；根目录MP25仅为旧兼容回归。publication.json同时列明两种来源，原生组件仍明确NOT_APP202_WORKER_E2E。

仓库example保留本地开发运行的真实原件、源码文件SHA与当时HEAD；不冒称提交后CI。最终精确SHA和官方工件在新Draft PR回执中提供，历史RED不覆盖。本模块通过后，只有C3用实际新APP202/Worker/签名Reader及同一pack/run完成组合，才可声称整机闭环。
