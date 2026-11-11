# RA-2A EvidencePack 实现与验收

执行依据：[Issue #7](https://github.com/gloweaseco-leo/VRAE/issues/7)，Owner明确授权RA-2A。
起始main重新fetch核对为`f70ecffc2465807f34cb82d84f663508fe6db465`，
与Owner基线一致；它与已验收RA-1B实现的文件差异为空，仅新增合并提交。
独立分支`feat/ra2a-evidence-pack`；不合并、不部署、不进入RA-2B/2C/2D。
本轮按DEVELOPMENT_MASTER_PLAN_V1.1的RA-2A定义执行，旧路线图中更粗粒度的
RA-2A标签不扩大本轮范围。沿用ADR-0001/0002、数据架构与证据方法论。

## 实现

新增`contracts/v1/evidence/EvidencePack.schema.json`和`vrae/evidence`。
HTTP及Browser来源先复制并执行原`CaptureBundle.verify`/`BrowserBundle.verify`；
包保存原清单的完整内容、原hash字段、schema_version和整个清单的SHA256。
来源对象以内容哈希复用，不改写原source对象键，默认私有且仅在内存保存。
未改RA-0契约、领域Evidence约束、RA-1A或RA-1B代码、依赖及安全CI。

来源、快照和EvidencePack引用都绑定精确tenant/run/policy/version。
原HTTP snapshot/evidence ID原样保存；浏览器源本来没有这两类ID，保留null，
明确标识独立派生的snapshot_ref/evidence_ref，绝不冒充已有PageSnapshot身份。
source_ref绑定完整源清单；locator为指向原source记录的精确JSON pointer。
HTTP额外限制原定位符只能是生产者实际使用的`http-response-body`；
Browser OBSERVED额外检查DOM URL/基本容器形状、PNG头/视口尺寸与既有大小上限。
该适配验证不等于完整PNG解码、视觉真实性或自然语言支持验证。

`EvidencePack.verify`不是只比较外层hash：它重新执行来源校验，
重算源/对象hash，重建所有快照、证据、覆盖和限制字段，比较整个规范投影。
外层重新签算不能隐藏丢源、错ID、错hash、错locator、跨scope、覆盖伪造或旧引用。
同源重复输入、同mode/URL/viewport的不同版本、跨源重复原ID都拒绝。
相同输入的来源顺序不影响结果；来源清单本身的顺序是版本的一部分。
源/时间/版本改变会生成新引用，旧包及旧引用不变；消费引用必须钉住可信的expected_pack_ref。

冻结dataclass保存不可变bytes和tuple；原始输入深复制，document返回独立副本，
objects为只读映射且内容为bytes。无DB/对象存储、覆写接口或持久化承诺；
不防御已经能反射篡改Python进程的攻击者。限制为16来源、8MB清单、512对象/64MB。

## 状态和局限

- OBSERVED仅为有界采集观察；原文未保存时标明NOT_RECOMPUTABLE及RAW_BODY_NOT_RETAINED，
  resolve只返回元数据和content=null，不能重算远端原文或推断链接/文案。
- UNKNOWN保留未完成尝试、未核实页面角色。没有发现某类链接不表示该业务内容不存在。
- ACCESS_BLOCKED保留robots、403/WAF等拒绝；受阻和未知Browser工件可供私有审计，
  但resolve拒绝将其作为已观察证据返回。
- NOT_VISITED只用于已知inventory URL或批准viewport没有对应观察；不凭空编造未访问URL。
- NOT_APPLICABLE显式保留但本版拒绝生成/接收：本轮没有适用性判定来源，
  因而不存在可以诚实使用该状态的依据。未来支持需要独立版本化依据契约，不能用缺数据充当依据。

integrity=VERIFIED仅指来源及引用一致性；每份内容另区分HASH_VERIFIED与NOT_RECOMPUTABLE。
SHA256不是远端来源签名，不能辨别一个从头一致伪造且重新生成新ref的来源，
也不能证明远端事实、实际渲染、当前许可或页面商业完整性。可信预期ref必须由调用方持有；
不能从待验包自己取出ref便称外部认证。Policy身份/版本绑定不代表重新授权。
URL路径、源清单、DOM、截图可能含PII，全部默认私有；仓库和CI只有明确合成数据。
不生成Observation规则结果、Finding、报告、销售事件或模型请求。

## 先失败后修复和重放

原始[缺模块红灯](ra2a-red.log)：exit2，属于测试收集失败，不计安全断言通过。
加入基础来源转换后，[定位符红灯](ra2a-red-locator.log)：1失败/29通过/exit1，
证明仅复用旧verifier不足以约束新的精确引用。补充HTTP定位符适配后同一断言通过，
未修改旧源verifier或降低负例。独立复核又补充HTTP mode不符和未经验证excerpt拒绝，
最终47项专项涵盖HTTP/Browser/联合正例、source重封装、
缺失引用、跨scope、旧新版本、错误hash/locator、duplicate、coverage篡改、缺原文、
不完整Browser、robots/403/WAF、DOM跨页和PNG视口错配，以及冻结接口。

可独立重放样本：[combined.json](../../tests/fixtures/evidence/combined.json)，
含原source清单、base64对象和固定expected_pack_ref。
其Browser PNG/DOM为离线构造，不冒称真实Chromium输出；原真实Chromium安全CI保留。

```sh
python scripts/verify_ra2a.py
python -m pytest -q tests/evidence
python scripts/verify_ra1a.py <output-directory>
```

本地Python3.11.15/3.13.13初轮各470通过/0失败/25环境限定跳过，
compileall/Ruff/mypy/pip check全部exit0，类型检查32源文件。
最后补充“内容是否可重算”字段后的final-python311/313结果另存；复核补齐两个来源负例后，
以acceptance311/313完整五门禁日志与源码hash为最终本地结果（各472通过/0失败/25跳过）。
25跳过为24个真实HTTP隔离测试和1个真实Browser函数，不计普通单测通过；
它们在专用Linux CI中分别执行，Browser仍按16场景独立汇报。
工具与精确命令见[证据目录](ra2a-evidence/README.md)。

本文件提交时不提前声明托管PASS。最终SHA的Python3.11、3.13、isolated-http、
isolated-browser必须全部实际成功；run/job和四份真实日志在新Draft PR补齐，
避免为补记结果循环产生提交。满足后结论为RA-2A PASS（仅离线合成证据工程范围），
否则如实PARTIAL/BLOCKED。等待Owner验收，保持Draft。

独立于编写过程的复核覆盖：来源哈希边、跨scope隔离、对象映射、时间/状态/locator、
重新封装反例、冻结接口和缺原文限制。这里不冒称外部第三方审计。
无新增框架/依赖/服务/数据库、采集器重写、网络例外、生产能力或后续规则范围。
无模型费用或服务采购；既有机器/托管CI账单未知，不记为零。
