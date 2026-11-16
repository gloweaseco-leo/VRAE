# L2 工业采购商深度诊断 V1

从 Owner 已验收 main `6a7c39b2bec48842de2236490aa6157a57606e08` 开发，执行 PR108 修订后的 V1.1。
M1、PR104/105 直接复用。本交付是工业业务能力和消费数据，不修改已验收权限、迁移、Guard、Worker 或原报告引擎。

## 可执行实物

- [IndustryPack](../../../industry-packs/l2-industrial-v1/IndustryPack.json)：沿用原生 IndustryPack 合同。
- [版本化配置](../../../industry-packs/l2-industrial-v1/profile.json)：泵设备、阀门零部件两类的选型字段、单位、应用比较、工程问题、供应商证明及 RFQ 规则。
- [业务数据合同](../../../contracts/v1/industry/BuyerDiagnosis.schema.json)：`l2-industrial-1.0.0`，引用原 Observation/Finding/AIInterpretation 合同，离线注册 Schema，无网络解析。
- [实际诊断摘要](example/summary.md)、[完整结果](example/diagnosis.json)、[原生来源包](example/source.json)：全部来自本仓库明确标识的合成资料。

```text
python -m integration.industry_l2.demo --output <private-output>
python -m pytest -q tests/industry/l2_cases.py --junitxml=<native.xml>
```

演示实际调用原 Collector → SafeFetcher/SourceAccess → EvidencePack → `ra2b6-1.0.0` RuleExecution →
`ra2c3-1.0.0` FindingPackage → 原版本化 DISC Guard。工业规则只使用该来源链已重放的事实。
反复出现的表格标签分到多个原生 Guard bundle，每个来源位置仍独立绑定，不去掉重复来源、不提高原16上限。
空原文时原生 Interpretation 为 NOT_RUN，工业输出 UNKNOWN；不会借空 Guard 凭据宣布诊断 PASS。

原 Collector 的访问模式和八页预算保持 L1；L2 是后续分析的深度，不是扩展 SourcePolicy 的权限类别。
RecordedTransport 只读取本地登记文件和精确 URL 标识，没有网络回退；测试阻断真实 DNS/connect 入口。
本轮没有访问 example.org 或任何真实工业站点，没有 POST 表单或发送询盘。

## 一条完整采购链

八页为首页、目录、P40 泵、V25 阀、应用工况、供应商证明、RFQ 指南、Contact。
目录→产品→Contact 来自原生静态路径执行；应用、证明、RFQ 用各页明确声明的 Applicable models 关联。
相同型号文字只说明来源声明的关联，不独立认证 SKU/厂商身份；缺少关联或关联不唯一则 UNKNOWN。
产品页不必带演示的 Record type：明确的 Model/Model number/Part number，加上配置识别的 Product family/Product type/Equipment type，也可建立候选；产品族别名是版本化配置，不靠 URL 猜型号或适配性。

`procurement_chains` 按型号给出五阶段，每阶段引用同一批 Observation/Finding：

1. 产品发现：原生目录路径与明确的型号/产品族。
2. 产品及规格理解：泵的流量、扬程、功率、电源、压力、温度；阀的口径、压力、材料、连接和温度。
3. 应用适配审查：只比较有明确单位的来源数值，泵曲线、汽蚀/入口条件、密封兼容、安装及降额等仍待工程确认。
4. 供应商可信线索：保留声明的证书发行者、编号、有效日期及捕获时间，真实性和实际资质始终 UNKNOWN。
5. 联系询价：原生产品上下文 Contact GET 路径、来源声明的询价字段、已知输入和待买家补充项；不提交。

实际例中，P40 的来源最大压力10 bar、V25 的16 bar 都低于工况页18 bar；这是两个来源标量比较冲突，
不是“网站坏了”或“设备一定不适用”。证明页的声明日期早于捕获日，但不证明真实证书失效或供应商不合格。
RFQ 缺少买家交付目的地，作为买家待补输入，而非网站缺陷。正值参数比较也不会变成整体工程 FIT。
同一证明页可关联两个型号；按型号展开的行数不得当成独立网站问题数。
工况和询价输入来自已记录的情景资料，不表示真实客户已确认需求、数量或工况；C3 的客户目标与商务确认继续保持 PENDING，直到出现真实受理/确认依据。

