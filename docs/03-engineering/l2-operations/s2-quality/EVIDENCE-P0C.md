# C3-P0 最终修复候选证据

正式执行源码：`e5b8a9313c98f59b7baef9769a31955630e1a6bf`。本轮后续只封存docs；推送HEAD在PR123回执记录，不把封存SHA冒称此前执行时SHA。范围仅Issue120 C3-P0，尚非S2整机EXIT。

[操作说明](README.md) · [最终回执](published-p0c/local-receipt.json) · [原始ZIP](published-p0c/raw-evidence.zip) · [逐成员哈希](published-p0c/raw-evidence-manifest.json) · [实际审阅文本](published-p0c/reviewer.md) · [空白人审输入](published-p0c/s2-review-input.json)。

## 最终同源验证

| 环境 | 实际测试 | 导出/独立重放/接收 | 原默认库存 |
| --- | --- | --- | --- |
| Windows Python3.11.15 | 131/131，零skip/error/failure | 通过，Gold0 | 原2564完整ID，missing/extra=0 |
| Windows Python3.13.13 | 131/131，零skip/error/failure | 通过，Gold0 | 原2564完整ID，missing/extra=0 |
| Linux Python3.11.17 / pytest9.2.0 | 131/131，零skip/error/failure | 通过，Gold0 | 由两个Windows证明，不冒称Linux此项已执行 |

Linux基础镜像**实际没有cryptography/psycopg**，原integration/l2_ops/conftest.py仍在源码快照中。只读原生源码卷避免Windows绑定文件IO瓶颈；network none、cap-drop ALL、no-new-privileges，未添加依赖或修改原fixture。

[3.11 JUnit](published-p0c/native-311.xml) / [3.13 JUnit](published-p0c/native-313.xml) / [Linux JUnit](published-p0c/linux-native.xml)，全部原字节。Windows实际自动wall分别200906000000ns、361000000000ns；不是人工工时/费用。

默认库存证明是**无过滤默认收集，不是测试执行**：[3.11](published-p0c/default-inventory-311.json) / [3.13](published-p0c/default-inventory-313.json)。原manifest SHA `ee50d3ce0a4c424c7d98d94ef123629ddcbd40a4be0992e2fd81fb7711c5f537`；完整ID在ZIP中。新S2测试采用quality_cases.py/input_cases.py专用文件，与原industry/l2_cases.py一样由专用门禁显式执行，所有新安全项仍在131中。没有修改旧库存/manifest/pyproject/CI，没有新增skip或旧套件过滤。

## 首轮RED与最小修复（保留）

首轮HEAD `179034b70d3f2d12c11602161baabc731449c6e0`：18工作流，16成功/2失败；38Job，34成功/4失败，全部attempt1。[完整原始API回执](first-ci-red-179034b/full-first-attempt-ci.json)。

1. 两个C3 Job在收集前加载旧PG conftest并因基础依赖无cryptography退出；没有产生JUnit，不能算测试通过。修复仅把自己的输入测试及JSON解析移到便携tests模块，原conftest/签名/锁文件不改。[原始ZIP/日志/摘要](first-ci-red-179034b/manifest.json)。
2. 两个RA4B Job普通测试收集2603项，0error/failure、25个既有环境skip；原2564冻结库存正确拒绝新增39项。修复仅将自己的新套件改为显式收集，保持旧库存原样；两个[官方原始ZIP](first-ci-red-179034b/runtime-311.zip) / [313 ZIP](first-ci-red-179034b/runtime-313.zip)保留。未推送已知仍有库存问题的中间候选。
3. 一个额外只读Windows绑定Linux探针被操作员停止，exit137，**不是原生崩溃/测试PASS**。100次读取实测907085414ns，而tmpfs1444131ns；其未完成日志/CID/清理在私有原始目录保留。最终验证使用字节相同的Linux本地只读源码快照并已完整通过。

[最初Windows候选证据](EVIDENCE-P0.md)及published-p0原件保持，开发和中间localp0a/localp0b输出均保留。没有重跑旧HEAD CI、没有更改历史RED。

## 来源与人审真实性

最终仍为6个通用夹具、9个工业场景、32个新增单元、15个有界范围、21个分层。原26候选仍独立0/26；新人审分母0/32。实际report_ref和packet_ref及两版Windows完整benchmark字节相同，源解释见[原始输入/观察包](published-p0c/s2-packet.json)。

默认[新质量指标](published-p0c/human-quality-assessment.json)和[原26指标](published-p0c/original-26-assessment.json)均NOT_EVALUABLE/null。所有身份/日期/裁决字段保持空白，复用原Owner签名与带外信任，未生成实际签署或审批许可。合成TP3/FP0/FN0/TN17与12个弃判不构成真实90%精度/质量PASS。

ZIP1144166字节，SHA256：`b299adf4528f5a699d76575fc296c69ec660928c6d1b04c905ebbe709032c321`。完整Windows/Linux输出、默认库存完整ID和每成员原始哈希在ZIP与manifest中。

## 定向清理与边界

[Linux主机回执](published-p0c/linux-host-receipt.json)确认两个CID及自有源码卷均不存在：
- populate：`1517ceb6b0ea304abdaaf288bcfb8b3468d36ac9c8fd9bb8ca46f24422c022ed`
- QA：`7b514f823887ca576e604880249c1f9cb77ba5e323a8863f23f405ba67af1912`
- 卷：`vrae-s2-c3-code-e5b8a9313c`

未启动本地PG/Chrome，旧匿名卷UNKNOWN_UNTOUCHED，不全局prune。原vrae/apps/db/contracts/industry-packs/旧Gold/旧库存/旧CI无修改，pack blob仍8d45d5882103323e62bc4bd61a4379899e759966。没有复制C1/C2未合并源码、外站/付费模型/正式人审/外发/部署。

保持Draft，等待本修复HEAD自然CI及Owner独立P0验收。结论仅C3_P0_ENGINEERING_READY_GOLD_PENDING / S2_QUALITY_NOT_EVALUABLE；C1/C2合并后才开展真正五维PG/Worker/SSR/Chrome整机P2，不将本P0冒作S2 EXIT。
