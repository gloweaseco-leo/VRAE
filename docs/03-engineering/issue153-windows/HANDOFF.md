# VRAE Issue153 本地 Windows 单份交接回执

**Owner 已批准正式客户交付、AI 费用及凭证/委托至北京时间 2026-11-30 23:59:59。**

已实际续期客户端 CA/叶证书、部署/网址签发委托、原身份目录及四个原角色的期限；
保留原密钥、手机配对、角色 epoch 和历史撤销。没有恢复过期的旧来源许可或邀请。
本轮真实公网全流程、人审和定向读取的历史证据仍保留；没有采集真实客户网站。
Owner 本次业务交付授权已成立，每个新网站仍需合法来源授权，每份新报告仍需实际审核。
历史样例的 Reviewer 意见仅批准自控验收，不能改写成对新客户报告的审核。

历史真实 Qwen4-Max 已接通（当前按最新诊断联调指令暂停本实例供应商出网）：两位受邀主体各调用一次；一份产生待人审候选，另一份被
引用锚点校验拒绝（AI_UNAVAILABLE），不重试、不降低 Guard。费用估算合计 ¥0.05121，
正式账单 UNKNOWN；继续使用原有每日 ¥5 的同一共享账本。
[授权与续期](evidence/nov30-authority-renewal.json)、
[两次真实调用及共享额度](evidence/approved-real-qwen-receipts.json)。

## 实际运行地址

| 用途 | 真实地址 | 传输 |
| --- | --- | --- |
| 诊断 API | https://dong.tail27555e.ts.net:443 | 原始 TCP Funnel → 127.0.0.1:28769 → API8769 |
| 正式报告协议 | https://dong.tail27555e.ts.net:8443 | 原始 TCP Funnel → 127.0.0.1:28770 → REVIEW8770 |

TLS 在 VRAE 终止；没有使用 HTTPS 终止隧道代替 mTLS。正确证书及其绑定
Bearer 均必需；错 Bearer/错证书 403，无证书 TLS 拒绝。调用方须在自己的服务器
保存凭据，不得将私钥/Bearer 放在浏览器包、日志、Issue 或聊天。

当前客户端证书、部署/网址签发委托、身份目录及独立模型费用许可均截至
**2026-11-30 15:59:59 UTC（纽约 10:59:59，北京 23:59:59）**。
到期后须重新授权并续期；公网服务器证书有效至 2027-02-17，不延长上述权限。
[当前部署契约与证书期限](evidence/nov30-deployed-openapi-and-intake-contract.json)。

## 精确版本及运行状态

- 最终运行源码：`c456312aec1f54a2a6c89e42f3bce990a0081109`。
- 最终镜像：`sha256:be2711e41bfbdf00708dc9555c5391919645f52866494a155a0595f1cd1a242b`。
- 完整公网流程使用镜像对应源码 `589eb1d8cc4f08829e716bcb331108f1d87d6005`；
  后续最终版本将 TCP DNS 选择移入服务适配器，恢复原 resolver 字节，另做实际 DNS、
  完整回归、持久数据核对和外部健康验证。没有声称最终健康测试重做了人审。
- PG16、Worker=1、APP10001、REVIEW10007、AI10008、Worker65532 持续运行；
  PG 和正式报告 Ledger 位于持久卷，根密钥/手机种子在 ext4 私有卷 0700/0600。
- 最终运行后已再次读到两个原 PG artifact 哈希；两份正式 Ledger 文件存在。
  [最终运行/DNS/PG/AI回执](evidence/final-runtime-dns-pg-ai.json)、
  [冷备份与升级](evidence/final-deployment-and-cold-backup.json)、
  [持久Ledger文件哈希](evidence/persistent-approved-and-revoked-ledgers.json)。
- 当前镜像 93 项 Windows/运维/模型许可/服务身份回归通过；核心140文件类型检查此前通过，本次未修改核心。
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

历史两份已人审样例的 AI 回执保持 AI_UNAVAILABLE/0 次调用，不改写历史。
本次新来源 V4、两份新任务的真实调用见上方独立回执：

| 主体 | job_id | 真实模型结果 |
| --- | --- | --- |
| acceptance-a | 9322ab70-99cd-4d2b-95f1-bdc7b426fc7a | 1次，GUARD_ANCHOR_REQUIRED，0候选 |
| acceptance-b | 54741a19-b65a-4204-b2c7-45ca1339cd70 | 1次，AI_CANDIDATES_FOR_HUMAN_REVIEW，1候选 |

