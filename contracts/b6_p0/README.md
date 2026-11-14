# B6-P0 v1 私有候选与预期交接合同

这些封闭 JSON Schema 不替换 `contracts/v1`，也不增加原 v1 ErrorCode。规范序列化使用 UTF-8、键排序、无空白、有限整数和无重复键；拒绝未知字段、浮点数、非有限值、过深或超长输入。所有 `$ref` 均为本地 `$defs`，不读取外部 schema。

候选始终是 `TEST_ONLY_PRIVATE_PREVIEW / NOT_APPROVED`，approval/share/delivery/external visibility 均为 false，native decision 与 real recipient 均为 null。L1 草稿候选最多 3 项支持充分的 Finding；coverage-only 不含 Finding 或 native content hash。每条引用只带 evidence/source/Guard 引用、字节区间及内容哈希，不带原文、联系人或 URL。原生 ReportVersion 的内容哈希仅通过已验收 `report_content_hash` 复核；它不是自然人身份或生效审批的证明。

字段分类由合同固定：完整 pins 与 recipient-policy descriptor 为 Reviewer-only；发现与 coverage 仍是 INTERNAL_PREVIEW_ONLY。`prospective_owner_fields` 只列未来可能的最小字段；`owner_visible_now=[]`。当前不能向任何外部 Owner 或客户交付候选本身。

VF 信封仅描述未来服务间的责任：VRAE 拥有证据/报告；VEYFRONT 拥有 lead/customer/E2/E3；不共享数据库。correlation/idempotency 由候选摘要和精确 report scope 确定。未来每次访问都必须向已授权服务检查到期、撤销、收件人、Owner 同意和法律依据；本轮 lookup endpoint/transport endpoint/recipient binding 均为 null，缺少证明始终 DENY。没有被实现的 VF API 路径，也没有域名、email、webhook、服务密钥或 token 兑换服务。

拒绝回执不是 grant/token/审批/outbox 事件，`is_token=false`。其 request SHA 是不可信输入的审计指纹，不回显任何输入内容。所有操作均在有界内存 sink 内记录 DENY/no-send，禁止传入外部 sender 或 callback。
