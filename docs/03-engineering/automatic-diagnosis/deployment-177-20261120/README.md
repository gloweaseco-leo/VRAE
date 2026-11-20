# PR177 已合并 main 并部署

Owner 已批准合并、部署。核对时 PR177 已合并到 main，实际部署提交为
`2d2ccdeb5af1c6df8ac3041a1fc13c29d8d7b808`，其 Git tree 与已测试的 `10aca76` 完全一致。
没有重复合并或改变此前保留的 B5A 冻结门禁。

- 原实例：`vrae-windows`。
- 原公网入口：`https://dong.tail27555e.ts.net`。
- 运行镜像：`sha256:d1491b280b7104092f0546a1f90f698b41a488c6273b7067280526272756d0fd`。
- 受信操作器：`sha256:215ba348dafa986e26c060885166bfb2ae9c4533727dbac0bea8a7433e8c11a6`。
- 原 PG、Worker/APP/REVIEW、独立 AI 和转发服务均运行；响应头绑定上述 main 合并提交。

## 实际部署核验

`verify.json`、`public.json` 记录本地及原443/Funnel入口的健康、OpenAPI、一次授权契约均为200，
错误 Bearer 为403。新 OpenAPI 已包含 `capture_summary`、`analysis_outcome` 等字段。
`report-probe.json` 复用原探针，诊断与正式报告服务的合法身份200、错误 Bearer/证书403、
无证书TLS拒绝，共8项通过。未修改正式报告权限。

公网探针来自同一Windows宿主上的新bridge操作器，**不是独立外部网络或 VF BFF/UI 端到端验收**。
没有提交网站，没有真实模型调用，也没有重跑原已结束任务。

升级前后21份历史采集工件和21条AI回执摘要完全相同；21份工件全部通过原版本 NativeSource 重放。
原共享模型账本仍为9笔，逻辑摘要为
`9a59d0b8664613f6c1d1e237a98d8ccd5cb01a7dba042be1fb682d8b626a2886`。
没有复制、重置、退款或替换该账本。

原模型许可只重绑新源码SHA，日上限仍为CNY5，许可仍截至2026-11-30T15:59:59Z，
原单次上限、无自动重试、数据最小化及独立隔离保持不变。
AI实际启动核验为配置有效、UID10008、固定供应商目的地址2个；这不是实际Qwen调用验收。

## 冷备及回退材料

原PG与报告Ledger完成静止冷备，私有操作材料保存在独立Linux卷
`vrae-windows-pr177-backups`；文件摘要见 `backup.json`。
原镜像 `sha256:7c3b0dc2f566223170d32d8465c54fb37fea38d2fae769c8f0221290b898e78d`
和原源码 `7a09748` 保留，原控制器manifest保留previous坐标。

冷备本身成功，但首个操作器的备份后只读核对仍处于PG重启前的网络命名空间，连接被拒绝。
使用当前PG命名空间的新操作器复核后，备份文件、工件、回执及模型账本全部匹配。
未重复备份、未恢复覆盖数据、未重置Docker/WSL。此纠错记入 `receipt.json`。

必要时由原受信操作器执行回退，并同时恢复私有冷备中的旧模型许可源码绑定和连接源码标识；
不能只回退镜像。原共享模型账本不随镜像回退而恢复或清零。

## VF 私有交接

原Preview身份 `vf_preview_20261120a`、私钥、证书、Bearer、角色epoch及邀请均未变动，未签发新身份。
角色到期仍为2026-11-21T05:16:57Z（北京时间11月21日13:16:57）。

沿用前次获准的私有交接，仅将 `VRAE_DIAGNOSIS_SOURCE_SHA` 更新为新合并提交；
目标仍是 `veyfront / Preview / feature/vf-b-offline-g1-adapter`，类型仍为Sensitive。
通过Vercel connector重新核对分支、目标、类型与更新时间，未回读凭据，见 `handoff.json`。
没有修改VF源码、其他变量、开关、Production或触发VF部署。

**VF团队需重新部署该Preview分支，加载新源码标识。** 旧部署可能继续按旧SHA拒绝新VRAE响应。
VRAE服务本身已升级；旧诊断结果和原AI不可用回执不会被此部署改写为成功。

本目录仅含源码、镜像、摘要、状态和部署核验信息，不含客户网址、任务标识、Cookie、凭据或网页原文。
