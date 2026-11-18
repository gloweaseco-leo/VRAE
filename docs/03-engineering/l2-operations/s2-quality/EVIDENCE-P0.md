# S2-C3 P0 原生证据｜待 Owner 独立验收

范围仅 [Issue120 C3-P0](https://github.com/gloweaseco-leo/VRAE/issues/120)，不是整个 S2 EXIT。初始 accepted main `84276325befdcf858852a1ec791e8b0695a515eb`；正式执行源码 `d41e1f881b25b44fed8ac625f17a1783acd5fba4`。后续证据封存提交只增加 docs 文件，可执行差分必须为空。

[操作与边界](README.md) · [开发 RED](DEVELOPMENT-RED.md) · [完整本地回执](published-p0/local-receipt.json) · [原始 ZIP](published-p0/raw-evidence.zip) · [ZIP及每个成员哈希](published-p0/raw-evidence-manifest.json)。

## 同源码原生门禁

| 原生解释器 | 实际测试 | 包导出/原生独立重放 | Gold只读评估 | 自动化 wall ns |
| --- | --- | --- | --- | --- |
| Python3.11.15 | 131/131，零skip/error/failure | 通过 | 新0/32、旧0/26 | 333609000000 |
| Python3.13.13 | 131/131，零skip/error/failure | 通过 | 新0/32、旧0/26 | 296766000000 |

原始 [3.11 JUnit](published-p0/native-311.xml) / [3.13 JUnit](published-p0/native-313.xml)，解释器及实际 import 根见各回执。同一工作树与原生 source manifest 全部文件在运行前后哈希一致。lint通过，原mypy120文件通过。开发38项的首次专项另保留为 [开发JUnit](published-p0/development-first-38.xml)，不冒充正式候选131项。

可重现命令为原生：
`python integration/l2_ops/s2_quality_verify.py --label <new-label> --python311 <native311.exe> --python313 <native313.exe>`。
当前两轮实际 label=`localp0a`。每轮依次执行旧 benchmark、新质量安全、CLI输入、工业兼容共131项，再执行实际 packet导出、verify-export、assess、legacy。任一失败停止后续版本，拒绝覆盖已存在label。

## 输入、输出与业务含义

- 6个通用夹具覆盖5类站型，另有9个工业场景，共15个有界范围、32个新增独立单元、21个分层组。原26个候选仍是独立集合，不因新增数据而改变。
- 31个单元有原生观察；1个计划单元因原403停止而无原生观察，仍保留 UNKNOWN/分母。来源包、时间、适用范围、字节/引用定位全部在 [实际packet](published-p0/sample-packet.json)；[实际审阅文本](published-p0/reviewer.md) 可直接给内部人员核查原生判断与行动边界。
- [分层及覆盖统计](published-p0/candidate-statistics.json) 的合成二元计数 TP3、FP0、FN0、TN17；另有12个弃判：UNKNOWN10、BLOCKED1、NOT_APPLICABLE1。二元precision/recall只是合成候选算术，不能作为真实准确率或90%质量通过。
- 新人类Gold分母0，旧26项仍0/26 pending。人类TP/FP/FN/TN/precision/recall/严重事实虚构数量均null：[新只读接收](published-p0/human-quality-assessment.json) / [原26接收](published-p0/original-26-assessment.json)。
- 两版产生相同 report_ref、packet_ref 及完整 benchmark 原始字节；不是把第二版指向第一版旧输出。每版分别运行原生采集、诊断/Guard和导出/重放。
- report_ref：`s2-bench-7e003f31cd4ac486fdcbd7edb18c3e41d29bd1dc6998838e7da4fe712ce77bb7`。
- packet_ref：`s2-review-packet-8a1e2ca7ade5936f9ff8bede05fc3a3b671809ee76eec0f2b57d2c8dde4e438b`。
- 668746字节的原始ZIP SHA256：`c6fc384a5210b1d3278eb5cc6aac044a7da471064a20ce9d5e58e888d570c0e9`。每个原始成员均逐字节核对；本地原始目录继续保留。

## 安全与质量负例

覆盖改packet并重新哈希、无证据/跨run/tenant/来源/时刻/版本、伪外部身份/签名、内嵌自信任、重复JSON字段/非有限数/大小上限、UNKNOWN/BLOCKED/N/A当TN、重复导入与冲突排除、不覆盖人工改过的review、伪造专业事实被独立重放拒绝。源定位检查实际解析原包对象并核对字节切片/内容哈希。

两名真实独立人员的字段保持空白，见 [审阅输入模板](published-p0/sample-review-input.json)。新只读接收复用原 OwnerTrust/verified_owner_rows/签名namespace，不生成密钥、签署、人名、日期或权限。原26行、原签名核验及信任锚未改。

## 源码和阶段边界

所有生产 `vrae/apps/db/contracts/industry-packs`、原Gold/quality/scenarios/samples 均无差分；pack精确blob仍为 `8d45d5882103323e62bc4bd61a4379899e759966`。旧CI未改，只新增本P0的路径限定工作流。

本P0实际统计已验收的三条通用路径规则和独立IND六规则；没有把未合并的S2十条新规则或浏览器字段算已实现。C1/C2候选只读契约用于后段准备，未复制源码。S2真正五维整机、真实PG/Worker/唯一SSR/Chrome新任务和双权威Brief仍待其Owner合并后执行。

P0未启动PG/Chrome/容器/服务，资源清理对象为空；外网/模型调用0，费用/人工时长UNKNOWN。旧匿名卷及历史RED/dump/A1/MAX3均未触碰。不是正式人审、客户批准、ShareGrant、E2/E3或生产部署。

当前结论仅 `C3_P0_ENGINEERING_READY_GOLD_PENDING` 与 `S2_QUALITY_NOT_EVALUABLE`，保持独立Draft PR供Owner审阅，不宣告 `S2_ENGINEERING_PASS_GOLD_PENDING` 或 `S2_FULL_QUALITY_PASS`。
