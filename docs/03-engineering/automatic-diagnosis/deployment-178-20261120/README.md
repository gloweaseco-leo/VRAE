# PR178 合并与上线记录

PR [178](https://github.com/gloweaseco-leo/VRAE/pull/178) 已合并并部署到原 VRAE Windows/Docker 实例。
运行源码为 `af8a4708102952b88f28ff0a16ad422e36592c77`，与通过测试的 PR head
`26e92b95feecd79054749cb1722b723bfa6e7a08` 文件树一致。
运行镜像固定为 `sha256:05e9744da3a59e3f08d4387574e87d5e1c0e3599e25eb73861064b3d4d12b417`。
验证时间为 2026-11-20 09:00–09:04 UTC，所有公开记录均脱敏。

## 已上线行为

VF 受信后台可以直接 `POST /v1/diagnosis-sessions`，请求体 `{}`，取得每位访客独立的
Cookie/CSRF；新诊断不再依赖一次性 `VRAE_PREVIEW_INVITATION`。
沿用原 mTLS、Bearer、媒体类型、授权声明及诊断/结果端口。
具体调用顺序见 [接入契约](../automatic-sessions/README.md)。

原 VF 身份、私钥、Bearer、CA 和 actor epoch 保持原样。额外 24 小时 Preview 截止已去除，
证书和 actor 有效期改为服从现有部署/模型许可/CA 中最早的授权截止：
2026-11-30 15:59:59 UTC（北京时间 23:59:59）。这不是永久服务授权；后续凭据轮换由后台维护。
原已消费邀请及过期会话未被重置或复活。

## 上线实测

- `session-probe.json`：使用原 VF 身份，经公开 HTTPS、不带邀请或 Cookie，连续两次建会话均为 200；
  两个不同主体及上下文，Cookie 为 Secure/HttpOnly/SameSite=Strict，并有 CSRF。
  伪造主体和错误 Bearer 均为 403。该探针从原 PG 网络命名空间访问公开入口，属于同宿主验证。
- `verify.json`：服务/契约正反检查通过，四个服务容器运行，模型配置有效；
  原 21 份工件全部回放，21 份 AI 回执及其摘要一致，零待处理任务。
- `public.json`：同宿主独立 bridge 容器经公开 HTTPS 的服务、契约和错误身份检查通过。
- `report-probe.json`：诊断/报告端口共八项正反检查通过，包括错误证书、错误 Bearer 及无证书。
- 模型共享账本仍为原 9 条调用，逻辑摘要未变，费用许可仍为每日人民币 5 元、原截止日期。
  本次未提交客户网站、未新增采集或真实模型调用，以上结果不声称是客户业务验收。

## 私有交接与 VF 后续动作

续期 `VRAE_DIAGNOSIS_CLIENT_CERT_PEM` 和完整 `VRAE_DIAGNOSIS_SOURCE_SHA` 已写入原 VF 项目、
原 `feature/vf-b-offline-g1-adapter` 分支的 Preview Sensitive 变量。
私密值仅经匿名进程管道交接，未写入 Windows 文件、Git、日志或聊天。
`handoff.json` 与 `handoff-metadata.json` 仅保留结果及作用域元数据。

**VF 团队需要按新契约改用 `POST /v1/diagnosis-sessions {}` 并自行重新部署，加载更新后的私有变量。**
此前已经构建的 VF 部署不会自动获得新环境变量；仅 VRAE 上线不能让旧 VF 调用自动切换。
VRAE 未改 VF 仓库、前端、发布配置，也未触发 VF 部署，未验证 VF BFF 出网或页面交互。
每个访客上下文独立保存会话；不要在结果轮询时换会话，也不要跨新主体自动重提已提交或结果不明的旧请求。

## 备份、回滚与 CI

切换前已完成原实例静止冷备份，PG/报告 ledger 归档和私有配置封存于受控 Linux 卷；
`backup.json` 含摘要及校验结果。共享模型账本没有被复制、重建或清零。
原运行源码为 `2d2ccdeb5af1c6df8ac3041a1fc13c29d8d7b808`，
原镜像为 `sha256:d1491b280b7104092f0546a1f90f698b41a488c6273b7067280526272756d0fd`。
需要回滚时须由受信操作流程同时恢复匹配源码的签名模型许可、源码 pin 和原证书绑定，不能只换运行镜像。

PR head 的 24 项工作流已完成，23 项成功，包括 Windows 3.11/3.13 边界及真实 PG16 测试。
唯一失败为已存在的 B5A `ACCEPTED_SOURCE_CHANGED` 源码冻结检查；该门禁未改动或绕过，Owner 已批准合并。
逐项状态见 `ci-final.json`，实现验证见 [原验证记录](../automatic-sessions/validation.json)。

本记录仅追加上线证据，不修改已验收历史材料。VRAE 工作完成，等待 Owner 独立验收。
