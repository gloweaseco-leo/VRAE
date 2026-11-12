# 设计决策、兼容性缺口与实施顺序

**P0.1 候选，等待 Owner 审阅，不代表生产 GO。**

| ID | 取舍/决定 | 原因与后续门禁 |
| --- | --- | --- |
| DD01 | 原 RA0 schema 和函数保持原义；完整审批使用独立侧车 | 原 content_hash 不覆盖文字/HTML；不能往 additionalProperties=false 的对象加字段或挪用 reason |
| DD02 | ReviewTarget 同时绑定 native、editorial、HTML、source/Guard、版本和 scope | 单个列表或 native hash 不能证明所见文字与被批准字节相同 |
| DD03 | 原 RA3C 草稿不改，审批投影另存 | 固定候选 loader 明确要求 private/NOT_APPROVED/unshareable；改 flags 后重哈希也不合法 |
| DD04 | 任何变化形成新版本，整份重新审核 | 包括页脚、布局、来源新包、规则/模型版本、时间/策略；旧回执是历史，不是新内容的权限 |
| DD05 | REQUEST_CHANGES 为应用状态，关闭本轮审核 | 原 enum 无该状态；原 helper 仍接受 REVIEW_REQUIRED，未来外层必须阻止绕过退回直接批准 |
| DD06 | 零问题仅内部 acknowledgement | 不造 finding，不借用正式 APPROVE，不伪造 null native 的 approved 状态；外发摘要未来另定合同 |
| DD07 | 假设的机器类型不因人审被升级 | 真实人可以接受某种表述，不能凭人审记录证明认证/SEO/损失或把 Guard REJECTED 洗成事实 |
| DD08 | Owner review 和 Owner share 分开记录 | 沿用原角色权限，允许 V1.1 同人兼任，但绝无角色身份暗示自动批准/外发 |
| DD09 | 一个 scoped report 的第一次有效 CAS 决策胜出 | 防并发批准/退回互相覆盖；重复同 key 返回同回执，不同 key 不产生第二份批准 |
| DD10 | 决策、全文侧车、投影、审计、outbox 原子提交 | 先写绿标后丢事件会制造无法追责的批准；没有持久性不能声称流程完成 |
| DD11 | 保留不可变原 HTML，未来改变对外水印也需新制品审核 | 不在 approved-copy/render 步骤悄悄更改被签署字节；当前合成草稿永不直接转成客户报告 |
| DD12 | share helper 不是 recipient 登录校验器 | 原 check_share 要求 Owner 角色；禁止伪造 Owner 上下文供客户读。外部读取独立合同/RA4 runtime 尚未授权 |
| DD13 | 当前 prompt/gateway provenance 缺失不凭空补全 | 固定 RA3C 只记录 null model 与限制，未来真实模型运行须完整版本来源；当前只作合成参考 |
| DD14 | 拒绝依赖浏览器时间和孤立 hash 判断有效 | 需服务端可信时间/高水位、当前权限/撤销/版本，读失败时不允许旧缓存继续授权 |

## 固定参考并不是永久 API

本分支 main 无 `vrae/reporting`。RA3C `6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2`
仅是未合并的功能候选；QA #48 的 64 项独立业务测试及 Owner 最终判断不在本设计中运行或认领。
后续合并后的模块、字段、loader 和 renderer 可能变化，须做显式适配审查。

### 必须先解决的实施缺口

1. **编辑输入**：固定候选仅接收 `editorial.PROPOSALS`，不能任意改写；需 Owner 再审
   新的版本化私有人工文字输入、重新 Guard/renderer 与完整 hash 方案，不能静默放宽。
2. **身份适配**：原 actor dict 是领域函数受信输入，不是已实现真人认证；未来服务端必须
   验证 human/session/assignment/tenant，并区别 SERVICE/WORKER/Fake，不用“勾选真人”代替。
3. **原生与侧车运输**：冻结 v1 POST 没有全内容侧车；未来版本化命令/审核会话适配和存储合同须评审。
   不新增有效端点、JWT 约定、DB migration 或原错误码于本轮。
4. **持久与原子性**：RA4 的 DB/对象存储/事务/鉴权尚未被本包实现；RA3D 的后续离线状态机
   可先验语义，不能冒充真实 durable commit、角色撤销或客户可用访问。
5. **客户读取和分享**：Owner grant 的规范是未来边界，不是当前开放入口；原 check_share 单独不够。
   需独立 RA4 接收人身份/subject/token/consent/撤销/缓存授权与端到端安全验收。
6. **审批失效/撤回**：任意新版立即使旧批准失去当前效力。发现旧批准存在安全疑问时，
   未来应记录 invalidation 事件、撤销 grant、创建新版本重新审核，不删除历史或复用旧批准。

## 授权后的建议实现顺序（本轮不执行）

| 后续包 | 可以验证的对象 | 仍不能宣称 |
| --- | --- | --- |
| D1 兼容性复核 | 实际已合并 RA3C、QA、schema/版本 pins；Owner 单独代码 GO | 本 Phase0 已授权代码 |
| D2 离线审核领域合同 | target/decision/ack、版本与并发语义、可信 actor 适配接口的合成验收 | 合成 actor 是实际人审，内存提交是持久提交 |
| D3 私有审核 UI/API 原型 | 证据与全 hash 展示、明确决策、未启用客户访问 | 已有生产认证/DB或可分享客户报告 |
| RA4 受保护运行时 | 真实身份、数据库事务、对象不可变、Owner grant/撤销、recipient 安全访问 | 未经实测的存储/权限/恢复保证 |
| RA5 授权商业样本 | 实际人审与有限客户同意、商务反馈 | 合成记录证明商业效果、自动 E2/E3 |

每包仍需独立范围授权、确切 main 和 PR/SHA 验收；本设计不能代替相应阶段 GO。
保留 Human Gold 0/26、MODEL_LIVE_NO_GO、CUSTOMER_SHARE_NO_GO，无实际费用/客户操作。
