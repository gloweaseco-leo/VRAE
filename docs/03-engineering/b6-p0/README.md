# B6-P0 私有交付预检

授权：[Owner CODE GO](https://github.com/gloweaseco-leo/VRAE/issues/80#issuecomment-6873766807)。独立入口为已验收 main `ae2505f74f7a81d7a563c05d1a811aaa526c2839`；没有从 PR83 或 PR89 分支复制实现。只新增指定 B6 路径；V1.1、v1 合同、原有模块、迁移、角色和 CI 保持不变。

本轮提供三个严格 v1 合同：`B6PrivateHandoffCandidate`、`B6VFIntendedEnvelope`、`B6PrivateDenialReceipt`。实际候选只由已验收 B2 签名会话和 B5A Reviewer 原文读取生成。DTO 中不复制原始 BYTEA/HTML、Guard、URL、联系人或凭据，只保留哈希、Guard 引用、精确引用区间和固定警示。404 是 1 项有证据支持的静态路径发现；200 为 0 发现和明确 UNKNOWN，不是已批准 L1。

`PrivateHandoffReader.verify` 必须在当前会话、assignment、policy 与实际 Reviewer SQL 权限下重新读取原文，逐字节比对完整候选和密封私有预览页。仅通过 JSON Schema 或重算摘要不能证明来源，更不能赋予分享权限。`Candidate` 的直接构造只校验格式和内容绑定，不能代替这个读取边界。

`DeliveryAuthorizationGate` 对所有真实 grant/token/收件人访问/公开链接/通知/发送/VF 操作无条件 DENY。`DenyOnlySink` 只保留有限内存拒绝回执；没有 sender callback、传输接口、持久 grant、数据库写入或真实 token。预期 VF 信封的 endpoint、recipient、consent、legal proof 和有效期全部为空；其未来查询/撤销/幂等描述不代表已运行的服务。

## 本地执行

使用 Python 3.11 和 3.13，安装已有 `requirements-ra1a.lock` 与 `requirements-ra4a-p2b2a.lock` 后分别执行：

```text
python -B -m integration.b6_p0.run local-311-unique
python -B -m integration.b6_p0.run local-313-unique
```

每个标签只能用一次。需要本地 Docker PG16。实验复用已验收 B5A PG 生命周期和 0001–0003；B6 的所有私有状态留在 `integration/b6_p0/.runtime/`，不修改旧实验目录、不增加 SQL 表或迁移。测试控制面持有一次性管理员/签名器，产品读取面仅持有已有 Reviewer 会话/连接。原始日志、失败 XML、token 和凭据保持忽略。公开证据只包含限定的成功 JUnit、摘要、指纹、清理记录、两个候选/预期信封和两张小型脱敏 HTML 页面。

完整本地矩阵通过后，推送前核对 Owner 已验收 main；若已前进，普通 merge 已验收 main 并重跑受影响本地门禁。仅一次显式路径提交/推送、一个 Draft PR 和首轮自然 CI；实际 jobs 数以 GitHub 为准。首轮结束即 STOP，不 rerun、不补推、不自行合并或部署，交 Owner 独立审查。

完整 B6、自然人审批、ShareGrant、收件人交付及 VF 外部写入均未解禁；Beta 仍为 2/7，G1/G2/G3 NO-GO。
