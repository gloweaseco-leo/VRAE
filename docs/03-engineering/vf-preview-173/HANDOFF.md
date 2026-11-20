# Issue 173 · VEYFRONT PR37 Preview API 交付

当前回执：**BLOCKED:DEDICATED_IDENTITY_REGISTRATION_AND_PRIVATE_DELIVERY**。
按 [Owner 最新转交](https://github.com/gloweaseco-leo/VRAE/issues/173#issuecomment-7026432530)，VF动态BFF已完成，旧协议适配阻断撤销。
凭据真实注册/私有收讫后再核对Vercel出站证据；没有实际证据不宣告联调通过。PR174保持独立Draft。

本交付基于独立分支 `codex1/vf-preview-173` / main `1e3cd9cd409e695dad8b4e0a8357130ae35f6d7e`。
最新只读核查 VRAE PR172 `c456312aec1f54a2a6c89e42f3bce990a0081109` 与 VEYFRONT PR37
`2f75721c5900f2a6d7c933b72ca82053d6746df3`（2026-11-20 UTC）。二者不是本轮验证过的运行 SHA。
没有读取 Codex3 工作树、容器、PG、凭据卷或 Tailscale 配置；没有签发真实凭据、消费真实邀请或修改 VF。

## 当前消费协议核对（10 行）

1. PR37 `createDiagnosisClient.submit()` 已改POST `/v1/diagnoses`，不再消耗静态VFSubmit数组。
2. PR172 `/v1/diagnoses` 输入 `{url,idempotency_key,accepted_at,consent_version,language}`，由原本机签发器生成 VFSubmit 并直接原 PG admission；不是 VFSubmit 导出接口。
3. 新会话先 POST `/v1/invitation-session`；邀请一次性，`__Host-vrae-targets` 与 `X-CSRF-Token` 只能留 BFF。
4. POST `/v1/target-applications` 必须恰含 `url,paths,consent`；consent 为 `version,read_only_authorized:true,model_data_notice:true`。
5. POST `/v1/target-applications/authorize` 必须恰含 `application_token`；授权201后才有当前目标/计划，`target_id` 来自响应。
6. `/v1/diagnoses` 的 `accepted_at` 必须不早于当前 policy.created_at、在当前30分钟内且不晚于服务器当前时间；原请求完整保留用于重试。
7. PR37已先展示当前intake原文、以`paths: []`完成201/201授权，再由用户主动确认记录accepted_at，保持原始幂等意图。
8. 当前只用`VRAE-READONLY-DIAGNOSIS-1`，不选择新增可选模型同意`VRAE-READONLY-AI-DIAGNOSIS-2`；本阶段不安排新模型调用。
9. 两边均严格匹配 `X-VRAE-API-Version: vrae.diagnosis-api.v1`、40位 `X-VRAE-Source-SHA`、`Cache-Control:no-store` 和精确媒体类型。
10. 健康/OpenAPI成功用JSON；PR37已支持失败时的VF safe_error媒体，旧403被映射503的问题已处理。

VF协议适配已完成，不要求VF重复开发或重新生成静态签发包。本交付不实现第二套签发平台，不改PR172，不改VF源码。
新动态接口没有完整 JSON Schema：OpenAPI 的 requestBody 是描述字段，须同时读取
`/v1/target-intake-contract` 的真实文案与字段；不能从旧静态 OpenAPI 文件推断运行实例已启用 intake。

## Vercel 分支环境表

全部仅限 `feature/vf-b-offline-g1-adapter` 的 **Preview**、Node 服务端；由 VF 有权限的负责人私有录入。
未读取 Vercel 实际变量，因此下表表示代码要求，不声称已配置。

| 变量 | 要求 / 本轮状态 |
| --- | --- |
| `VRAE_DIAGNOSIS_BASE_URL` | `https://dong.tail27555e.ts.net`（443）；Owner称已配，未私有回读 |
| `VRAE_DIAGNOSIS_CA_PEM` | 验证服务器真实证书的CA链，**不是**客户端签发CA的当然替代品；待操作者提供 |
| `VRAE_DIAGNOSIS_CLIENT_CERT_PEM` | Preview独有 clientAuth 证书，SHA256(DER)绑定；待签发 |
| `VRAE_DIAGNOSIS_CLIENT_KEY_PEM` | 对应私钥，仅受信root私有卷生成存储，私有录入；待签发 |
| `VRAE_DIAGNOSIS_BEARER` | 新独立随机Bearer，仅服务配置保存其SHA256；待注册 |
| `VRAE_DIAGNOSIS_SOURCE_SHA` | 操作者实际受信健康响应的40位源码SHA；不能拿PR HEAD代填 |
| `VF_VRAE_PREVIEW_SESSION_KEY` | VF自己生成32随机字节、64小写hex，用于其会话加密；不得共用服务Bearer |
| `VF_VRAE_PREVIEW_TARGET_URL` | `https://vrae-owned-source.tail27555e.ts.net/`，动态流程唯一允许的自控源根地址 |
| `VF_VRAE_PREVIEW_ENABLED` | VF团队决定启用窗口；身份/实连未验收，不在本仓自动设1 |
| `VRAE_REPORT_*` | Stage B独立身份，非本轮诊断联调凭据；报告地址不等于报告可用 |

原始TCP Funnel保留端到端TLS，客户端校验服务器CA及hostname；服务端验证客户端CA、证书指纹及对应Bearer。
Host必须为允许的精确值；BFF不要添加浏览器Origin。业务 Accept 与所有业务POST Content-Type均为
`application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"`；成功健康/docs Accept为 `application/json`。
轮换与重部署后，服务端实际SHA变更须由有权VF方更新分支pin；不得关闭严格SHA检查。

Vercel官方[env CLI](https://vercel.com/docs/cli/env)与[环境变量管理](https://vercel.com/docs/environment-variables/managing-environment-variables)
支持 Preview 分支定向及私有文件stdin录入。操作者在已核对项目/team的受信Linux环境中执行，例如：

```sh
# 仅示意路径；不得在Windows公共目录或CI生成这个文件。
vercel env add VRAE_DIAGNOSIS_CLIENT_KEY_PEM preview feature/vf-b-offline-g1-adapter --sensitive < /root-private/vf_preview_173/VRAE_DIAGNOSIS_CLIENT_KEY_PEM
```

其余4项分别同样录入；先核对所装CLI `env add --help` 的分支参数（版本可能支持 `--git-branch`），已有项使用相应update流程。
不使用 `--value`、echo、命令行秘密、聊天、GitHub、公开artifact、`NEXT_PUBLIC_*` 或 Production。
变更后仅由VF负责人重新部署指定Preview，核对deployment ID、Git SHA及分支；不改生产alias/域名。不得通过env pull搬运Secrets。

## 唯一受信本机动作：一个串行 Preview 身份注册/授权交接窗口

执行者仅 Codex3 或 Owner 已明确授权的唯一本机操作者。**这是一项待执行请求，不是Codex1已执行的操作。**
现在即可在安全窗口接单，无需等Codex3整轮结束。以下是同一动作的成功条件：

1. 从原受信管理入口核对当前运行image/source SHA、原PG、单Worker、本次任务不会调用模型、原canonical账本未变，确认没有活动capture。
   核对当前SOURCE_ADMIN签名 `source-ownership.json` 中自控源的真实节点/证书、有效期，deployment delegation、PG计划与许可当前性。
   不延长既有许可，不创建假控制证明。任一无效就返回准确拒绝原因。
2. 审查并在原root-owned ext4私有卷中运行本仓 `integration/vf_preview_handoff/stage_identity.py`，参数为原私有根、
   真实server验证CA文件、刚核对的运行SHA及新 `vf_preview_*` role。多个业务APP存在时用`--source-role`明确原APP。
   新版跳过PR172临时`health_probe`绑定，不复制健康限定权限；即使显式选health role也拒绝。
   脚本只暂存，不读运行容器、不改PG或API配置。
   证书有效期取当前客户端CA/现有deployment许可/1小时三者最早值，不自动续期；少于5分钟拒绝。
3. 原有 `provision.install()` 会插入tenant/capacity，**不能向已有tenant重复执行全量install**。
   用其现有actor注册语义作最小additive事务：新LOGIN role，仅 `target_v1_app`、NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE；
   同原tenant写 `ra4a_private.principals`、`ra4a_private.assignments`、`target_v1.actors`，actor有效期不得超过暂存证书截止。
   私有password只来自 `binding.private.json`，不抄到命令行。只在原`api.json.bindings`追加新binding，不修改原actor/Worker/REVIEW/AI。
   动态签发器 `caller()`按role要求唯一非health APP binding；Preview必须独立role，不得借用GitHub临时health身份。
4. 由同一操作者通过原 `private_host`/control 流程安全重新stage/reload原配置；先确认原acceptance身份与新身份都能ready200，
   新证书+旧Bearer/旧证书+新Bearer均403，无证书TLS拒绝。原actor仍可工作，不得创建第二个API/PG/Worker。
   可由该唯一操作者在原root上下文运行`python -B <已审只读脚本目录>/check_identity.py --bundle <暂存目录> --control-config <原caller.json>`：
   检查器与`stage_identity.py`放同一已审目录即可独立运行，无需修改PR172代码或等待本PR合并。
   只GET诊断ready/OpenAPI，检验两身份/交叉配对/错误Bearer/无证书；严格hostname/CA/SHA与证书指纹，非TLS网络失败不会算拒绝成功。
   control身份仅作操作者本机对照，永不导出给VF；该脚本不测报告、不消费邀请、不触发模型，也不声称Vercel出站。
5. 用原 `infra.windows_service.operator invite --subject <new-opaque-subject>` 创建一个全新邀请（绑定当前原tenant；不复用已消耗邀请）。
   该命令只建邀请，**不等于**站点授权或用户同意；原动态入口在当前受邀session下完成challenge/authorize及实际确认。
   真实文本必须来自当前intake contract。操作者私有交接专用5项与邀请给指定VF负责人；CA私钥、permission/source/deployment签名私钥永不离卷。
6. 只返回非秘密：实际健康SHA、api版本、证书DER指纹、notBefore/notAfter、注册成功/旧身份回归、站点控制证明类型与有效期、
   邀请是否新建、私有接收方确认；不返回邀请/token/session/私钥。没有可用私有接收通道时精确报 `PRIVATE_RECIPIENT_CHANNEL_UNAVAILABLE`。

`stage_identity.py` 根路径/父路径检查、0600输入、独立密钥及Bearer、排他创建、SHA一致性都是暂存保护；
它不验证本机真实控制权、签名委托当前性、当前PG或运行SHA，以上必须由原受信入口核对。
暂存物不代表注册成功。root操作者也必须确认输入根位于原ext4卷，不能在宿主NTFS/repo中生成真实私钥。

轮换：多业务APP绑定且未指定source-role时拒绝；操作者须显式审查选定原tenant/role，不能删除原身份绕过此门禁。
后续按同一原注册路径新增新role/证书/独立Bearer，私有更新Preview并验证后撤旧绑定、禁用旧actor/assignment及角色LOGIN。
原TLS客户端CA未实现按序列号CRL门禁；撤销依靠删除证书/Bearer绑定与原PG当前权限，不声称有CRL能力。
即时撤销同样需原配置reload，随后旧配对ready403与原会话status403；到期需实际到期请求拒绝，不能仅验notAfter字段。
回滚只移除本轮新增绑定/禁用本轮actor，保留原PG任务/许可/会话历史；不回滚时间或恢复过期授权。

## VF团队的真实联调准备

`integration/vf_preview_handoff/vercel_probe.mjs` 是VRAE提供的Node探针，默认只读检查ready/OpenAPI/错误Bearer/无会话403。
必须由VF团队在其指定Preview的服务器端运行；本地伪造 `VERCEL_*` 不算出站证据。
探针结果须和同一deployment ID的Vercel服务器执行记录、Git SHA交叉核对。完整响应只在内存，公开输出为HTTP状态/响应哈希/非秘密元数据。
默认执行不消费邀请；不会自动开启VF预览或发起模型调用。

VF当前已实现动态流程、私有会话与原意图恢复，实际联调应直接使用其现有Preview界面，不要求新增本探针接线。
探针的可选动态入口`runProbe(env,true,undefined,confirmConsent)`仅供其授权测试者选择：回调须在授权201后取得真实主动确认，不能自动代签同意。
它使用`paths: []`及原非模型同意，不读取报告。CLI `--execute`没有回调会在消费邀请前拒绝。
`VRAE_PREVIEW_INVITATION`、`VRAE_PREVIEW_IDEMPOTENCY_KEY` 及当前接受事实仅在受控会话私有提供，不写公共配置。

成功后探针也仅返回 `DRAFT_READY_PENDING_REVOCATION_AND_CROSS_SUBJECT_EVIDENCE`，不会自行宣告HANDOFF_READY。
还必须补齐真正不同受邀主体越权403、到期与撤销拒绝（单操作者窗口）、有权限来源的原PG/单Worker关联证据。
错误mTLS应区分TLS拒绝与网络不可达；GitHub runner历史通过不能作为Vercel成功。
真实站点始终是operator-owned自控测试源，不能称正式客户网站；报告保持UNPUBLISHED。模型与报告读取均非本阶段前置。
原实例按tenant+origin复用当前plan；操作者核对当前plan的exact_paths和model_processing必须与本轮`paths: []`/非模型同意相符。
过期/撤销或scope不符时原authorize会409；不得自动延长、复活许可或切换模型同意来通过。本项由原操作者做当前来源核验，不是要求VF重新开发。

## 本轮证据和完成门槛

本轮实际完成：源码只读比对、独立worktree、隔离暂存安全验证、探针拒绝/协议校验测试。原始测试输出和摘要在 `evidence/`。
首次隔离测试因read-only根未设TMPDIR而未进入测试；原7+5项证据保留。最新14项Python（含真实loopback TLS）及5项Node通过。
新增TLS测试首次遇到合成server证书/CA缺失严格验证扩展，保留RED并修正测试证书AKI/KeyUsage；未放宽客户端CA/hostname验证。
隔离容器只有本工作树只读挂载、network none和新tmpfs；未挂原凭据/PG/engine socket，合成私钥仅在root tmpfs，容器结束销毁。

真实运行SHA、Preview证书指纹/有效期、当前站点授权、Vercel GET200/POST202/status200、真实跨主体/过期/撤销均**尚未观察**。
历史Owner公开[Stage A回执](https://github.com/gloweaseco-leo/VRAE/pull/172#issuecomment-7009343431)
陈述 `dec729dca05fb4e4dadfea506db4649d246ed294` 双主体外部runner验收；这是历史背景，不作为本轮运行SHA或Vercel实证。
PR37新HEAD GitHub Vercel status为Deployment completed，deployment `HC5ZuK9m7GhJyDfhv2NfHs3EUrSd`，仅证明部署状态，不证明BFF调用VRAE。

只有专用身份已注册/私有交付、当前源授权链有效、VF协议匹配且指定Vercel Preview真实出站
ready200/openapi200/合法202/原Worker DRAFT_READY/同主体status200/错误凭据与跨主体403/到期与撤销拒绝、实际SHA齐全，
才能改发 `VF_PREVIEW_HANDOFF_READY`。Owner最新交付顺序为`VF_PREVIEW_CREDENTIALS_DELIVERED`→真实Vercel `VF_PREVIEW_E2E_PASS`，均以实际证据为准。
当前唯一VRAE P0如首行：原私有实例动作由Codex3/唯一获授权操作者完成。收到非秘密签发/收讫确认后，Codex1核对证据并协同VF真实201/201/202/DRAFT_READY；不再以协议适配为阻断。
