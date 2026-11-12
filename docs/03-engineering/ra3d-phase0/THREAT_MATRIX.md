# 威胁矩阵 P0.1

**24 项设计威胁，未执行攻击测试。** `D_*` 是拟议内部审计原因；右列使用已存在的 native 安全错误
作为兼容映射建议，不把新原因添加到冻结 ErrorCode schema。跨租户/无权限的公开错误不回显目标是否存在、
内容/hash/quote、对方租户或角色。HTTP/身份适配尚未实现。

| ID / 待验用例 | 攻击/故障与信任边界 | 必须阻断的精确原因（内部 / 现有兼容 code） | 防线与测试判定 |
| --- | --- | --- | --- |
| TH01 · A01–02 | 外租户 Reviewer 用合法登录及猜到的报告/decision id | D_TENANT_SCOPE / FORBIDDEN_TENANT | 鉴权后 scoped lookup 之前拒绝，不返回对方任何字节；同租户还需 assignment |
| TH02 · A03–04 | 伪造 actor/reviewer/Owner 字段；SERVICE/模型自称人 | D_HUMAN_REQUIRED 或 D_ACTOR_MISMATCH / FORBIDDEN_ROLE | 可信会话与真人主体，角色/任务来自服务端；报告创建者和姓名字段无权威 |
| TH03 · A05–06 | 审核旧 target，原生 hash 没变但全文/版本已变 | D_TARGET_STALE / REPORT_VERSION_STALE | CAS latest + Htarget + review_seq，不能只比较 H0 |
| TH04 · A07–08 | 同 report_id 换新 evidence pack 或 scope/policy/run/version | D_SOURCE_CHANGED / REPORT_VERSION_STALE；跨 tenant 优先 FORBIDDEN_TENANT | 原 pack/对象/引用/Guard 重放，合法更新也须新版重新审 |
| TH05 · A09–10 | 两个 Reviewer 同时 approve，或 approve 与退回竞态 | D_REVIEW_CONFLICT / INVALID_TRANSITION | 单 scoped transaction/CAS 首个胜出，无覆盖、无两个成功决定 |
| TH06 · A11–12 | 双击/重试同请求；换 key 重复批准 | D_COMMAND_CONFLICT / IDEMPOTENCY_CONFLICT；D_REVIEW_CLOSED / REVIEW_REQUIRED | 同 key 同载荷一回执，不同载荷冲突，不同 key 不能重开关闭轮次 |
| TH07 · A13–14 | 校验后替换 HTML/CSS、追加像素或改页脚 | D_ARTIFACT_TAMPER / REPORT_VERSION_STALE | 不可变对象 + 精确原字节 hash；不重新格式化后做等价比较 |
| TH08 · A15–16 | 改原 quote、href/byte range，保留 evidence_id 或伪造 Guard 状态 | D_SOURCE_INTEGRITY / EVIDENCE_REFERENCE_INVALID | 逐条完整 fact/binding/pointer 与原始对象字节重放；全局列表不是证明 |
| TH09 · A17–18 | 客户端回拨时钟、服务器 rollback、无时区或刚好到期 | D_CLOCK_UNTRUSTED / SOURCE_NOT_ALLOWED；到期 SHARE_EXPIRED | 服务端 aware UTC + 高水位，不使用浏览器钟；expires_at <= now 拒绝 |
| TH10 · A19–20 | 未审核即复制/打印/导出或只有批准就公开分享 | D_APPROVAL_REQUIRED / REPORT_NOT_APPROVED；D_SHARE_DISABLED / SOURCE_NOT_ALLOWED | 私有预览只给内部授权；外部读恒 no-go；缺 Owner grant/consent/runtime 不给字节 |
| TH11 · A21–22 | 批准后改字、改引用、升级模型/布局，或 latest 回拨复活 v1 | D_APPROVAL_STALE / REPORT_VERSION_STALE | 历史决策不删除；新版本单调，旧批准/授权当前失效；不能 mutable overwrite |
| TH12 · A23–24 | grant 已过期、撤销或 native 与侧车的状态不一致 | D_GRANT_INACTIVE / SHARE_EXPIRED | 当次读当前 revocation_seq、状态、expiry；无旧缓存/历史 URL 后门 |
| TH13 · A25–26 | quote/理由/修改建议中含 script、onerror、指令、恶意链接/bidi/超长 | D_UNTRUSTED_CONTENT / SOURCE_NOT_ALLOWED | 全文/原始引文转义；无远程资源、源页面导航；不执行页面指令，输入有界 |
| TH14 · A27–28 | durable decision 丢失，先写 approved projection 后 crash；outbox 重放 | D_AUDIT_INCOMPLETE / REPORT_NOT_APPROVED | 决策+侧车+投影+审计+outbox 原子提交；不能凭孤立绿标放行；消费者幂等 |
| TH15 · A29–30 | 页面打开后权限被撤销/认证过期/任务重新分配 | D_SESSION_INVALID / FORBIDDEN_ROLE | prepare 与 commit 都查当前授权，会话过期拒绝；不信旧前端允许按钮 |
| TH16 · A31–32 | 0 问题构造空 Finding 或把 acknowledgement 升格 APPROVE | D_COVERAGE_NOT_REPORT / REVIEW_REQUIRED | native=null，独立 ack，无 ReportVersion/正式 decision/grant；不制造问题 |
| TH17 · A33–34 | 真人“批准”后把 HUMAN 改成客观事实，或 override REJECTED | D_CLAIM_CEILING / REVIEW_REQUIRED | 原 Guard 不改；假设只是被接受的表达；机器 REJECTED 阻断并要求新稿 |
| TH18 · A35–36 | 假装 Fake 模型真人、缺失/伪造 prompt/model/rule 版本 | D_PROVENANCE_INVALID / MODEL_SCHEMA_INVALID | Htarget 绑定真实版本/原解释；null/NOT_RUN 诚实标记；真实模型缺版本不能审批 |
| TH19 · A37–38 | 偷来的 token/不同 subject、无 consent 或伪造 Owner issuance | D_SHARE_SUBJECT 或 D_OWNER_ISSUANCE / SOURCE_NOT_ALLOWED | 后续原 grant + Owner 侧车 + subject/token/consent/用途并验；当前分享仍恒禁用 |
| TH20 · A39–40 | CDN/本地缓存/raw-object id 绕过撤销或获取另一 HTML | D_ACCESS_BINDING / SOURCE_NOT_ALLOWED | RA4 才可开放且需 no-store、每次授权、不可猜对象；当前没有外部读实现 |
| TH21 · A41–42 | 伪造 decision id/hash/审计链，复制别人的历史批准 | D_DECISION_UNTRUSTED / REPORT_NOT_APPROVED | 可信仓库+认证写入+正确 target/actor/seq，SHA 不当身份签名；孤立文件不可信 |
| TH22 · A43–44 | REQUEST_CHANGES/REJECT 后直接调用 native approve，覆盖理由 | D_REVIEW_CLOSED / INVALID_TRANSITION | 外层轮次门禁不可省；重开需新版本，新稿全审；原 helper 不独自决定当前状态 |
| TH23 · A45–46 | 只通过原 H0/native schema 就绕过全文侧车；v1 POST 偷加字段 | D_FULL_BINDING_REQUIRED / REPORT_NOT_APPROVED；形状冲突 MODEL_SCHEMA_INVALID（仅拟议适配） | 不改 native schema，未来版本化运输；native/full 双绑定缺一不得正式批准 |
| TH24 · A47–48 | 网络超时误显示已批准，确认时切换版本或静默换 signer | D_CONFIRMATION_UNCERTAIN / REVIEW_REQUIRED；变版 REPORT_VERSION_STALE | 只认持久回执，锁定完整 target+身份，先查同幂等 key；未确认绝不绿标 |

### 残余边界

证据已一致不等于其商业解释真实；人仍可能误判。身份验证/点击来源也不能证明充分理解，
需要可审计责任、清晰限制与后续真实样本质量验收。有效撤销只能阻止后续访问，不能收回既得副本。
持久审计/事务/对象不可变/令牌保护依赖未来 RA4 的真实实现与故障测试，本包只指定要求。
静态概念图不能验证这些安全属性。Human Gold 0/26 不因本设计或合成演练改变。