新来源明确为自控公网站，产品表补充了实际 `Record type: Product`，没有增加未知参数、
资质或供应商真实性声明。[公开站部署](evidence/owned-public-product-record-type.json)。
来源许可到期时间是独立短窗口，见[本次新来源许可](evidence/fresh-owned-ai-source-scope.json)，
不随全局 Nov30 授权自动延长。Beta 联系页超时保留 UNKNOWN。
旧 V1 模型数据告知不产生真实模型同意；网址申请 V2 `VRAE-READONLY-AI-DIAGNOSIS-2`
须明确同意北京区域、最小化类型证据、不含原始HTML/PII，并绑定当前邀请与签名计划哈希。
原 SourceIntent 的 `model_fee_go=NOT_GRANTED` 保持不变；独立签名费用许可才授权隔离
AI10008 的供应商出网，不扩展 Worker 网络权限。

共享额度卷是 `vrae-local-ledger` 的 `qwen` 子目录。修复了错误挂载父目录导致的权限失败；
没有 chmod、复制或重置其他实例的账本，没有重启其他实例。原7笔记录保留，新增2笔；
3笔历史用量未知的预留仍占额，当前UTC日可用额度见实际回执。无供应商自动重试。
[本次冷备份与升级](evidence/approved-ai-deployment-and-backup.json)。

从实际 Windows 用户、该API工作树操作。受信本机操作器含Docker CLI：
`sha256:eb717a1af90b4736afb22635638224fafae93a0918836a57b9199547795210c6`。

