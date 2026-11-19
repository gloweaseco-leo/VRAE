# VRAE Issue153 本地 Windows 单份交接回执

**自控公网技术流程已验证；正式客户业务交付尚未批准。**

本轮完成真实公网 mTLS、两位受邀主体顺序采集、原 PG COMMIT、真实 Windows
账户密码 + 手机 TOTP、本人审核、定向报告读取、跨主体拒绝和 Owner 撤销。
没有采集真实客户网站。Reviewer 明确仅同意自控样例流程验收，保留 UNKNOWN；
客户报告业务价值与呈现质量仍需专项验收，并在实际获授权网站诊断后重新审核。
不能把本回执当作客户报告内容已获认可、Qwen 已可用或长期可用性的证明。

## 实际运行地址

| 用途 | 真实地址 | 传输 |
| --- | --- | --- |
| 诊断 API | https://dong.tail27555e.ts.net:443 | 原始 TCP Funnel → 127.0.0.1:28769 → API8769 |
| 正式报告协议 | https://dong.tail27555e.ts.net:8443 | 原始 TCP Funnel → 127.0.0.1:28770 → REVIEW8770 |

TLS 在 VRAE 终止；没有使用 HTTPS 终止隧道代替 mTLS。正确证书及其绑定
Bearer 均必需；错 Bearer/错证书 403，无证书 TLS 拒绝。调用方须在自己的服务器
保存凭据，不得将私钥/Bearer 放在浏览器包、日志、Issue 或聊天。

当前临时客户端证书、部署/网址签发委托及身份目录的运行窗口截至
**2026-11-20 10:30 UTC（纽约 05:30，北京 18:30）**，之后必须先续配权限/凭据，
不能因服务进程仍在或公网服务器证书尚有效而继续宣称可用。
公开服务器证书有效至 2027-02-17；它不延长上述权限。

## 精确版本及运行状态

- 最终运行源码：`be4ca8ef85706417d8c7d496d25609bc0a08fac1`。
- 最终镜像：`sha256:85d9ca064d9d297af8f02d4f05e346f0341ede168b064ce661bdc6fe0b8a070f`。
- 完整公网流程使用镜像对应源码 `589eb1d8cc4f08829e716bcb331108f1d87d6005`；
  后续最终版本将 TCP DNS 选择移入服务适配器，恢复原 resolver 字节，另做实际 DNS、
  完整回归、持久数据核对和外部健康验证。没有声称最终健康测试重做了人审。
- PG16、Worker=1、APP10001、REVIEW10007、AI10008、Worker65532 持续运行；
  PG 和正式报告 Ledger 位于持久卷，根密钥/手机种子在 ext4 私有卷 0700/0600。
- 最终运行后已再次读到两个原 PG artifact 哈希；两份正式 Ledger 文件存在。
  [最终运行/DNS/PG/AI回执](evidence/final-runtime-dns-pg-ai.json)、
  [冷备份与升级](evidence/final-deployment-and-cold-backup.json)、
  [持久Ledger文件哈希](evidence/persistent-approved-and-revoked-ledgers.json)。
- 最终镜像 67 项相关回归通过，`mypy vrae` 的 140 个源文件通过。
  原封不动的 B5A 源码冻结检查通过；没有修改其黄金基线。

## 接口契约

在线 `/v1/openapi.json`、`/v1/target-intake-contract` 和 `/health/ready`
使用 API mTLS/Bearer 与 `Accept: application/json`。
[实际部署契约与证书期限](evidence/deployed-openapi-and-intake-contract.json) 已保存。

诊断 POST 使用原媒体类型：
`application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"`。

1. `POST /v1/invitation-session`：单次邀请换 Secure/HttpOnly Cookie 和 CSRF。
2. `POST /v1/target-applications`：HTTPS网址、明确只读授权/模型数据告知及精确附加路径。
3. `POST /v1/target-applications/authorize`：实际域名 TXT 控制证明后由受限签发器
   创建原签名 SourcePlan/许可；自控站使用单独已签名的自控节点证明。
   根 SOURCE_ADMIN 私钥不进入 HTTP 调用方；不伪造客户网站法律证明。
