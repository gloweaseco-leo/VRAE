# L2 消费与同工作台集成

## 来源与版本

`vrae.l2.report.OfflineSource` 消费 `vrae.l2.deep-result.v1`，由服务端独立持有目录和原始 result 文件 SHA256：

`0734221083be47b3e91bbb8e3bb3c790af2577c1b2a922e509eba85c486768b7`

每次读取重放页面字节、哈希、引用边界及原始引文，禁止客户端替换来源。该生产保证名为 `OFFLINE_AUTHORED_SOURCE_BOUND_NOT_NATIVE_GUARD`，不等于 Codex1 原生 Guard。复用 V1 IndustryPack、Finding、ReportVersion、ReviewDecision、ShareGrant 及原 `report_content_hash` / `approve_version` / `check_share`。另绑定完整展示哈希，覆盖采购任务、优先级、蓝图和背景；不能用仅 Findings 哈希允许调换建议。修订只允许改造建议，证据事实不能改写。

## Codex1 PR110 对接

协同记录见 [Issue94](https://github.com/gloweaseco-leo/VRAE/issues/94#issuecomment-6907739497)。消费契约固定于 Codex1 PR110 提交 `e661926628250cfaff84798b8dbbb716b39fe5fc`：原 `contracts/v1/industry/BuyerDiagnosis.schema.json` 的只读快照保存在 `contracts/l2_consumer/`；实际离线示例及来源记录在 `fixtures/l2/codex1-contract-v1/`。未导入或运行未合并的 Codex1 代码。

`vrae.l2.codex1.inspect_export(raw, held)` 使用本地封闭 schema 注册表和独立保留的 tenant/run/industry/pack/diagnosis 引用及原始文件 SHA。结果明确 `OFFLINE_CONTRACT_INSPECTED_NOT_NATIVE_REPLAYED`，只能做契约分析，不产生 ReportVersion、APP202、任务分配、批准或分享。测试使用真实上游导出，不伪造 Guard 成功：81 条 literal source facts、19 项分析，不等于 81 个独立问题；工程适配 UNKNOWN、影响及建议 HUMAN_REVIEW_REQUIRED 原样保留。

上游合并验收后，原生消费必须调用其真实 API：

```python
from vrae.industry.l2_v1 import load, verify
profile = load(tenant_id=server_held_tenant)
verify(data, pack,
       expected_result_ref=server_held_diagnosis_ref,
       expected_pack_ref=server_held_pack_ref,
       expected_industry_ref=profile['industry_ref'])
```

必须完整重算来源、原生执行、Guard 和配置。不能将 JSON Schema 成功、自算 envelope hash 或 `diagnosis_ref` 冒充 M1 report SHA。实际任务还须复用现有签名读边界独立持有 tenant/request/run/job/当前 source pack；离线示例没有这些任务分配，不填假 UUID。工业深度分析不扩大 SourcePolicy 页数/采集权限。

业务映射：procurement_chains→采购任务；assessments/observation/finding→观察及解释；source_facts/source_guard_inputs→证据及原始 Guard 详情；rfq_packets→询价准备与买方待补资料；coverage/limitations→覆盖及 UNKNOWN。源声明型号不等于独立 SKU 验真，参数标量比较不等于工程适配，声明证书日期不等于真实资质失效，买方未填目的地不是网站故障。所有影响/建议先待人审，语义批准不会自动继承。

## 同一服务的私有装配

原 `integration.b5b.m2_bridge` 的可信 STDIN 配置可选 `deep`，或原 HTTP launcher 提供 `--deep-profile`。均装配同一个 B5B Application：

```json
{
  "version": "L2_PRIVATE_PROFILE_1",
  "directory": {
    "issuer": "https://controlled-issuer.invalid",
    "audience": "vrae-l2-review",
    "jwks": {"keys": []},
    "people": [],
    "expires": 0,
    "mode": "CONTROLLED"
  },
  "sources": [{"root": "PRIVATE_IMMUTABLE_SOURCE_DIR", "bundle_sha256": "SERVER_HELD_PIN"}],
  "ledger": "PRIVATE_LOCAL_SQLITE_PATH"
}
```

这是结构说明，空 keys/people 和过期时间不会被当成可用身份。真实值来自受信部署者，目录只能放公钥；不支持上传身份目录或让浏览器指定租户、角色、责任人。不存在新 APP 数据库凭据入口或新 Worker 结果接口。Codex3 可在双方实现通过 Owner 验收合并后装配此字段，未合并前不复制兄弟实现。

CONTROLLED 始终不正式；VERIFIED_DIRECTORY 要求独立核验主体和 MFA，仍不启用外部客户分享。本轮实际验证只使用受控虚构主体、离线私库，不能据此宣称正式身份/生产 PG/原生 Worker 已完成。定向访问与审核都绑定确切来源及版本，新版本须重新决定。报告事实、改造建议、版本化审核和 RebuildBrief 授权是不同业务边界。
