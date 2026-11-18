# 权限、视图和同意矩阵（R0候选）

所有“身份”输入须来自受信server adapter：JWT issuer/audience/expiry/revocation校验和持久授权仓库。HTTP body里的role、人身份或receipt_verified布尔值均不产生权限。R0的FixtureVerifier只使用公开合成种子生成的独立Ed25519测试key，不能充当这些真实适配器。

| 操作/视图 | 持有者/权威 | 必需条件 | 失败/撤销 |
| --- | --- | --- | --- |
| Availability | VF前台可消费最小能力信息 | 真实服务/Owner放行状态 | 当前NOT_AVAILABLE，不发送扫描请求 |
| 创建L1任务 | 已认证VF BFF SERVICE / Owner | tenant同源、opaque audit/request/source_ref、原body和header幂等key一致、当前源许可、签名同意引用 | 403/409/429；存储失败503无假202 |
| 原L2创建 | 独立受邀深度桥接 | 正式合法许可及R1生产适配 | 本候选fixture明确503，不能通过原L1采集 |
| 状态读取 | 同tenant且持有请求访问能力的BFF | 当前许可/任务关联/未撤回 | 不泄露他租户ID；403 |
| PublicPreviewView | 指定recipient，VF BFF代持会话 | 低敏有界投影、当前ReportVersion、真实人审、Owner批准view hash、有效收方grant/token | 默认不匿名；未审、旧版、过期、撤销403/409 |
| ApprovedL2ReportView | 受邀企业recipient | 上述全部、audit_mode=L2、真实ReviewDecision及Owner ShareGrant | Controlled不是正式人审；403/409 |
| 原EvidencePack、模型/浏览器原文 | 原内部角色和权限路径 | 原系统决定，不经默认公共view | 不通过跨仓公开投影提供 |
| ReviewDecision | 真实REVIEWER/Owner | 当前版本/hash与独立核实的人身份 | SERVICE或合成Reviewer不得正式签署 |
| ShareGrant | 真实Owner | 精确report版号/hash/view hash/收方/token hash/期限；当前持久撤销状态 | 重复相同请求幂等；同ID换body409；过期/撤销拒绝 |
| HANDOFF_REQUESTED | Owner或受信VRAE SERVICE | 主动咨询同意ref、当前授权audit和已知当前报告引用 | 不发送客户报告；不宣称VF保存 |
| VF_INQUIRY_RECORDED | VF storage service签名 | 实际保存与可对账存储receipt；tenant/audit/版本/请求hash一致 | VF失败/ACK丢失保留WAITING_ACK，重试不造新事实 |
| QUALIFIED_BY_HUMAN | 独立真实商业人员，Owner认可身份 | VF收据、询盘证据ref、人员确认签名 | VF服务自签/点击/发邮件均不合格 |
| 撤回/撤销 | 请求持有者经VF BFF或Owner | 当前主体/请求关联及撤回权限；具体协议G0确认 | 报告与旧下载链接关闭；迟到ACK不得复活 |

## 最小投影与token

默认公开投影只含：opaque tenant/audit/run/report/version、原内容hash、A/B中英文有界摘要、获准的短引用/URL/定位/时间、观察页数/授权页数及UNKNOWN。schema additionalProperties=false；无内部EvidencePack、原始DOM/模型输出、姓名/邮件/验证码/密钥。deny scan只能补充字段白名单，不能替代人工脱敏/权利审核。

原source/citation内容必须经过获准投影，而非直接截取内部原件。零采证保持UNKNOWN，整个站点分母为null，不能将授权3页写成已观察3页。受保护对象一律no-store/private；每次下载再次核对当前版本、源许可、token/subject/audience和撤销。不要给出绕过授权的永久对象URL；token不放URL、日志或前端持久存储。BFF会话/CSRF和具体token托管由VF Agent设计，安全约束由Owner冻结。

## 同意文本版本分离

| 用途 | 现状/候选版本 | 权限意义 |
| --- | --- | --- |
| VF咨询与联系隐私同意 | 当前源码VEYFRONT-PRIVACY-2026-10-30 | 联系资料保存在VF，不能顺带授权站点扫描 |
| 有界站点访问与诊断 | VF-SCAN-CONSENT-DRAFT-1（候选，不是已生效法律文本） | 记录scope/路径/目的/期限与文本hash；用户声明≠验证站点控制 |
| 浏览器执行/子资源 | 独立purpose、地区及Owner批准，当前未授予 | 不从普通URL同意推导 |
| 模型发送/地区/留存 | 独立purpose与地区/费用批准，当前未授予 | 默认NO_MODEL、真实Provider调用0 |
| Rebuild联系 | 独立VF contact consent ref | 只转咨询，不授权客户报告交付、报价、素材复用 |
| 删除与撤回 | Owner待定留存/删除流程 | 访问先关闭，删除完成需独立持久回执，不用点击冒充删除 |

VF保留客户信息与同意记录正文；VRAE只持opaque reference、版本和hash。不得把同意checkbox映射为genuine human review、legal ownership verified或客户批准。R0签名示例、ReviewDecision和ShareGrant对象均为合成消费方fixture，不是正式签署或现实授权。