4. `POST /v1/diagnoses`：原 202 队列；同意图幂等 202，改变同键内容 409。
5. `GET /v1/audits/{audit_ref}`：当前受邀主体读取任务状态。
   历史 `GET /v1/audits/{audit_ref}/report` 仍为 403。

正常域名须真实证明和明确许可；不能把 URL 直接当合法 SourcePlan。
私有IP、元数据IP、非HTTPS、缺失许可均在真实公网调用中拒绝。
Worker=1、原租约30秒、有界排队，不将客户数量写死为1或2。

正式报告使用 REVIEW mTLS/Bearer、
`application/vnd.vrae.report+json; profile="vrae.report-authority.v1"` 和
`X-Report-Profile: VERIFIED_HUMAN_CUSTOMER_REPORT`。
Reviewer 使用原 challenge/session/actions/decisions；Owner 仅签发定向 grant。
收件人不需要 Windows 身份或 Authenticator：

- `POST /v1/report-authority/recipient-session`，精确字段为
  `audit_ref, task_cookie, task_csrf, grant_id, grant_token`；
  返回仅 READER 的短会话，不赋予 Owner/Reviewer 身份。
- `GET /v1/report-authority/audits/{audit_ref}/report`，携带
  `X-Report-Session`、`X-Report-Grant`、`X-Report-Token`。
- 仅实际审核及有效定向授权成立时，外层 envelope 的
  `formal_human_review`/`external_release` 才为 true。内层原始 Native 文档保持
  生产时的未批准字段，不通过改写来源内容冒充真人审核。
- Owner 用原 `actions`/`revocations` 撤销；版本、当前邀请、来源、角色及期限均重新校验。

## 两位主体真实回执

来源为已获许可的 `https://vrae-owned-source.tail27555e.ts.net/`，是自控样例，
不是客户、真实供应商资质或工程认证。

| 主体 | audit_ref | 原任务 job_id | 实际结果 |
| --- | --- | --- | --- |
| acceptance-a | aref-5d84e6ff0bc148869dc06f59f4dd9c9f | 6e9a5f42-4ac6-40fe-9d58-c14f5263e00c | 3页、7条来源事实、11项评估、3项蓝图；约19.7秒 COMMIT |
| acceptance-b | aref-3316cad50f294091beaa69f9b63ac651 | d903187e-7ae9-470e-8bb0-bff66646cfca | 3页、7条来源事实、11项评估、3项蓝图；约18.4秒 COMMIT |

11项评估均保留 UNKNOWN；真实来源声明不等于已获独立业务/工程确认。
[完整原提交、证据包及重放结果](evidence/committed-drafts-before-human-review.json)
是审核前快照，里面的 `report_approved:false` 不能被改写成后来的审核记录。
后续审核见[真人审核及定向授权](evidence/actual-human-review-and-directed-grants.json)，
撤销见[真实 Owner 撤销](evidence/actual-owner-revocations.json)。

公网外部 GitHub Ubuntu 调用证据分别保存，避免把健康当成全流程：