```powershell
$op = 'sha256:eb717a1af90b4736afb22635638224fafae93a0918836a57b9199547795210c6'
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


## 历史交接读回（业务批准之前）

2026-11-19 23:12 UTC 的当前用户网络读回确认 Tailscale在线、原始443/8443转发、
v2rayN/xray及原代理仍正常。之后的
[外部运行44635592022](https://github.com/gloweaseco-leo/VRAE/actions/runs/44635592022)
再次验证最终be4ca8e版本两个公网端口均200，错证/错Bearer403、无证TLS拒绝；
[当前外部健康回执](evidence/14581439902-handoff-current-public-health.json)已持久保存。
服务没有在验收后停止。仅供本轮外部验收的 GitHub Actions secret
`VRAE_WINDOWS_PUBLIC_MTLS` 已删除；服务自己的凭据仍在原受保护私有卷。
后续显式实测须重新通过安全运营渠道提供当前有效客户端配置。


## Nov30 授权后的真实公网与运行读回

[外部运行44641002837](https://github.com/gloweaseco-leo/VRAE/actions/runs/44641002837)
使用续期后的真实客户端证书，通过两个公网端口及所有无证/错证/错Bearer拒绝检查，
随后两位受邀主体顺序完成新来源采集、幂等、跨主体403及历史报告403。
[外部mTLS](evidence/14585963762-renewed-public-mtls.json)、
[新来源采集](evidence/14585963762-ai-source-capture.json)。该运行部署源码是74c1def，
之后的共享账本修复部署是adb37f2；不把前者写成后者的外部测试。
`mode=ai` 的工作流只验证真实采集，模型成功判据来自独立PG回执和供应商用量。
新候选尚未人审，不宣称它已成为正式报告；历史实际人审/读取/撤销证据保持原版本。

当前用户进程唤醒请求和登录快捷方式已延长到Nov30同一截止时间；停止它使用
`windows-power-guard-nov30.stop` 或结束回执中的PID。没有更改电源计划。
[唤醒回执](evidence/nov30-process-wake-guard.json)。


2026-11-20 00:06 UTC [当前网络读回](evidence/nov30-windows-network-readback.json)
确认 VPN v2rayN/xray、原127.0.0.1:10809代理、Tailscale在线及443/8443原始TCP转发均正常；
PG/runtime/隔离AI/relay/source均持续运行。当前镜像70项相关回归和140个核心源文件类型检查通过，
原B5A源码冻结检查通过。[检查回执](evidence/nov30-runtime-checks.json)。

最终adb37f2镜像的本地mTLS/契约与真实模型PG回执均已核对。自动审批拒绝重新将客户端私钥、
Bearer和邀请凭证写入GitHub临时Secret，要求明确目的地授权；已停止此上传并删除旧临时Secret。
因此最终镜像的新外部复验待该授权；不能用74c1def的外部回执声称已验证adb37f2外部全流程。
正式模型密钥、身份签名密钥、手机种子始终未上传。


## 最新 Owner 执行：Preview 专用身份已私有交付，部署由 VF 团队执行

已执行 [Owner #7026419809](https://github.com/gloweaseco-leo/VRAE/pull/172#issuecomment-7026419809)
及随后聊天中对 V5 切换和私有目的地的明确授权。**VF_PREVIEW_CREDENTIALS_DELIVERED**，
尚未声称 VF_PREVIEW_E2E_PASS。[实际执行回执](evidence/vf-preview-final-backend-receipt.json)。

实际运行源码 `c456312aec1f54a2a6c89e42f3bce990a0081109`；镜像
`sha256:be2711e41bfbdf00708dc9555c5391919645f52866494a155a0595f1cd1a242b`。
新增独立 `vf_preview_20261120a` APP actor/LOGIN role，仅继承原 `target_v1_app`；
不对已有 tenant 重跑全量 install。原四角色、epoch=1、Nov30期限均保持不变。
审查PR174 `bd2c217` 暂存脚本后在原ext4卷执行，输出展平为root私有文件以兼容原控制器，
没有把秘密落到NTFS或仓库。CA链为真实服务器的ISRG Root X1，非客户端签发CA。

专用证书SHA256为 `911c4e26ececdb0c5171cd1ed474e8ba79ab54aef7664217cf6661bf28157a96`。
**该Preview证书/角色/新邀请仅至 2026-11-20 01:39:55 UTC（北京时间09:39:55）**，
不等于全局Nov30授权窗口。邀请未消费、target_ids为空，不替测试者同意或授权网站。
原业务身份和新身份ready均200，新身份OpenAPI200；新证+旧Bearer、旧证+新Bearer、
错证及错Bearer均403，无证TLS拒绝。
[本机实际mTLS正反检查](evidence/vf-preview-identity-checks.json)，不是Vercel出站证明。

接收账号 `gloweaseco-1757`、团队 `gloweaseco-1757s-projects`、项目 `veyfront`
已实际核对。五项 `VRAE_DIAGNOSIS_*` 配置及 `VRAE_PREVIEW_INVITATION` 已由该账号
直接写入 `Preview / feature/vf-b-offline-g1-adapter`，六项均核对为Sensitive。
仅经内存/标准输入到获准目的地，没有GitHub/聊天/公开文件/Production中转。
[私有接收回执](evidence/vf-preview-vercel-private-delivery.json) 是认证写入和精确分支元数据确认，
不冒称VF人员另行人工确认。邀请码在实际消费后须从该Preview变量删除；当前尚未消费。

用户明确批准旧V4来源授权失效后，锁定并确认无活动采集，切换为无模型处理的V5。
为匹配VF真实 `paths:[]`，在V5尚无任务时仅收窄至 `/robots.txt`、`/`；没有加入其他站点。
来源原到期仍为 **2026-11-20 01:42:19.648899 UTC（北京时间09:42:19）**，不自动延期。
[V5切换](evidence/vf-preview-authorized-v5-scope.json)、
[V1精确路径兼容](evidence/vf-preview-v5-exact-paths.json)。
全局Nov30权限、旧四角色和历史PG/账本均保留；本实例模型许可在私有卷内暂停，
实际AI_UID出网策略为REJECT、provider_ip_count=0、dns_count=0。共享canonical账本仍9笔，
原调用ID哈希一致，无新增付费调用，无复制/重置；另一个实例没有重启或改权限。

健康临时身份新增了严格GET路由/到期/原mTLS绑定限制，避免上传正式业务身份。
随后按最新VF优先级撤下未使用的GH临时绑定，实际旧配对403；没有上传或dispatch GH复验，
临时Secret确认不存在。该GH身份没有用于VF。93项相关回归、原B5A源码冻结检查通过；
`c456312`自然CI 51项SUCCESS、1项SKIPPED。
[检查范围和边界](evidence/vf-preview-backend-handoff-checks.json)。

当前已部署VF源码仍为 `2f75721c5900f2a6d7c933b72ca82053d6746df3`，
`dpl_HC5ZuK9m7GhJyDfhv2NfHs3EUrSd`，早于本次凭据写入。指定分支缺少既有
`VF_VRAE_PREVIEW_ENABLED`、独立 `VF_VRAE_PREVIEW_SESSION_KEY`、
`VF_VRAE_PREVIEW_TARGET_URL`。**用户已明确选择由VF团队自行配置并重部署**；
Codex3未更改启用开关、部署保护、VF源码、Preview部署或生产。
VF团队需在该短期窗口内配置三项并重建原分支Preview，随后完成真实UI确认、Vercel Node BFF
health/OpenAPI200、application/authorize201、diagnoses202、原Worker DRAFT_READY、
同主体状态200及关键拒绝。GitHub Runner/本机mTLS/凭据写入均不替代这些实际出站证据。
未报E2E_PASS，不因临时密钥已删除或CI通过而自动发布报告。