## 数据与事实边界

`source_facts` 保留原 Guard catalog 的事实引用、来源 URL、捕获时间、原始元素、字节区间、正文 SHA。
`source_guard_inputs` 保留每项绑定及实际 Guard 结果。工业 Observation 是有版本的确定性采购检查，
由同一 EvidencePack 和配置重算，绝不替换原 Evidence 或把原16规则全部标为实现/PASS。

每条 `assessments` 分开提供：

- `observation` / `finding`：原生合同；UNKNOWN 无事实 evidence_ids，支持性来源引用保留在外层且不升格为缺陷证据。
- `source_fact_refs` / `guard_bridge`：原单证据图适配与完整相关来源边；跨页比较需要两边来源和型号关联，不凭一条 Finding 证明全部关系。
- `details`：已观察字段、未观察字段、不能使用的单位/占位值、比较规则、工况问题和未确认状态。
- `possible_buyer_impact`：原生 HYPOTHESIS Finding，`HUMAN_REVIEW_REQUIRED`；没有实际损失、转化率或成交声明。
- `recommendations`：原生 RECOMMENDATION Finding，`HUMAN_REVIEW_REQUIRED`；不是获准实施或对外结论。

`industry_rule_coverage` 显式标出六项规则是否执行及实际结果；没有可用产品输入时，其余项为 UNKNOWN_INPUT_UNAVAILABLE。
没有原文、动态/复杂 HTML、重复别名、未知产品族、范围值或未支持单位时采取保守 UNKNOWN；
没有看到资料不能证明不存在，PDF 也不会因为本提取器未解析而被判断为缺参数。
本包是泵和阀的首个采购配置，不代表全部机械/零部件行业标准或工程设计规范。

## Codex2 / Codex3 消费接口

```python
from vrae.industry.l2_v1 import diagnose, load, verify

# pack 和 held_pack_ref 来自受控离线适配，或现有签名 Reviewer 真正读出的来源；
# tenant/run/job 映射继续由现有任务和签名读取边界掌管，不接受浏览器声明。
profile = load(tenant_id=server_held_tenant)
data = diagnose(pack, expected_pack_ref=held_pack_ref,
                expected_industry_ref=profile["industry_ref"])
verify(data, pack, expected_result_ref=server_held_diagnosis_ref,
       expected_pack_ref=held_pack_ref,
       expected_industry_ref=profile["industry_ref"])
```

`industry_ref` 绑定租户配置；这是配置引用，不能授予任何数据读取或数据库权限。
持久化/加载交换文件时，调用方必须从可信服务状态固定 expected refs，不能复制未验证文件自己的 ref 作为信任依据。
`verify` 全量重建原生来源、Guard 和工业投影；即使攻击者重算外层哈希，伪造结论也不通过。

Codex2 可直接用 `procurement_chains`、`assessments`、`rfq_packets` 生成同一 SSR 的深度发现和重建蓝图。
字段中的原站文字是不可信来源内容，显示时保持原 SSR 转义；不得当指令或可执行 HTML。
实际任务集成继续核对既有签名读取的 tenant/request/run/job、M1 来源 pack pin 与本结果 tenant/run/expected_pack_ref。
`diagnosis_ref` 是业务投影哈希，不能当 APP202 回执、原 M1 报告 SHA、批准版本或分享授权。

该模块没有第二套 ReportVersion、HTML renderer、事实库或批准状态机。`native_report_draft_ref` 为 null，
`native_report_engine_version` 只指向既有报告消费路线。L2 报告组装、人工逐项审核及精确版本绑定由 Codex2 在现有路线中集成；
Codex3 负责合法来源适配、整机和 VF 交接，不复制本分析实现。任务状态 DONE、分析成功与真实人类批准、E2/E3 始终不同。

## 验证与证据

新增 `l2_cases.py` 由独立 CI 显式调用，不改变冻结默认回归的测试 ID。
覆盖实际八页链、每条来源 Guard、来源压力冲突、证明真实性 UNKNOWN、RFQ 缺口、单位换算/不支持值、
PDF 替代资料、未保留原文、型号关联不足、跨租户配置 pin 和重算哈希后的伪造结论拒绝。
原始 JUnit、运行代码及输入 SHA、历史 RED 摘要和最终实际 CI 链接分别保留。