- [真实顺序采集](evidence/14540354650-capture.json)。
- [正式报告读取/版本一致/跨主体及 Reader 越权拒绝](evidence/14545475470-formal-report.json)。
- [撤销后的真实拒绝与仍有效任务身份](evidence/14546026171-formal-report.json)。
- [最终运行版本的公网mTLS健康](evidence/14546318728-final-public-health.json)，
  对应 [外部运行44560092062](https://github.com/gloweaseco-leo/VRAE/actions/runs/44560092062)。

撤销判据还包括原 Owner API 在15:30、grant尚未自然到期时记录 REVOKED。
外部撤销检查窗口为15:34:18–15:34:41，来源授权当时未过期、任务会话仍有效。
该回执未导出逐请求时钟，Alpha自然到期34:37落在窗口末4秒；**不单凭其403
独立区分到期与撤销**。旧Reader会话也有自身5分钟期限。
[时序证据界限](evidence/external-revocation-window.json) 保留，不刷绿或隐藏。
两份样例 grant 当前均已撤销，样例来源许可已于15:35过期；禁止用旧许可继续扫描或交付。

## 安全、AI及操作

[实际逐UID拒绝](evidence/uid-boundaries-during-authorized-capture.json) 包含根签名密钥、
Docker socket、内部API、元数据IP及未授权公网目的地。只有原 Worker 在许可有效时能到
自控来源443，所有服务 CapEff=0/NoNewPrivs=1。最终版本实际TCP DNS完整验证A+AAAA，
过期来源已从允许出网目的地移除；不是关闭隔离后才让采集成功。

两任务 PG AI 回执均为 `AI_UNAVAILABLE`，`model_fee_go=NOT_GRANTED`、Provider=None、
实际 provider_attempts=0、invoice=UNKNOWN。C1 Adapter代码存在不等于真实Qwen4调用获准；
本轮不声称真实模型成功或账单为零，后续费用/密钥/Provider须单独实际联调。

从实际 Windows 用户、该API工作树操作。受信本机操作器含Docker CLI：
`sha256:c279621ceb9977c58524f830a0a67692f0f75c7b582efb0276e2975cc9f025f4`。

```powershell
$op = 'sha256:c279621ceb9977c58524f830a0a67692f0f75c7b582efb0276e2975cc9f025f4'
python -B -m infra.windows_service.private_host status --image $op --name vrae-windows
python -B -m infra.windows_service.private_host up --image $op --name vrae-windows
python -B -m infra.windows_service.private_host stop --image $op --name vrae-windows
python -B -m infra.windows_service.private_host restart --image $op --name vrae-windows
```

根凭据位置为 Docker Desktop ext4 `vrae-windows-private`，0700/0600；`caller.json`
引用实际mTLS文件及绑定Bearer。仅通过经批准的私有服务器渠道交接证书/密钥/邀请，
不得复制到NTFS共享、前端、公共附件或聊天。备份在独立私有 `vrae-windows-backups` 卷。
原 control 的备份/回滚保留，恢复应使用新空卷，不覆盖现有卷。
完整本地流程与错误码约束见 [OPERATIONS](../../../infra/windows_service/OPERATIONS.md)。

Docker Desktop已配置当前用户登录启动，容器`unless-stopped`；本机临时保持唤醒进程及
当前用户`VRAE-TemporaryWake.lnk`截至同一临时授权窗口，退出进程即释放，不改电源计划。
电脑开机且用户登录、Docker/Tailscale/网络正常是条件；手动休眠/关机/退出Docker/断网
会中断服务，不承诺云高可用。VPN v2rayN/xray、原127.0.0.1:10809代理及原始TCP
Funnel读回见 [网络回执](evidence/windows-network-readback.json)。没有修改全局代理、DNS或路由。

发生无证/错证/Bearer错误或历史报告403，不降级HTTP；Cookie过期用原一次性返回协议，
不篡改数据库复活会话。采集失败/UNKNOWN不当成完整诊断。实际遇到并保留了DNS失败、
来源TLS阻塞、重复UNKNOWN ID、浏览器Origin:null、断线等证据，针对原因修复。
[真实Chrome空表单回归](evidence/real-chrome-form-regression.json)证明Forbidden修复，
不伪称该空表单测试产生过真人批准。原运行中的成功/失败均保留。

VPS以后迁移：先冷备份PG和Ledger，经私有渠道迁移root私有材料；在目标宿主重新核验
原UID/namespace/DNS/防火墙、实际FQDN证书与SNI/Host；重新验证身份发行和MFA链，
不能复制本机密码验证元数据冒充VPS本地身份。再做外部实际读/撤销和新网站授权验收。
本轮没有等待VPS，也没有修改VEYFRONT仓库、Vercel配置、域名或上线安排。
